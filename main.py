from fastapi import FastAPI
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from bot import register_handlers
from dotenv import load_dotenv
import os
import aiohttp


# Load .env
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Init bot
bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=MemoryStorage())
register_handlers(dp)

# FastAPI
app = FastAPI()


# --- Aiogram Polling ---
async def start_bot():
    await dp.start_polling(bot)


# --- KEEP RENDER ALIVE ---
async def keep_alive():
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                await session.get("https://just-confess.onrender.com/health")
                print("💙 KeepAlive Ping Sent")
        except Exception as e:
            print("KeepAlive Error:", e)

        await asyncio.sleep(240)  # Every 4 minutes


@app.on_event("startup")
async def startup_event():
    print("🚀 Starting Polling...")
    asyncio.create_task(start_bot())
    asyncio.create_task(keep_alive())
    print("Bot started successfully!")


@app.get("/")
async def root():
    return {"status": "Bot is running on Render!"}


@app.get("/health")
def health():
    return {"status": "ok"}
