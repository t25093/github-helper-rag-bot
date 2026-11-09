"""טעינת המסמכים הארגוניים, חלוקה לפי כותרות, יצירת וקטורים ושמירה ב-ChromaDB.

הרצה:  python ingest.py
"""
import re
from pathlib import Path

import chromadb
from llama_index.core import Settings, SimpleDirectoryReader, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter
from llama_index.core.schema import TextNode
from llama_index.vector_stores.chroma import ChromaVectorStore

import config
from models import get_embed_model, with_retry

MARKDOWN_EXT = {".md", ".markdown"}


def load_documents():
    if not Path(config.DATA_DIR).exists() or not any(Path(config.DATA_DIR).iterdir()):
        raise SystemExit(f"התיקייה '{config.DATA_DIR}' ריקה. הכניסי אליה את המסמכים הארגוניים.")
    reader = SimpleDirectoryReader(
        config.DATA_DIR,
        recursive=True,
        required_exts=[".md", ".markdown", ".txt", ".pdf", ".docx"],
        exclude=["README.md"],
    )
    docs = reader.load_data()
    for doc in docs:
        strip_front_matter(doc)
        # מטא-דאטה טכנית לא צריכה להיכנס לווקטור. כותרת ונושא המסמך כן נשארים
        noise = ["file_path", "file_type", "file_size", "creation_date", "last_modified_date", "last_accessed_date"]
        doc.excluded_embed_metadata_keys = noise
        doc.excluded_llm_metadata_keys = noise
    return docs


FRONT_MATTER_RE = re.compile(r"\A\s*﻿?---\s*\n(.*?)\n---\s*\n", re.S)


def strip_front_matter(doc):
    """קבצים שמתחילים בבלוק --- title/topic --- : הבלוק עובר למטא-דאטה ומוסר מהטקסט,
    כדי שלא יידבק לסעיף הראשון כטקסט רגיל."""
    text = doc.get_content()
    m = FRONT_MATTER_RE.match(text)
    if not m:
        return
    for line in m.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            doc.metadata[key.strip()] = value.strip()
    doc.set_content(text[m.end():])


def body_length(text: str) -> int:
    """אורך התוכן של סעיף בלי שורות הכותרת."""
    return len("".join(l for l in text.splitlines() if not l.lstrip().startswith("#")).strip())


def header_path(node) -> str:
    """מחזיר את שרשרת הכותרות של הסעיף (MarkdownNodeParser שומר אותה במטא-דאטה)."""
    return node.metadata.get("header_path", "").strip("/")


def merge_tiny_nodes(nodes):
    """סעיף שהוא רק כותרת (בלי תוכן) לא שווה וקטור משלו - מאחדים אותו עם הסעיף שאחריו.
    סעיף קצר שיש בו תוכן (למשל הגדרה במילון מונחים) נשאר קטע נפרד."""
    merged, carry = [], None
    for node in nodes:
        if carry is not None and carry.ref_doc_id == node.ref_doc_id:
            node.set_content(carry.get_content() + "\n\n" + node.get_content())
            carry = None
        elif carry is not None:  # המסמך הסתיים - שומרים את הקטע הקצר כמו שהוא
            merged.append(carry)
            carry = None
        if body_length(node.get_content()) < config.MIN_BODY_CHARS:
            carry = node
        else:
            merged.append(node)
    if carry is not None:
        merged.append(carry)
    return merged


def split_documents(documents):
    md_parser = MarkdownNodeParser(include_metadata=True)
    # פיצול משני לסעיפים ארוכים מדי ולקבצים בלי כותרות - גם הוא ללא חפיפה
    fallback = SentenceSplitter(chunk_size=config.MAX_CHUNK_TOKENS, chunk_overlap=config.CHUNK_OVERLAP)

    is_md = lambda d: Path(d.metadata.get("file_name", "")).suffix.lower() in MARKDOWN_EXT
    md_docs = [d for d in documents if is_md(d)]
    other_docs = [d for d in documents if not is_md(d)]

    nodes = merge_tiny_nodes(md_parser.get_nodes_from_documents(md_docs))

    final = []
    for node in nodes:
        # סעיף ארוך מדי מפוצל שוב, וכל חלק מקבל את שם הכותרת שלו כדי לא לאבד הקשר
        if len(node.get_content()) > config.MAX_CHUNK_TOKENS * 3:
            title = header_path(node)
            for part in fallback.split_text(node.get_content()):
                text = part if not title or part.startswith("#") else f"[{title}]\n{part}"
                final.append(TextNode(
                    text=text,
                    metadata=dict(node.metadata),
                    excluded_embed_metadata_keys=list(node.excluded_embed_metadata_keys),
                    excluded_llm_metadata_keys=list(node.excluded_llm_metadata_keys),
                ))
        else:
            final.append(node)

    final.extend(fallback.get_nodes_from_documents(other_docs))
    add_positions(final)
    return final


def add_positions(nodes):
    """שומר לכל קטע את המיקום שלו בקובץ (0, 1, 2...), כדי שבזמן החיפוש אפשר יהיה
    להביא גם את הקטעים שלפניו ואחריו - למשל את השלב הקודם והשלב הבא בתהליך."""
    counters = {}
    for node in nodes:
        name = node.metadata.get("file_name", "")
        node.metadata["chunk_index"] = counters.get(name, 0)
        counters[name] = node.metadata["chunk_index"] + 1
        node.excluded_embed_metadata_keys = list(node.excluded_embed_metadata_keys) + ["chunk_index"]
        node.excluded_llm_metadata_keys = list(node.excluded_llm_metadata_keys) + ["chunk_index"]


def build_index(nodes):
    client = chromadb.PersistentClient(path=config.CHROMA_PATH)
    # בונים מחדש בכל הרצה כדי שלא ייווצרו כפילויות
    if config.COLLECTION_NAME in [c.name if hasattr(c, "name") else c for c in client.list_collections()]:
        client.delete_collection(config.COLLECTION_NAME)
    collection = client.create_collection(
        config.COLLECTION_NAME, metadata={"hnsw:space": config.DISTANCE_METRIC}
    )
    vector_store = ChromaVectorStore(chroma_collection=collection)
    storage = StorageContext.from_defaults(vector_store=vector_store)

    # מכניסים במנות קטנות כדי לעמוד במגבלת הקצב של השכבה החינמית
    index = VectorStoreIndex([], storage_context=storage)
    batch = config.EMBED_BATCH_SIZE
    for i in range(0, len(nodes), batch):
        with_retry(index.insert_nodes, nodes[i:i + batch])
        print(f"  נשמרו {min(i + batch, len(nodes))}/{len(nodes)} קטעים")
    return collection.count()


def main():
    Settings.embed_model = get_embed_model()
    docs = load_documents()
    print(f"נטענו {len(docs)} מסמכים")
    nodes = split_documents(docs)
    print(f"נוצרו {len(nodes)} קטעים (chunks) לפי כותרות")
    count = build_index(nodes)
    print(f"סיום. ב-ChromaDB יש {count} וקטורים.")


if __name__ == "__main__":
    main()
