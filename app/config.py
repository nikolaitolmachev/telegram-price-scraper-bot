"""Read application configuration from the environment and a local .env file.

Existing environment variables take precedence over values in .env.
Importing this module raises RuntimeError when BOT_TOKEN is missing or empty.
"""

import os

from dotenv import load_dotenv

load_dotenv()


BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
