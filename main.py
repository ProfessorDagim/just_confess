from fastapi import FastAPI
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from bot import register_handlers
from dotenv import load_dotenv
import os

# Load env variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Initialize Bot & Dispatcher
bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Register all message handlers
register_handlers(dp)

# FastAPI App
app = FastAPI()

# Background task holder
polling_task = None

@app.on_event("startup")
async def startup_event():
    global polling_task
    print("🚀 Starting Polling...")
    polling_task = asyncio.create_task(dp.start_polling())
    print("Bot polling started successfully!")

@app.on_event("shutdown")
async def shutdown_event():
    global polling_task
    print("🛑 Stopping Polling...")
    if polling_task:
        polling_task.cancel()
    await bot.session.close()

@app.get("/")
async def root():
    return {"status": "Bot is running on Render!"}

@app.get("/health")
def health():
    return {"status": "ok"}
