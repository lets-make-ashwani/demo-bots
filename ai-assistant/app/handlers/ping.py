import time
from telegram import Update
from telegram.ext import ContextTypes
from app.middlewares import (
    handle_exceptions, 
    log_request, 
    authenticate_user, 
    rate_limit
)

@handle_exceptions
@log_request
@authenticate_user
@rate_limit
async def ping_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler for the /ping command. Calculates roundtrip network response latency.
    """
    start_time = time.time()
    # Send temporary message
    ping_msg = await update.message.reply_text("🏓 Ping...")
    latency_ms = (time.time() - start_time) * 1000
    
    await ping_msg.edit_text(
        f"🏓 *Pong!*\n\n"
        f"📶 *Network Latency:* `{latency_ms:.0f} ms`",
        parse_mode="Markdown"
    )
