"""מנוע השאלות: הרחבת שאלה -> חיפוש היברידי -> תשובה מהמסמכים בלבד."""
from dataclasses import dataclass, field

import chromadb

import config
from hebrew_bm25 import HebrewBM25
from models import get_embed_model, get_llm, with_retry

EXPAND_PROMPT = """את/ה עוזר/ת שמשכתב/ת שאלות קצרות של משתמש לשאלת חיפוש מלאה.
תחום המסמכים: """ + config.DOMAIN + """.
החזר/י שאלה אחת מלאה וברורה בעברית, בלי הסברים ובלי להוסיף עובדות.
המסמכים משלבים מונחים באנגלית, לכן אם יש לנושא מונח מקובל באנגלית (למשל push, branch, Pull Request),
הוסף/הוסיפי אותו בסוגריים.
אם השאלה היא רצף אותיות בלי משמעות, או שאי אפשר להבין מה שואלים, אל תנחש/תנחשי - החזר/י רק את המילה: UNCLEAR

שאלה מקורית: {question}
שאלה מורחבת:"""

CONDENSE_PROMPT = """לפניך שיחה בין משתמש לבוט, ושאלת המשך של המשתמש.
תחום המסמכים: """ + config.DOMAIN + """.
המשימה: לנסח מחדש את שאלת ההמשך כשאלה אחת עצמאית ומלאה בעברית, שאפשר להבין גם בלי השיחה.
- אם השאלה מתייחסת לשיחה ("איך להמשיך?", "ומה אחר כך?", "למה?", "ואם זה לא עובד?"), השלם/השלימי ממנה את הנושא
  ואת השלב שבו נמצאים, למשל: "מה השלב הבא אחרי git commit כשמעלים פרויקט לגיטהב?".
- אם השאלה עוסקת בנושא חדש, החזר/החזירי אותה כמו שהיא, בניסוח מלא.
- אם יש לנושא מונח מקובל באנגלית (למשל push, branch), הוסף/הוסיפי אותו בסוגריים.
- אם שאלת ההמשך היא רצף אותיות בלי משמעות (למשל שגיאת הקלדה), או שאי אפשר להבין מה שואלים,
  אל תנחש/תנחשי לפי השיחה - החזר/י רק את המילה: UNCLEAR
החזר/י רק את השאלה, בלי הסברים ובלי לענות עליה.

השיחה עד עכשיו:
{history}

שאלת ההמשך: {question}
שאלה עצמאית:"""

ANSWER_PROMPT = """את/ה בוט שעונה על שאלות לפי מסמכי הידע בלבד.
תחום המסמכים: """ + config.DOMAIN + """.
כללים:
1. ענה/י אך ורק לפי הקטעים שלמטה. אסור להשתמש בידע כללי.
2. אם בקטעים יש רק חלק מהתשובה, ענה/י רק על החלק שנמצא, ואל תכתוב/תכתבי מה חסר או מה לא מופיע במסמכים.
   רק אם אין בקטעים שום מידע שקשור לשאלה, כתוב/כתבי בדיוק, מילה במילה ובלי שום תוספת: \"""" + config.NOT_FOUND + """\"
3. ענה/י בעברית, בקצרה ובבהירות. אל תציין/תצייני שמות מסמכים או מספרי קטעים,
   ואל תפנה/תפני את המשתמש "לקובץ אחר" או "לתסריט" - המשתמש לא רואה את הקבצים. התעלם/י מהפניות כאלה בקטעים.
4. פקודות (למשל git push) ושמות כפתורים מעתיקים בדיוק כמו שהם מופיעים בקטעים.
   פקודות שמריצים ברצף כותבים יחד בבלוק קוד אחד שמתחיל ב-```bash, פקודה בכל שורה - ולא בלוק נפרד לכל פקודה.
   בלי גרש הפוך (`) נוסף בתוך הבלוק.
   אם בפקודות שבתשובה הזו יש ערכים לדוגמה שצריך להחליף (למשל USER, REPO, my-project, feature-login, "השם שלך"),
   כתוב/כתבי זאת פעם אחת בלבד, במשפט קצר בסוף. אם אין בתשובה פקודות עם ערכים כאלה - אל תכתוב/תכתבי משפט כזה.
   main ו-origin הם שמות רגילים ולא דוגמאות - אין להעיר עליהם.
   אסור להמציא פקודה או אפשרות שלא מופיעה בקטעים.
5. אם יש בקטעים צעדים לפי סדר, הצג/הציגי אותם כרשימה ממוספרת, עם כל השלבים שמופיעים בקטעים
   ובסדר שלהם - בלי לדלג על שלבים באמצע. אם בקטעים יש גם סיכום של כל הפקודות, אפשר להשתמש בו.
6. השיחה הקודמת נועדה רק כדי להבין למה המשתמש מתכוון. את המידע עצמו לוקחים רק מהקטעים.
   בשאלת המשך, אל תחזור/תחזרי על שלבים שכבר הוסברו בשיחה. המשך/המשיכי מהמקום שבו המשתמש נמצא.

השיחה הקודמת:
{history}

קטעים מהמסמכים:
{context}

שאלת הלקוח: {question}
(השאלה כפי שהובנה מתוך השיחה: {search_query})
תשובה:"""

