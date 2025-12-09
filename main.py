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

# Register handlers
register_handlers(dp)

# FastAPI App
app = FastAPI()

# ---- Run Bot Polling as background task ----
async def start_bot():
    await dp.start_polling(bot)

@app.on_event("startup")
async def startup_event():
    print("🚀 Starting Polling...")
    asyncio.create_task(start_bot())
    print("Bot started successfully!")

# ---- DO NOT CLOSE bot or session ----
@app.on_event("shutdown")
async def shutdown_event():
    print("⚠️ Render triggered shutdown — ignoring bot close.")

@app.get("/")
async def root():
    return {"status": "Bot is running on Render!"}

@app.get("/health")
def health():
    return {"status": "ok"}
