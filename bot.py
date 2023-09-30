import os

import telethon.types
from telegram import Update
from telegram.ext import filters, ApplicationBuilder, CommandHandler, MessageHandler
from telegram.ext import ContextTypes
from telethon import TelegramClient
from telethon.tl.custom.dialog import Dialog

from datetime import datetime
from enum import StrEnum, auto
import logging

import persistence
from persistence import create_db, UserManager

logging.basicConfig(level=logging.ERROR)


class CommandType(StrEnum):
    CLEAN_DB = auto()
    IMPORT = auto()
    INVITE = auto()
    INVITE_FORCED = auto()
    NO_OP = auto()
    SIGNIN = auto()
    SIGN_OUT = auto()
    STAT = auto()


class Service:

    def __init__(self, args: tuple[list[int], int, str, str, str]):
        self.cmd_list = """Click a command:
        /help - shows command list
        
        ☢️CRITICAL/SECURITY ☢️: 
        /clean_db - reset database
        /disconnect - close the current connection
        /sign_out - logout the client 
        
        🤑UTILS 💸:
        /clean_cache - remove all stats files
        /import - imports all users from a public group
        /invite - invites N users not invited yet from X to Y
        /inviteForced - invites N users also already invited from X to Y
        /list_chats - shows all the chats joined and their IDs
        /send_code - send code to Telegram for login
        /signin - login with Telegram auth code
        /stat - downloads a stats file until the given date
                """

        self.last_cmd: CommandType = CommandType.NO_OP

        self.admins, api_id, api_hash, bot_token, self.phone = args
        self.client: TelegramClient = TelegramClient('referral_bot', api_id, api_hash).start()
        self.app = ApplicationBuilder().token(bot_token).build()
        self.app.add_handler(CommandHandler("clean_cache", self._clean_cache))
        self.app.add_handler(CommandHandler("clean_db", self._clean_db))
        self.app.add_handler(CommandHandler("disconnect", self._disconnect))
        self.app.add_handler(CommandHandler("start", self._start))
        self.app.add_handler(CommandHandler("help", self._help))
        self.app.add_handler(CommandHandler("import", self._import_users))
        self.app.add_handler(CommandHandler("invite", self._invite))
        self.app.add_handler(CommandHandler("list_chats", self._list_chats))
        self.app.add_handler(CommandHandler("signin", self._signin))
        self.app.add_handler(CommandHandler("send_code", self._send_code))
        self.app.add_handler(CommandHandler("sign_out", self._sign_out))
        self.app.add_handler(CommandHandler("stat", self._stat))
        self.app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self._text))

    def run(self):
        self.app.run_polling()

    async def _clean_cache(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            for file in os.listdir("/stats"):
                os.remove(os.path.join("/stats", file))
            await update.message.reply_text("Stats files deleted")
        except OSError as err:
            await update.message.reply_text(f"{err}")
        self.last_cmd = CommandType.NO_OP

    async def _clean_db(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text("Are you sure you want cleanup the database? (yes/no)")
        self.last_cmd = CommandType.CLEAN_DB

    async def _disconnect(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if (res := await self._is_client_active()) is not None:
            await update.message.reply_text(res)
            self.last_cmd = CommandType.NO_OP
        else:
            await self.client.disconnect()
            await update.message.reply_text("Client disconnected.")
            self.last_cmd = CommandType.NO_OP

    async def _help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(f'{self.cmd_list}')
        self.last_cmd = CommandType.NO_OP

    async def _import_users(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._check_conn()
        await update.message.reply_text('From which public source group you want import? ')
        self.last_cmd = CommandType.IMPORT

    async def _invite(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._check_conn()
        await update.message.reply_text('Specify source and destination group names separated by , (e.g: home,hotel)')
        self.last_cmd = CommandType.INVITE

    async def _invite_forced(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._check_conn()
        await update.message.reply_text('Specify source and destination group names separated by , (e.g: home,hotel)')
        self.last_cmd = CommandType.INVITE_FORCED

    async def _list_chats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Lists client chats formatted"""

        if (res := await self._is_client_active()) is not None:
            await update.message.reply_text(res)
            self.last_cmd = CommandType.NO_OP
            return

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

    async def _send_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if self.client.is_user_authorized():
            await update.message.reply_text("Already authorized. Ready to use the bot APIs.")
        else:
            await self.client.send_code_request(self.phone)
            await update.message.reply_text("Auth code sent. Use /signin to login.")
        self.last_cmd = CommandType.NO_OP

    async def _signin(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(f'Please paste the auth code received on {self.phone}')
        self.last_cmd = CommandType.SIGNIN

    async def _sign_out(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if (res := await self._is_client_active()) is not None:
            await update.message.reply_text(res)
            self.last_cmd = CommandType.NO_OP
        else:
            await update.message.reply_text("Are you sure you want log out? (yes/no) ")
            self.last_cmd = CommandType.SIGN_OUT

    async def _start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Bot entry point. Allowed only to admins."""
        if update.effective_user.id not in self.admins:
            await update.message.reply_text(
                f"Sorry {update.effective_user.first_name} you're not enabled for this service.")
            return

        await create_db()

        message: str = f'Hello {update.effective_user.first_name}!'
        if not await self.client.is_user_authorized():
            _ = await self.client.send_code_request(self.phone)
            await update.message.reply_text(f'{message}. Auth code sent.\n'
                                            f'Call /signin command to login.')
        else:
            await self._check_conn()
            await update.message.reply_text(f'{message}. Please select a command:\n{self.cmd_list}')

    async def _stat(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if (res := await self._is_client_active()) is not None:
            await update.message.reply_text(res)
            self.last_cmd = CommandType.NO_OP
        else:
            await update.message.reply_text('From which date you want statistics? (DD-MM-YYYY). \'today\' for all.')
            self.last_cmd = CommandType.STAT

    async def _text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Text handler based on the last command"""

        response: str = ""
        message_text = update.message.text
        if message_text == "" or message_text is None:
            await update.message.reply_text("Message text empty.")
            return

        match self.last_cmd:
            case CommandType.CLEAN_DB:
                mess_to_lower = message_text.lower()
                match mess_to_lower:
                    case "yes":
                        await UserManager.delete_all()
                        response = "Database data burned. DB structure is still saved."
                        self.last_cmd = CommandType.NO_OP
                    case "no":
                        response = "Operation cancelled. Your database integrity is save."
                        self.last_cmd = CommandType.NO_OP
                    case _:
                        response = "Answer not accepted. Accepted: (yes/no). Please try again."
            case CommandType.IMPORT:
                await context.bot.send_message(chat_id=update.effective_chat.id,
                                               text=f'Try importing users from {message_text}...')
                group_name = await self._search_dialog(message_text)
                if group_name is None:
                    response = f'Group {message_text} not found in groups.'
                else:
                    user: telethon.types.User
                    users_count: int = 0
                    async for user in self.client.iter_participants(group_name):
                        if user.is_self:
                            continue
                        read_id = await UserManager.create(user.id, user.username)
                        if read_id > 0:
                            users_count += 1

                    response = f'Successfully imported {users_count} users from group {message_text}.'
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
                                                       text=f'Try inviting users from {source} to {destination}...')
                        # invite users

                        response = f'Successfully invite {1000} users from group {message_text}.'
            case CommandType.NO_OP:
                response = f"Cannot accept text messages for command {self.last_cmd.name}."
            case CommandType.STAT:
                dt: datetime = datetime.now()
                try:
                    if message_text != "today":
                        from dateutil import parser
                        dt = parser.parse(message_text)
                        if dt > datetime.now():
                            raise ValueError()

                    import aiofiles
                    path: str = f"./stats/stat_{datetime.now()}.txt"
                    async with aiofiles.open(path, mode="w") as file:
                        await file.write(f"Statistics until {dt}:\n\n")
                        await file.write("id | username | created_at | invited_at")
                        user_info: persistence.User
                        async for user_info in UserManager.read_all_full_info(dt):
                            await file.write(f"{user_info.telegram_id} | {user_info.username} | "
                                             f"{user_info.created_at} | {user_info.invited_at}\n")

                    await self.client.send_file(update.message.from_user.id, path)
                    response = f"Downloading stat file... :"
                    self.last_cmd = CommandType.NO_OP
                except (OverflowError, ValueError) as err:
                    response = f'{err}\nWrong date string format or limit! Retry.'
                except FileNotFoundError as err:
                    response = f"{err}"
            case CommandType.SIGNIN:
                result = await self.client.sign_in(self.phone, message_text)
                if type(result) is telethon.types.User:
                    response = f"User signed in correctly.\n\n{self.cmd_list}"
                    self.last_cmd = CommandType.NO_OP
                else:
                    response = f'\nWrong auth code format! Retry.'
            case CommandType.SIGN_OUT:
                mess_to_lower = message_text.lower()
                match mess_to_lower:
                    case "yes":
                        response = ("Client successfully logged out. "
                                    "To use again the APIs please use /send_code and then /signin") \
                            if await self.client.log_out() else "INTERNAL SERVER ERROR: could not log out correctly!"
                        self.last_cmd = CommandType.NO_OP
                    case "no":
                        response = "Operation cancelled. You're still authorized."
                        self.last_cmd = CommandType.NO_OP
                    case _:
                        response = "Answer not accepted. Accepted: (yes/no). Please try again."

        await update.message.reply_text(response)

    async def _check_conn(self) -> str | None:
        """Returns `str` if the connection fails, else `None`"""

        if not self.client.is_connected():
            try:
                await self.client.connect()
            except OSError as os_error:
                return f"Failed to connect to telegram client {os_error}"

    async def _is_client_active(self) -> str | None:
        """Returns `str` if the user is not authorized or the connection fails, else `None`"""

        if not await self.client.is_user_authorized():
            return "User not authorized. Please use /send_"
        if (res := await self._check_conn()) is not None:
            return res

    async def _search_dialog(self, message_text: str) -> str | None:
        """Returns `str` if the user's chats contain `message_str`, else `None` """

        group_name: str
        dialog: Dialog
        async for dialog in self.client.iter_dialogs():
            if dialog.name == message_text:
                return dialog.name
        else:
            return None