NOT_FOUND = config.NOT_FOUND


@dataclass
class Answer:
    text: str
    search_query: str
    expanded: bool
    sources: list = field(default_factory=list)  # [(file_name, header, text), ...]


class OrgBot:
    def __init__(self):
        self.embed_model = get_embed_model()
        self.llm = get_llm()
        client = chromadb.PersistentClient(path=config.CHROMA_PATH)
        try:
            self.collection = client.get_collection(config.COLLECTION_NAME)
        except Exception:
            raise RuntimeError("לא נמצא אינדקס. הריצי קודם: python ingest.py")

        # BM25 נבנה מהטקסטים ששמורים כבר ב-Chroma - אין צורך באחסון נוסף
        data = self.collection.get(include=["documents", "metadatas"])
        self.docs = {i: (d, m or {}) for i, d, m in zip(data["ids"], data["documents"], data["metadatas"])}
        self.bm25 = HebrewBM25(list(self.docs), [d for d, _ in self.docs.values()])

        # מפה ממיקום הקטע בקובץ למזהה שלו - לצורך הבאת הקטעים השכנים
        self.position = {}
        for doc_id, (_, meta) in self.docs.items():
            if meta.get("chunk_index") is not None:
                self.position[(meta.get("file_name"), int(meta["chunk_index"]))] = doc_id
        if not self.position and config.NEIGHBORS > 0:
            print("שימי לב: האינדקס נבנה בגרסה ישנה. הריצי שוב python ingest.py כדי להפעיל הבאת קטעים שכנים.")

    def with_neighbors(self, hits):
        """מוסיף לכל קטע שנמצא את הקטעים שלפניו ואחריו באותו קובץ, ומסדר הכל לפי הסדר בקובץ."""
        if config.NEIGHBORS <= 0 or not self.position:
            return hits
        ids = []
        for doc_id, _, meta in hits:
            idx = meta.get("chunk_index")
            if idx is None:
                ids.append(doc_id)
                continue
            for d in range(-config.NEIGHBORS, config.NEIGHBORS + 1):
                j = self.position.get((meta.get("file_name"), int(idx) + d))
                if j and j not in ids:
                    ids.append(j)
        # קבצים לפי סדר הרלוונטיות, ובתוך כל קובץ - לפי סדר הסעיפים
        file_rank = {}
        for j in ids:
            file_rank.setdefault(self.docs[j][1].get("file_name"), len(file_rank))
        ids.sort(key=lambda j: (file_rank[self.docs[j][1].get("file_name")], int(self.docs[j][1].get("chunk_index", 0))))
        return [(j, *self.docs[j]) for j in ids]

    @staticmethod
    def format_history(history) -> str:
        if not history:
            return "(אין - זו השאלה הראשונה)"
        lines = []
        for q, a in history[-config.HISTORY_TURNS:]:
            short = a if len(a) <= config.HISTORY_ANSWER_CHARS else a[: config.HISTORY_ANSWER_CHARS] + "..."
            lines.append(f"משתמש: {q}\nבוט: {short}")
        return "\n\n".join(lines)

    @staticmethod
    def _first_line(resp, fallback: str) -> str:
        text = str(resp).strip()
        return (text.splitlines()[0].strip() if text else "") or fallback

    # --- החלטה 8 (+ שאלות המשך) ---
    def expand_question(self, question: str, history=None):
        """כשיש שיחה קודמת: מנסחים את השאלה מחדש כשאלה עצמאית לפי השיחה.
        בלי שיחה קודמת: מרחיבים רק שאלה קצרה, כמו קודם."""
        if history:
            prompt = CONDENSE_PROMPT.format(history=self.format_history(history), question=question)
            return self._first_line(with_retry(self.llm.complete, prompt), question), True
        if len(question.split()) >= config.EXPAND_IF_WORDS_LESS_THAN:
            return question, False
        resp = with_retry(self.llm.complete, EXPAND_PROMPT.format(question=question))
        return self._first_line(resp, question), True

    # --- החלטה 9: וקטורי (cosine) + BM25, ממוזגים ב-Reciprocal Rank Fusion ---
    def hybrid_search(self, query: str):
        q_vec = with_retry(self.embed_model.get_query_embedding, query)
        vec = self.collection.query(query_embeddings=[q_vec], n_results=config.CANDIDATES_PER_RETRIEVER)
        vector_ids = vec["ids"][0]
        bm25_ids = self.bm25.search(query, config.CANDIDATES_PER_RETRIEVER)

        scores = {}
        for ranking in (vector_ids, bm25_ids):
            for rank, doc_id in enumerate(ranking):
                scores[doc_id] = scores.get(doc_id, 0) + 1 / (config.RRF_K + rank + 1)
        best = sorted(scores, key=scores.get, reverse=True)[: config.TOP_K]
        return [(i, *self.docs[i]) for i in best if i in self.docs]

    def ask(self, question: str, history=None) -> Answer:
        """history: רשימה של (שאלה, תשובה) מהשיחה עד עכשיו."""
        search_query, expanded = self.expand_question(question, history)
        if search_query.strip().upper().startswith("UNCLEAR"):
            print(f"\n[שאלה] {question}\n[חיפוש] לא הובנה - מבקשים מהמשתמש לנסח מחדש")
            return Answer(config.UNCLEAR, question, False)
        # מחפשים עם השאלה המקורית וגם עם המורחבת, כדי שהרחבה לא מוצלחת לא תאבד את המילים של המשתמש
        hits = self.hybrid_search(f"{question}\n{search_query}" if expanded else question)
        hits = self.with_neighbors(hits)

        # הדפסה לטרמינל (לא לצ'אט) - כדי לראות למה הבוט ענה כמו שענה
        print(f"\n[שאלה] {question}\n[חיפוש] {search_query}")
        for _, text, meta in hits:
            print(f"   - {meta.get('file_name', '?')}: {text.strip().splitlines()[0][:70]}")

        if not hits:
            return Answer(NOT_FOUND, search_query, expanded)

        sources, blocks = [], []
        for n, (_, text, meta) in enumerate(hits, 1):
            name = meta.get("file_name", "מסמך")
            header = meta.get("header_path", "").strip("/")
            sources.append((name, header, text))
            blocks.append(f"[{n}] מסמך: {name} {('| ' + header) if header else ''}\n{text}")

        prompt = ANSWER_PROMPT.format(
            history=self.format_history(history),
            context="\n\n---\n\n".join(blocks),
            question=question,
            search_query=search_query,
        )
        resp = with_retry(self.llm.complete, prompt)
        text = str(resp).strip() or NOT_FOUND
        return Answer(text, search_query, expanded, [] if NOT_FOUND in text else sources)
