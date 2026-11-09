"""קליינט צ'אט ב-Chainlit.

הרצה:  chainlit run app.py
"""
import chainlit as cl

import config
from rag import OrgBot

_bot = None


def get_bot():
    global _bot
    if _bot is None:
        _bot = OrgBot()
    return _bot


@cl.on_chat_start
async def start():
    try:
        await cl.make_async(get_bot)()
    except Exception as e:
        await cl.Message(content=f"שגיאה בטעינת הבוט: {e}").send()
        return
    # היסטוריה נפרדת לכל משתמש/לשונית - שיחה חדשה מתחילה נקייה
    cl.user_session.set("history", [])
    await cl.Message(content=config.WELCOME).send()


@cl.on_message
async def on_message(message: cl.Message):
    history = cl.user_session.get("history") or []
    try:
        bot = get_bot()
        answer = await cl.make_async(bot.ask)(message.content, history)
    except Exception as e:
        await cl.Message(content=f"אירעה שגיאה: {e}").send()
        return

    if answer.expanded:
        async with cl.Step(name="הרחבת השאלה") as step:
            step.output = answer.search_query

    await cl.Message(content=answer.text).send()

    if answer.text == config.UNCLEAR:
        return  # שאלה שלא הובנה לא נשמרת בזיכרון השיחה
    history.append((message.content, answer.text))
    cl.user_session.set("history", history[-config.HISTORY_TURNS:])
