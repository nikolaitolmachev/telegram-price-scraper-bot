"""Bot entry point: build the dispatcher and start long polling."""

import asyncio

from aiogram import Bot, Dispatcher

from app.bot.handlers import router
from app.config import BOT_TOKEN


async def main() -> None:
    """Create the dispatcher, register handlers and start long polling."""
    bot = Bot(token=BOT_TOKEN)
    dispatcher = Dispatcher()

    dispatcher.include_router(router)

    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
