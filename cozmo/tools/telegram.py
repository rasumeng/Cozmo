from . import register_tool

_bot_instance = None

def set_bot_instance(bot):
    global _bot_instance
    _bot_instance = bot

@register_tool()
def telegram_send(chat_id: str, message: str) -> str:
    """Send a message to a Telegram chat."""
    if _bot_instance is None:
        return "Error: Telegram bot not running"
    try:
        import asyncio
        coro = _bot_instance.app.bot.send_message(chat_id=chat_id, text=message)
        asyncio.create_task(coro)
        return f"Message sent to {chat_id}"
    except Exception as e:
        return f"Error sending message: {e}"