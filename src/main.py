import asyncio

from aiogram import Bot, Dispatcher

from .config import CONFIG
from .db import init_db
from .handlers import router
from .logger import logger
from .scheduler import start as start_scheduler


async def main() -> None:
    init_db()
    start_scheduler()

    bot = Bot(token=CONFIG.bot_token)
    dp = Dispatcher()
    dp.include_router(router)
    logger.info("Starting bot")
    try:
        await dp.start_polling(bot)
    finally:
        logger.info("Shutting down bot")
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
