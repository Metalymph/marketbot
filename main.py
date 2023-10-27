import logging
import sys
from service import Service, Config

logging.basicConfig(level=logging.INFO)


def load_env() -> Config:
    """Loads the secret info from the environment and parse them"""

    from dotenv import load_dotenv
    import os

    load_dotenv()

    admins_str: str = os.getenv('ADMINS')
    bot_token = os.getenv('SERVER_BOT_TOKEN')
    api_id = os.getenv('API_ID')
    api_hash = os.getenv('API_HASH')
    phone = os.getenv('PHONE')

    critical_message: str = ""
    if admins_str is None:
        critical_message = "ADMINS env variable is none"
    if api_id is None:
        critical_message = "API_ID env variable is none"
    if api_hash is None:
        critical_message = "API_HASH env variable is none"
    if bot_token is None:
        critical_message = "SERVER_BOT_TOKEN env variable is none"
    if phone is None:
        critical_message = "PHONE env variable is none."

    if critical_message != "":
        raise Exception(critical_message)
    logging.info("Environment variables read.")

    admins: list[int]
    try:
        admins = [int(user_id) for user_id in admins_str.split(',')]
        api_id = int(api_id)
        if phone[0] != '+':
            raise ValueError(f"{phone} has not the right format")
        _ = int(phone[1:])
    except ValueError as verr:
        raise Exception(verr)
    logging.info("Environment load.")

    return Config(admins=admins, api_id=api_id, api_hash=api_hash, bot_token=str(bot_token), phone=phone)


# if __name__ == '__main__':
def main():
    Service(load_env()).run()


main()
