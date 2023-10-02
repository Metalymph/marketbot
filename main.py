import logging
import sys
from typing import Tuple
from service import Service

logging.basicConfig(level=logging.ERROR)


def load_env() -> Tuple[list[int], int, str, str, str]:
    """Loads the secret info from the environment and parse them"""

    from dotenv import load_dotenv
    import os

    load_dotenv()

    admins_str: str = os.getenv('ADMINS')
    api_id = os.getenv('TELEGRAM_API_ID')
    api_hash = os.getenv('TELEGRAM_API_HASH')
    bot_token = os.getenv('BOT_TOKEN')
    phone = os.getenv('PHONE')

    critical_message: str = ""
    if admins_str is None:
        critical_message = "ADMINS env variable is none"
    if api_id is None:
        critical_message = "API_ID env variable is none"
    if api_hash is None:
        critical_message = "API_HASH env variable is none"
    if bot_token is None:
        critical_message = "BOT_TOKEN env variable is none"
    if phone is None:
        critical_message = "PHONE env variable is none"

    if critical_message != "":
        logging.critical(critical_message)
        sys.exit(1)

    admins: list[int] = []
    try:
        admins = [int(user_id) for user_id in admins_str.split(',')]
    except ValueError as verr:
        logging.critical(f"{admins} format is not correct: {verr}")
        sys.exit(1)

    try:
        api_id = int(api_id)
        _ = int(phone[1:])
    except ValueError as verr:
        logging.critical(f"{verr}")
        sys.exit(1)

    if phone[0] != '+':
        logging.critical(f"{phone} has not the  right format")
        sys.exit(1)

    return admins, api_id, str(api_hash), str(bot_token), phone


# if __name__ == '__main__':
def main():
    s = Service(load_env())
    s.run()


main()
