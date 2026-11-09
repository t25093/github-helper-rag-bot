"""יצירת מודלי Gemini + ניסיון חוזר במקרה של חריגה ממגבלת הקצב (429)."""
import random
import time

from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
from llama_index.llms.google_genai import GoogleGenAI

import config


def _check_key():
    if not config.GOOGLE_API_KEY:
        raise RuntimeError("חסר GOOGLE_API_KEY. העתיקי את ‎.env.example ל-‎.env והכניסי מפתח.")


def get_embed_model():
    _check_key()
    return GoogleGenAIEmbedding(
        model_name=config.EMBED_MODEL,
        api_key=config.GOOGLE_API_KEY,
        embed_batch_size=config.EMBED_BATCH_SIZE,
    )


def get_llm():
    _check_key()
    # מגבלת אורך מפורשת וגבוהה, כדי שתשובה עם כמה פקודות לא תיחתך באמצע
    return GoogleGenAI(model=config.LLM_MODEL, api_key=config.GOOGLE_API_KEY,
                       temperature=0.1, max_tokens=config.MAX_ANSWER_TOKENS)


def with_retry(fn, *args, **kwargs):
    """מריץ קריאת API ומנסה שוב עם המתנה הולכת וגדלה אם התקבלה שגיאת מגבלת קצב."""
    for attempt in range(config.MAX_RETRIES):
        try:
            return fn(*args, **kwargs)
        except Exception as e:  # ספריית google-genai זורקת סוגי שגיאות שונים
            msg = str(e).lower()
            # 429 = חריגה ממגבלת הקצב, 503 = עומס זמני על המודל. בשני המקרים שווה לנסות שוב
            temporary = any(s in msg for s in ("429", "resource_exhausted", "quota", "503", "unavailable", "overloaded"))
            if not temporary or attempt == config.MAX_RETRIES - 1:
                raise
            wait = (2 ** attempt) * 3 + random.uniform(0, 2)
            print(f"שגיאה זמנית מה-API - ממתין {wait:.0f} שניות (ניסיון {attempt + 1})")
            time.sleep(wait)
