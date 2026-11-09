"""BM25 עם טוקניזציה שמתאימה לעברית.

ב-BM25 רגיל המילים "לתשלום", "התשלום" ו"ותשלום" הן שלוש מילים שונות, ולכן חיפוש
המילה "תשלום" לא מוצא אותן. כאן כל מילה נשמרת גם בצורתה המקורית וגם בלי אותיות
השימוש בתחילתה (ו, ה, ב, כ, ל, מ, ש).
"""
import re

from rank_bm25 import BM25Okapi

PREFIXES = ("וכש", "ומה", "וה", "וב", "ול", "ומ", "וש", "שה", "שב", "של", "מה", "כש", "לה", "בה",
            "ו", "ה", "ב", "כ", "ל", "מ", "ש")
WORD_RE = re.compile(r"[֐-׿a-zA-Z0-9]+")
NIKUD_RE = re.compile(r"[֑-ׇ]")


def tokenize(text: str):
    text = NIKUD_RE.sub("", text.lower()).replace("\"", "").replace("׳", "").replace("״", "")
    tokens = []
    for word in WORD_RE.findall(text):
        tokens.append(word)
        if "א" <= word[0] <= "ת":
            # לא תמיד ברור כמה אותיות הן תחילית ("בהוראת" = ב+הוראת), לכן נשמרות כל האפשרויות
            stems = {word[len(p):] for p in PREFIXES if word.startswith(p) and len(word) - len(p) >= 2}
            tokens.extend(sorted(stems))
    return tokens


class HebrewBM25:
    def __init__(self, ids, texts):
        self.ids = ids
        self.bm25 = BM25Okapi([tokenize(t) for t in texts]) if texts else None

    def search(self, query: str, k: int):
        """מחזיר רשימת מזהים לפי סדר רלוונטיות."""
        if self.bm25 is None:
            return []
        scores = self.bm25.get_scores(tokenize(query))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return [self.ids[i] for i in ranked[:k] if scores[i] > 0]
