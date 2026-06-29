from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters


class TelegramBot:
    def __init__(self, token: str, orch):
        self.orch = orch
        self.app = Application.builder().token(token).build()
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    async def cmd_start(self, update: Update, context):
        await update.message.reply_text(
            "Hello! I'm Cozmo, your local AI agent. Send me a message and I'll help."
        )

    async def cmd_help(self, update: Update, context):
        await update.message.reply_text(
            "Send me any question or task. I can search the web, read files, "
            "do calculations, and remember our conversations."
        )

    async def handle_message(self, update: Update, context):
        try:
            response = self.orch.run(update.message.text)
            await update.message.reply_text(response)
        except Exception as e:
            await update.message.reply_text(f"Error: {e}")

    def run(self):
        self.app.run_polling(allowed_updates=[])
