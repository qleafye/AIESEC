import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import config
from database.db import init_db
from handlers import registration, user_actions, admin
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

async def main():
    logging.basicConfig(level=logging.INFO)
    
    # Init DB
    await init_db()
    
    bot = Bot(token=config.BOT_TOKEN.get_secret_value())
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    dp = Dispatcher(storage=MemoryStorage())
    
    # Register routers
    dp.include_router(admin.router) # Admin first to intercept commands
    dp.include_router(registration.router)
    dp.include_router(user_actions.router)
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
