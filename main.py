from telegram.ext import filters, ApplicationBuilder, CommandHandler, MessageHandler
from commands import Commands

# if __name__ == '__main__':
app = ApplicationBuilder().token("6628334529:AAHnF51Tp6NVMjDRahRFkhCJGl8phsL8CZ8").build()
app.add_handler(CommandHandler("start", Commands.start))
app.add_handler(CommandHandler("help", Commands.help))
app.add_handler(CommandHandler("import", Commands.import_start))
app.add_handler(CommandHandler("stop", Commands.import_stop))
app.add_handler(CommandHandler("stat", Commands.stat))
app.add_handler(CommandHandler("link", Commands.get_post_link))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), Commands.text))
app.run_polling()
