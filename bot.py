import telethon.types
from telegram import Update
from telegram.ext import filters, ApplicationBuilder, CommandHandler, MessageHandler
from telegram.ext import ContextTypes
from telethon import TelegramClient
from telethon.tl.custom.dialog import Dialog

from enum import StrEnum, auto
import logging
from persistence import create_db, UserManager

logging.basicConfig(level=logging.ERROR)


class CommandType(StrEnum):
    IMPORT = auto()
    INVITE = auto()
    INVITE_FORCED = auto()
    NO_OP = auto()
    SIGNIN = auto()
    STAT = auto()


class Service:

    def __init__(self, args: tuple[list[int], int, str, str, str]):
        self.cmd_list = """Click a command:
        /help - shows command list
        /import - imports all users from a public group
        /invite - invites N users not invited yet from X to Y
        /inviteForced - invites N users also already invited from X to Y
        /list_chats - shows all the chats joined and their IDs
        /signin - login with Telegram auth code
        /stat - shows stats from a date to now
                """

        self.last_cmd: CommandType = CommandType.NO_OP

        self.admins, api_id, api_hash, bot_token, self.phone = args
        self.client: TelegramClient = TelegramClient('referral_bot', api_id, api_hash).start()

        self.app = ApplicationBuilder().token(bot_token).build()
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("help", self.help))
        self.app.add_handler(CommandHandler("import", self.import_users))
        self.app.add_handler(CommandHandler("invite", self.invite))
        self.app.add_handler(CommandHandler("list_chats", self.list_chats))
        self.app.add_handler(CommandHandler("stat", self.stat))
        self.app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self.text))

    def run(self):
        self.app.run_polling()

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Bot entry point. Allowed only to admins."""
        if update.effective_user.id not in self.admins:
            await update.message.reply_text(
                f"Sorry {update.effective_user.first_name} you're not enabled for this service.")
            return

        await create_db()

        message: str = f'Hello {update.effective_user.first_name}!'
        if await self.client.is_user_authorized():
            _ = await self.client.send_code_request(self.phone)
            await update.message.reply_text(f'{message}. Auth code sent.\n'
                                            f'Call /signin command to login.')
        else:
            await self.check_conn()
            await update.message.reply_text(f'{message}. Please select a command:\n{self.cmd_list}')

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(f'{self.cmd_list}')
        self.last_cmd = CommandType.NO_OP

    async def import_users(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self.check_conn()
        await update.message.reply_text('From which public source group you want import? ')
        self.last_cmd = CommandType.IMPORT

    async def invite(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self.check_conn()
        await update.message.reply_text('Specify source and destination group names separated by , (e.g: home,hotel)')
        self.last_cmd = CommandType.INVITE

    async def invite_forced(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self.check_conn()
        await update.message.reply_text('Specify source and destination group names separated by , (e.g: home,hotel)')
        self.last_cmd = CommandType.INVITE_FORCED

    async def list_chats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Lists client chats formatted"""
        await self.check_conn()

        groups: list[str] = []
        channels: list[str] = []
        user_chats: list[str] = []
        dialog: Dialog
        async for dialog in self.client.iter_dialogs():
            if dialog.is_group:
                groups.append(f"{dialog.name}: {dialog.id})")
            elif dialog.is_channel:
                groups.append(f"{dialog.name}, {dialog.id}")
            else:
                user_chats.append(f"{dialog.name}, {dialog.id}")

        groups_fmt = "\n".join(groups)
        channels_fmt = "\n".join(channels)
        user_chats_fmt = "\n".join(user_chats)

        response = (f'*Client info*:\n**Groups**:\n{groups_fmt}\n\n'
                    f'**Channels**:\n{channels_fmt}\n\n'
                    f'**Private chats**:{user_chats_fmt}')
        await update.message.reply_text(response)
        self.last_cmd = CommandType.NO_OP

    async def send_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if self.client.is_user_authorized():
            await update.message.reply_text("Already authorized. Ready to use the bot APIs.")
        else:
            await self.client.send_code_request(self.phone)
            await update.message.reply_text("Auth code sent. Use /signin to login.")
        self.last_cmd = CommandType.NO_OP

    async def signin(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(f'Please paste the auth code received on {self.phone}')
        self.last_cmd = CommandType.SIGNIN

    async def stat(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text('From which date you want statistics? (DD-MM-YYYY)')
        self.last_cmd = CommandType.STAT

    async def text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Text handler based on the last command"""

        response: str = ""
        message_text = update.message.text
        if message_text == "" or message_text is None:
            await update.message.reply_text("Message text empty.")
            return

        match self.last_cmd:
            case CommandType.IMPORT:
                await context.bot.send_message(chat_id=update.effective_chat.id,
                                               text=f'Try importing users from {message_text}.')
                print(message_text)
                group_name = await self._search_dialog(message_text)
                if group_name is None:
                    response = f'Group {message_text} not found in groups.'
                else:
                    # import into db
                    async for user in self.client.iter_participants(group_name):
                        await UserManager.create(user.telegram_id)

                    response = f'Successfully imported {1000} users from group {message_text}.'
            case CommandType.INVITE | CommandType.INVITE_FORCED:
                try:
                    (source, destination) = message_text.split(',')
                except ValueError as verr:
                    response = f'{verr}.\nRight format(2 elements): Source - Destination.'
                else:
                    group_name = await self._search_dialog(source)
                    if group_name is None:
                        response = f'Group {source} not found in groups.'
                    else:
                        await context.bot.send_message(chat_id=update.effective_chat.id,
                                                       text=f'Try inviting users from {source} to {destination}.')
                        # invite users

                        response = f'Successfully invite {1000} users from group {message_text}.'
            case CommandType.NO_OP:
                response = f"Cannot accept text messages for {self.last_cmd.name}."
            case CommandType.STAT:
                try:
                    from dateutil import parser
                    dt = parser.parse(message_text)
                    # read data from db basing on from dt to now
                    response = f"Statistics from {dt}:\n"
                    self.last_cmd = CommandType.NO_OP
                except (OverflowError, ValueError) as err:
                    response = f'{err}\nWrong date string format! Retry.'
            case CommandType.SIGNIN:
                result = await self.client.sign_in(self.phone, message_text)
                if type(result) is telethon.types.User:
                    response = f"User signed in correctly.\n\n{self.cmd_list}"
                    self.last_cmd = CommandType.NO_OP
                else:
                    response = f'\nWrong auth code format! Retry.'

        await update.message.reply_text(response)

    async def check_conn(self):
        if not self.client.is_connected():
            try:
                await self.client.connect()
            except OSError as os_error:
                raise RuntimeError(f"Failed to connect to telegram client {os_error}")

    async def request_code(self) -> telethon.types.auth.SentCode | None:
        """Request an auth code from Telegram for the client if not authorized"""

        if await self.client.is_user_authorized():
            return None
        code = await self.client.send_code_request(self.phone)
        return code

    async def _search_dialog(self, message_text: str) -> str | None:
        """Util to search if a dialog is in the user dialog list"""

        group_name: str
        dialog: Dialog
        async for dialog in self.client.iter_dialogs():
            if dialog.name == message_text:
                return dialog.name
        else:
            return None
