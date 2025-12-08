from fastapi import FastAPI
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from bot import register_handlers
from dotenv import load_dotenv
import os

# Load env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Initialize bot & dispatcher
bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Register handlers from bot.py
register_handlers(dp)

app = FastAPI()

@app.on_event("startup")
async def on_startup():
    loop = asyncio.get_event_loop()
    loop.create_task(dp.start_polling())
    print("Bot polling started...")

@app.get("/")
async def root():
    return {"status": "Bot is running locally!"}
