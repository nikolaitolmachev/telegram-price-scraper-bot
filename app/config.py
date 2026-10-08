"""Application configuration read from environment variables.

Importing this module raises RuntimeError when BOT_TOKEN is not set.
"""

import os

from dotenv import load_dotenv


load_dotenv()


BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
