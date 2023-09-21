from telegram import Update
from telegram.ext import ContextTypes

from enum import StrEnum, auto
from urllib.parse import urlparse


class CommandType(StrEnum):
    HELP = auto()
    IMPORT_START = auto()
    IMPORT_STOP = auto()
    LINK = auto()
    STAT = auto()


class Commands:
    cmd_list = """
/help - command list
/import - starts importing
/link - generate a post-link
/stop - brake the import phase
/stat - shows stats from a date to now
    """

    last_cmd: CommandType = CommandType.HELP

    @classmethod
    async def start(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_user.id not in [44870326, 64513378]:
            await update.message.reply_text(
                f"Sorry {update.effective_user.first_name} you're not enabled for this service.")
            return
        await update.message.reply_text(
            f'Hello {update.effective_user.first_name}! Please select a command:\n{cls.cmd_list}')

    @classmethod
    async def help(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(f'{cls.cmd_list}')
        cls.last_cmd = CommandType.HELP

    @classmethod
    async def import_start(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text('Import process start...?')
        cls.last_cmd = CommandType.IMPORT_START

    @classmethod
    async def import_stop(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text('Import process stop...')
        cls.last_cmd = CommandType.IMPORT_STOP

    @classmethod
    async def stat(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text('From which date you want statistics? (DD-MM-YYYY)')
        cls.last_cmd = CommandType.STAT

    @classmethod
    async def get_post_link(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text("Please, post the link you want to refactor.")
        cls.last_cmd = CommandType.LINK

    @classmethod
    async def text(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # await context.bot.send_message(chat_id=update.effective_chat.id, text=update.message.text)
        response: str = ""
        message_text = update.message.text
        if message_text == "" or message_text is None:
            await update.message.reply_text("Message text empty.")
            return

        match cls.last_cmd:
            case CommandType.STAT:
                try:
                    from dateutil import parser
                    dt = parser.parse(message_text)
                    # read data from db basing on from dt to now
                    response = f"Statistics from {dt}:\n"
                    cls.last_cmd = CommandType.HELP
                except (OverflowError, ValueError) as err:
                    response = f'{err}\nWrong date string format! Retry.'
            case CommandType.LINK:
                try:
                    parsed_url = urlparse(message_text)
                    if all([parsed_url.scheme, parsed_url.netloc]):
                        # Write message format
                        response = post_link_builder(message_text)
                        cls.last_cmd = CommandType.HELP
                    else:
                        response = "Problem while parsing URL internal components. Retry."
                except ValueError as verr:
                    response = f"{verr}\nWrong URL format! Retry."
            case CommandType.HELP | CommandType.IMPORT_START | CommandType.IMPORT_STOP:
                response = "Cannot accept text messages without a previous explicit allowed command (stat, link)"

        await update.message.reply_text(response)


def post_link_builder(link: str) -> str:
    """Build a post from a given promo link"""
    post = "Post"
    return post
