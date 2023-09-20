from telegram import Update
from telegram.ext import ContextTypes
from enum import StrEnum, auto


class CommandType(StrEnum):
    HELP = auto()
    ADD = auto()
    DEL = auto()
    LIST = auto()
    LINK = auto()
    STAT = auto()


class KeyManager:
    def __init__(self):
        # caricare dal db
        self.keys: set[str] = set()

    def add(self, key: str) -> None:
        self.keys.add(key)

    def remove(self, key: str) -> None:
        self.keys.add(key)

    def __str__(self):
        sorted_keys = list(self.keys)
        sorted_keys.sort()
        formatted_list = "\n".join(sorted_keys)
        return formatted_list


class Commands:
    cmd_list = """
    /help - command list
    /add - add a research key
    /del - remove a research key
    /list - show keys list
    /stat - shows stats from a date to now
    """

    last_cmd: CommandType = CommandType.HELP
    km = KeyManager()

    @classmethod
    async def hello(cls, update: Update) -> None:
        # insert also fabrizio ID
        if update.effective_user.id not in [44870326]:
            await update.message.reply_text(
                f"Sorry {update.effective_user.first_name} you're not enabled for this service.")
            return
        await update.message.reply_text(
            f'Hello {update.effective_user.first_name}! Please select a command:\n{cls.cmd_list}')

    @classmethod
    async def add_key(cls, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(f'{cls.km}\nWhich keyword do you want insert?')
        cls.last_cmd = CommandType.ADD

    @classmethod
    async def del_key(cls, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(f'{cls.km}\nWhich keyword do you want to delete?')
        cls.last_cmd = CommandType.DEL

    @classmethod
    async def list_keys(cls, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(f'{cls.km}')
        cls.last_cmd = CommandType.LIST

    @classmethod
    async def stat(cls, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(f'From which date you want statistics? (DD/MM/YYYY)')
        cls.last_cmd = CommandType.STAT

    @classmethod
    async def build_post_from_link(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text("Which keyword do you want insert?")
        cls.last_cmd = CommandType.LINK


def post_builder(link: str) -> str:
    post = ""
    return post
