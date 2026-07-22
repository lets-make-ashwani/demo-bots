import asyncio
import functools
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatAction

def send_typing_action(func):
    """
    Middleware decorator that displays the 'typing...' indicator in the chat
    periodically while the wrapped async function is running.
    """
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update.effective_chat or not update.message:
            return await func(update, context, *args, **kwargs)

        chat_id = update.effective_chat.id

        async def keep_typing():
            try:
                while True:
                    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
                    # Telegram typing indicator expires after ~5 seconds, so we refresh it every 4.5 seconds.
                    await asyncio.sleep(4.5)
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

        typing_task = asyncio.create_task(keep_typing())
        try:
            return await func(update, context, *args, **kwargs)
        finally:
            typing_task.cancel()
            try:
                await typing_task
            except asyncio.CancelledError:
                pass
    return wrapper
