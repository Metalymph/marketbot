from telegram.ext import ApplicationBuilder, CommandHandler
from commands import Commands


# change token for the bot and change start to hello
app = ApplicationBuilder().token("6628334529:AAHnF51Tp6NVMjDRahRFkhCJGl8phsL8CZ8").build()
app.add_handler(CommandHandler("hello", Commands.hello))
app.add_handler(CommandHandler("add", Commands.add_key))
app.add_handler(CommandHandler("del", Commands.del_key))
app.add_handler(CommandHandler("list", Commands.list_keys))
app.add_handler(CommandHandler("stat", Commands.stat))
app.add_handler(CommandHandler("link", Commands.build_post_from_link))
app.run_polling()
