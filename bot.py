import sqlite3
import html
import re
import logging
from datetime import datetime
from typing import Optional, List, Tuple

from aiogram import Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from dotenv import load_dotenv
import os

# -------------------- Load environment --------------------
load_dotenv()
BOT_LINK = os.getenv("BOT_LINK", "https://t.me/confess_ethiopia_bot")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_ID", "").split(",") if x]
CHANNEL_ID_RAW = os.getenv("CHANNEL_ID")
DB_PATH = os.getenv("DB_PATH", "confessions.db")

try:
    CHANNEL_ID = int(CHANNEL_ID_RAW)
except ValueError:
    CHANNEL_ID = CHANNEL_ID_RAW

# -------------------- Logging --------------------
logger = logging.getLogger(__name__)

# -------------------- DB Helpers --------------------
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS confessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                author_user_id INTEGER,
                text TEXT,
                timestamp TEXT,
                status TEXT DEFAULT 'pending',
                channel_message_id INTEGER
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                confession_id INTEGER,
                commenter_user_id INTEGER,
                text TEXT,
                timestamp TEXT
            )
        """)
        conn.commit()

def db_execute(query: str, params: tuple = (), fetch: bool = False):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(query, params)
        if fetch:
            return cur.fetchall()
        conn.commit()
        return cur.lastrowid

init_db()

# -------------------- Moderation --------------------
BAD_WORDS = ["fano", "badword2", "hateword"]
PHONE_EMAIL_REGEX = re.compile(r"(\+?\d[\d\s\-()]{6,}\d)|([\w.\-+]+@[\w.\-]+\.[a-zA-Z]{2,6})")

def moderate_text(text: str) -> Optional[str]:
    if text is None:
        return None
    t = text.strip()
    if not t:
        return None
    if PHONE_EMAIL_REGEX.search(t):
        return None
    for w in BAD_WORDS:
        if w in t.lower():
            return None
    return html.escape(t)

# -------------------- States --------------------
class ConfessStates(StatesGroup):
    waiting_for_confession = State()

class CommentStates(StatesGroup):
    waiting_for_comment = State()

# -------------------- Utilities --------------------
def human_ts(iso_ts: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_ts)
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return iso_ts

COMMENTS_PER_PAGE = 5

def fetch_comments(confession_id: int, page: int = 0) -> List[Tuple[int, str, str]]:
    offset = page * COMMENTS_PER_PAGE
    rows = db_execute(
        "SELECT id, text, timestamp FROM comments WHERE confession_id=? ORDER BY id ASC LIMIT ? OFFSET ?",
        (confession_id, COMMENTS_PER_PAGE, offset),
        fetch=True
    )
    return rows or []

def get_confession(confession_id: int) -> Optional[Tuple]:
    rows = db_execute(
        "SELECT id, author_user_id, text, timestamp, status, channel_message_id FROM confessions WHERE id=?",
        (confession_id,),
        fetch=True
    )
    return rows[0] if rows else None

def list_pending_confessions(limit: int = 50) -> List[Tuple]:
    rows = db_execute(
        "SELECT id, text, timestamp, author_user_id FROM confessions WHERE status='pending' ORDER BY id ASC LIMIT ?",
        (limit,),
        fetch=True
    )
    return rows or []

# -------------------- Keyboards --------------------
def main_reply_keyboard() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("/confess")
    return kb

def build_admin_moderation_kb(confession_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve:{confession_id}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject:{confession_id}")
    )
    return kb

def build_channel_confession_kb(confession_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✍️ Add Comment", url=f"{BOT_LINK}?start=confession_{confession_id}"),
        InlineKeyboardButton("👀 View Comments", url=f"{BOT_LINK}?start=confession_{confession_id}")
    )
    return kb

def build_inbot_add_view_kb(confession_id: int, page: int = 0) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✍️ Add Comment (Anonymous)", callback_data=f"add_comment:{confession_id}"),
        InlineKeyboardButton("👀 View Comments", callback_data=f"view_comments:{confession_id}:{page}")
    )
    return kb

def build_view_pagination_kb(confession_id: int, page: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=3)
    if page > 0:
        kb.insert(InlineKeyboardButton("⬅️ Prev", callback_data=f"view_comments:{confession_id}:{page-1}"))
    kb.insert(InlineKeyboardButton("✍️ Add Comment", callback_data=f"add_comment:{confession_id}"))
    next_rows = fetch_comments(confession_id, page + 1)
    if next_rows:
        kb.insert(InlineKeyboardButton("Next ➡️", callback_data=f"view_comments:{confession_id}:{page+1}"))
    return kb

# -------------------- Handlers --------------------
def register_handlers(dp: Dispatcher):

    # ---------- /start ----------
    @dp.message_handler(commands=["start", "help"])
    async def cmd_start(message: types.Message):
        args = message.get_args() or ""
        if args.startswith("confession_"):
            try:
                cid = int(args.split("_", 1)[1])
                conf = get_confession(cid)
                if conf is None or conf[4] != "approved":
                    await message.answer("Confession not found or not approved yet.", reply_markup=main_reply_keyboard())
                    return
                await message.answer(
                    f"You opened anonymous menu for ኑዛዜ <b>#{cid}</b>.",
                    reply_markup=build_inbot_add_view_kb(cid)
                )
                return
            except Exception:
                pass
        text = (
            "👋 Welcome to the Anonymous Confession Bot!\n\n"
            "Here, you can share your thoughts anonymously and read comments from others.\n"
            "All submissions are reviewed by admins before being posted publicly.\n\n"
            "Start sending your confession here: /confess"
        )
        await message.answer(text, reply_markup=main_reply_keyboard())

    # ---------- /confess ----------
    @dp.message_handler(commands=["confess"])
    async def initiate_confession(message: types.Message):
        await message.answer(
            "Please send your confession text. It will be reviewed by an admin before posting.\n\n"
            "(Do not include phone numbers, emails or personal contact info.)"
        )
        await ConfessStates.waiting_for_confession.set()

    @dp.message_handler(state=ConfessStates.waiting_for_confession, content_types=types.ContentTypes.TEXT)
    async def receive_confession(message: types.Message, state: FSMContext):
        sanitized = moderate_text(message.text)
        if sanitized is None:
            await message.answer("Your message was rejected by our safety filters. Modify and try again.")
            await state.finish()
            return

        timestamp = datetime.utcnow().isoformat()
        confession_id = db_execute(
            "INSERT INTO confessions (author_user_id, text, timestamp, status) VALUES (?, ?, ?, 'pending')",
            (message.from_user.id, sanitized, timestamp)
        )

        preview = f"🆕 <b>New Confession</b>\nID: {confession_id}\n\n{sanitized}\n\nFrom user: <code>{message.from_user.id}</code>"
        await send_admin_notification(message.bot, preview, reply_markup=build_admin_moderation_kb(confession_id))
        await message.answer("Thanks — your confession was submitted and will be reviewed by an admin. You will not be publicly identified.")
        await state.finish()

    # ---------- /view_confession ----------
    @dp.message_handler(commands=["view_confession"])
    async def cmd_view_confession(message: types.Message):
        args = message.get_args().strip()
        if not args:
            await message.answer("Usage: /view_confession <confession_id>")
            return
        try:
            cid = int(args.split()[0])
        except ValueError:
            await message.answer("Invalid confession id.")
            return
        conf = get_confession(cid)
        if conf is None:
            await message.answer("Confession not found.")
            return
        if conf[4] != "approved":
            await message.answer("This confession is not publicly posted (not approved).")
            return
        await message.answer(f"Anonymous menu for confession <b>#{cid}</b>.", reply_markup=build_inbot_add_view_kb(cid))

    # ---------- /list_pending ----------
    @dp.message_handler(commands=["list_pending"])
    async def cmd_list_pending(message: types.Message):
        if message.from_user.id not in ADMIN_IDS:
            await message.answer("Only admins may use this command.")
            return
        rows = list_pending_confessions(100)
        if not rows:
            await message.answer("No pending confessions.")
            return
        parts = []
        for r in rows:
            cid, text, ts, author = r
            short = (text[:120] + "...") if len(text) > 120 else text
            parts.append(f"#{cid} — {short}\nFrom: <code>{author}</code>\n{human_ts(ts)}\n")
        msg = "<b>Pending confessions:</b>\n\n" + "\n".join(parts)
        await message.answer(msg)

    # ---------- Admin moderation ----------
    @dp.callback_query_handler(lambda c: c.data and c.data.startswith("admin_"))
    async def admin_moderation_handler(callback_query: types.CallbackQuery):
        data = callback_query.data
        try:
            action, raw_id = data.split(":", 1)
            confession_id = int(raw_id)
        except Exception:
            await callback_query.answer("Invalid callback data")
            return

        if callback_query.from_user.id not in ADMIN_IDS:
            await callback_query.answer("Only admins may perform that action", show_alert=True)
            return

        if action == "admin_approve":
            db_execute("UPDATE confessions SET status='approved' WHERE id=?", (confession_id,))
            rows = db_execute("SELECT text FROM confessions WHERE id=?", (confession_id,), fetch=True)
            if not rows:
                await callback_query.answer("Confession not found")
                return
            text = rows[0][0]
            try:
                posted = await callback_query.bot.send_message(
                    CHANNEL_ID,
                    f"<b>ኑዛዜ#{confession_id}</b>\n\n💬 Anonymous Confession:\n\n{text}",
                    reply_markup=build_channel_confession_kb(confession_id)
                )
                db_execute("UPDATE confessions SET channel_message_id=? WHERE id=?", (posted.message_id, confession_id))
                await callback_query.answer("Approved and posted to channel")
                await callback_query.bot.send_message(callback_query.from_user.id, f"ኑዛዜ #{confession_id} approved and posted.")
            except Exception as e:
                logger.exception("Failed posting confession to channel: %s", e)
                await callback_query.answer("Approved but failed to post to channel (see admin).")
                await callback_query.bot.send_message(callback_query.from_user.id, f"ኑዛዜ #{confession_id} marked approved but failed to post to channel: {e}")
        elif action == "admin_reject":
            db_execute("UPDATE confessions SET status='rejected' WHERE id=?", (confession_id,))
            await callback_query.answer("Rejected")
            await callback_query.bot.send_message(callback_query.from_user.id, f"ኑዛዜ #{confession_id} has been rejected.")
        else:
            await callback_query.answer("Unknown admin action")

    # ---------- Add/View comments ----------
    @dp.callback_query_handler(lambda c: c.data and c.data.startswith("add_comment:"))
    async def add_comment_callback(callback_query: types.CallbackQuery):
        try:
            _, raw_id = callback_query.data.split(":", 1)
            confession_id = int(raw_id)
        except Exception:
            await callback_query.answer("Invalid callback")
            return

        conf = get_confession(confession_id)
        if conf is None or conf[4] != "approved":
            await callback_query.answer("Confession not available", show_alert=True)
            return

        try:
            await callback_query.bot.send_message(callback_query.from_user.id, f"Send your anonymous comment for ኑዛዜ <b>#{confession_id}</b>:\n\n(Do not include phone numbers or emails.)")
        except Exception:
            start_link = f"{BOT_LINK}?start=confession_{confession_id}"
            await callback_query.answer("Please start the bot in private chat first: " + start_link, show_alert=True)
            return

        state = dp.current_state(user=callback_query.from_user.id)
        await state.update_data(confession_for_comment=confession_id)
        await CommentStates.waiting_for_comment.set()
        await callback_query.answer()

    @dp.message_handler(state=CommentStates.waiting_for_comment, content_types=types.ContentTypes.TEXT)
    async def receive_comment(message: types.Message, state: FSMContext):
        data = await state.get_data()
        confession_id = data.get("confession_for_comment")
        if confession_id is None:
            await message.answer("No confession selected. Use the Add Comment button from a confession post.")
            await state.finish()
            return

        sanitized = moderate_text(message.text)
        if sanitized is None:
            await message.answer("Your comment was rejected by safety filters. Modify and try again.")
            await state.finish()
            return

        timestamp = datetime.utcnow().isoformat()
        comment_id = db_execute(
            "INSERT INTO comments (confession_id, commenter_user_id, text, timestamp) VALUES (?, ?, ?, ?)",
            (confession_id, message.from_user.id, sanitized, timestamp)
        )

        await message.answer("Your comment was submitted anonymously. Thank you.")

        admin_text = f"📝 New comment on ኑዛዜ #{confession_id}\n\n{sanitized}\n\nFrom user: <code>{message.from_user.id}</code>\nComment id: {comment_id}"
        await send_admin_notification(message.bot, admin_text)

        logger.info(f"Anonymous comment stored for confession #{confession_id}")
        await state.finish()

    @dp.callback_query_handler(lambda c: c.data and c.data.startswith("view_comments:"))
    async def view_comments_callback(callback_query: types.CallbackQuery):
        try:
            _, raw_id, raw_page = callback_query.data.split(":", 2)
            confession_id = int(raw_id)
            page = int(raw_page)
        except Exception:
            await callback_query.answer("Invalid callback")
            return

        conf = get_confession(confession_id)
        if conf is None or conf[4] != "approved":
            await callback_query.answer("Confession not available", show_alert=True)
            return

        rows = fetch_comments(confession_id, page)
        if not rows:
            await callback_query.answer("No comments found on this page.", show_alert=True)
            return

        msg_parts = []
        for i, text, ts in rows:
            msg_parts.append(f"💬 {text}\n<code>{human_ts(ts)}</code>")

        kb = build_view_pagination_kb(confession_id, page)
        await callback_query.message.answer("\n\n".join(msg_parts), reply_markup=kb)
        await callback_query.answer()

# -------------------- Admin notification helper --------------------
async def send_admin_notification(bot_instance, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None):
    for admin_id in ADMIN_IDS:
        try:
            await bot_instance.send_message(admin_id, text, reply_markup=reply_markup)
        except Exception:
            logger.exception(f"Failed sending admin notification to {admin_id}")
