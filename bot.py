"""
MegaSaver Bot — Railway-compatible
YouTube: full quality selection
Instagram / TikTok: instant best quality download + audio option
"""

import os
import re
import asyncio
import logging
import tempfile
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode

# ─── Config ───────────────────────────────────────────────────────────────────

BOT_TOKEN = os.environ["BOT_TOKEN"]
LOG_LEVEL  = os.getenv("LOG_LEVEL", "INFO")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
)
log = logging.getLogger(__name__)

DOWNLOAD_DIR = Path(tempfile.gettempdir()) / "megasaver"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ─── Platform detection ───────────────────────────────────────────────────────

PATTERNS = {
    "youtube": re.compile(
        r"https?://(?:www\.)?(?:youtube\.com/(?:watch\?v=|shorts/|embed/|live/)|youtu\.be/)[\w\-]+"
    ),
    "instagram": re.compile(
        r"https?://(?:www\.)?instagram\.com/(?:p|reel|tv)/[\w\-]+"
    ),
    "tiktok": re.compile(
        r"https?://(?:www\.|vm\.|vt\.)?tiktok\.com/[\w\-/@?=&]+"
    ),
}

EMOJI = {"youtube": "▶️", "instagram": "📸", "tiktok": "🎵"}

def detect(text: str) -> tuple[str | None, str | None]:
    for platform, pat in PATTERNS.items():
        m = pat.search(text)
        if m:
            return platform, m.group(0)
    return None, None

# ─── Quality options (YouTube only) ──────────────────────────────────────────

YT_QUALITIES = [
    (
        "q_best",
        "✨  Best Quality",
        ["-f", "bestvideo+bestaudio/best", "--merge-output-format", "mp4"],
    ),
    (
        "q_720",
        "🎥  720p",
        ["-f", "bestvideo[height<=720]+bestaudio/best[height<=720]/best", "--merge-output-format", "mp4"],
    ),
    (
        "q_480",
        "📱  480p",
        ["-f", "bestvideo[height<=480]+bestaudio/best[height<=480]/best", "--merge-output-format", "mp4"],
    ),
    (
        "q_360",
        "💾  360p",
        ["-f", "bestvideo[height<=360]+bestaudio/best[height<=360]/best", "--merge-output-format", "mp4"],
    ),
    (
        "audio",
        "🎵  Audio Only  MP3",
        ["-x", "--audio-format", "mp3", "--audio-quality", "0"],
    ),
]

QUALITY_MAP: dict[str, tuple[str, list[str]]] = {
    key: (label, args) for key, label, args in YT_QUALITIES
}

# Format args for instant downloads (Instagram / TikTok)
INSTANT_FORMAT = ["-f", "bestvideo+bestaudio/best", "--merge-output-format", "mp4"]
AUDIO_FORMAT   = ["-x", "--audio-format", "mp3", "--audio-quality", "0"]

def build_yt_keyboard(url: str) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(YT_QUALITIES[0][1], callback_data=f"{YT_QUALITIES[0][0]}||{url}"),
            InlineKeyboardButton(YT_QUALITIES[1][1], callback_data=f"{YT_QUALITIES[1][0]}||{url}"),
        ],
        [
            InlineKeyboardButton(YT_QUALITIES[2][1], callback_data=f"{YT_QUALITIES[2][0]}||{url}"),
            InlineKeyboardButton(YT_QUALITIES[3][1], callback_data=f"{YT_QUALITIES[3][0]}||{url}"),
        ],
        [
            InlineKeyboardButton(YT_QUALITIES[4][1], callback_data=f"{YT_QUALITIES[4][0]}||{url}"),
        ],
    ]
    return InlineKeyboardMarkup(rows)

# ─── Downloader ───────────────────────────────────────────────────────────────

async def download(url: str, fmt_args: list[str], out_dir: Path) -> Path:
    template = str(out_dir / "%(id)s.%(ext)s")
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--max-filesize", "50m",
        "--no-warnings",
        "-o", template,
    ] + fmt_args + [url]

    log.info("Running: %s", " ".join(cmd))
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(stderr.decode().strip() or "yt-dlp failed with no output")

    files = sorted(out_dir.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        raise RuntimeError("Download completed but no file was found")
    return files[0]

def cleanup(directory: Path) -> None:
    for f in directory.iterdir():
        try:
            f.unlink()
        except Exception:
            pass

async def send_file(message, file_path: Path, is_audio: bool, caption: str) -> None:
    with open(file_path, "rb") as fh:
        if is_audio:
            await message.reply_audio(audio=fh, caption=caption, parse_mode=ParseMode.MARKDOWN)
        else:
            await message.reply_video(video=fh, caption=caption, parse_mode=ParseMode.MARKDOWN, supports_streaming=True)

def error_message(err: str) -> str:
    if "50m" in err or "File size" in err or "maxfilesize" in err.lower():
        return "⚠️ File exceeds *50 MB*.\nTry a lower quality or Audio Only."
    elif "private" in err.lower() or "login" in err.lower():
        return "🔒 This content is private or requires a login."
    elif "unavailable" in err.lower() or "removed" in err.lower():
        return "❌ This video is unavailable or has been removed."
    return "❌ Download failed. The video may be unavailable or region-locked."

# ─── Handlers ─────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 *MegaSaver Bot*\n\n"
        "▶️ *YouTube* — choose quality\n"
        "📸 *Instagram* — instant best quality\n"
        "🎵 *TikTok* — instant best quality\n\n"
        "Works in DMs and groups ✅",
        parse_mode=ParseMode.MARKDOWN,
    )

async def cmd_help(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🛠 *How MegaSaver works*\n\n"
        "Just send a video link:\n\n"
        "▶️ *YouTube* — pick from ✨ Best / 🎥 720p / 📱 480p / 💾 360p / 🎵 MP3\n"
        "📸 *Instagram* — downloads instantly at best quality\n"
        "🎵 *TikTok* — downloads instantly at best quality\n\n"
        "⚠️ Max file size: *50 MB* (Telegram bot limit)",
        parse_mode=ParseMode.MARKDOWN,
    )

async def handle_link(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    platform, url = detect(update.message.text)

    if not platform:
        if update.message.chat.type != "private":
            return
        await update.message.reply_text(
            "❌ No supported link found.\n"
            "Send a YouTube, Instagram, or TikTok URL."
        )
        return

    emoji = EMOJI[platform]

    # YouTube — show quality keyboard
    if platform == "youtube":
        await update.message.reply_text(
            f"{emoji} *YouTube link detected*\n\nChoose your quality 👇",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=build_yt_keyboard(url),
        )
        return

    # Instagram / TikTok — download instantly
    msg = await update.message.reply_text(
        f"{emoji} *{platform.capitalize()} link detected*\n\n⏳ Downloading…",
        parse_mode=ParseMode.MARKDOWN,
    )

    user_id  = update.message.from_user.id
    user_dir = DOWNLOAD_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)

    try:
        file_path = await download(url, INSTANT_FORMAT, user_dir)
        size_mb   = file_path.stat().st_size / (1024 * 1024)
        caption   = f"{emoji} *{platform.capitalize()}* — Best Quality\n📦 {size_mb:.1f} MB  •  🤖 @megasaveroriginalbot"

        await msg.edit_text("✅ *Done! Sending…*", parse_mode=ParseMode.MARKDOWN)
        await send_file(update.message, file_path, is_audio=False, caption=caption)
        await msg.delete()

    except Exception as exc:
        log.error("Download error: %s", exc)
        await msg.edit_text(error_message(str(exc)), parse_mode=ParseMode.MARKDOWN)

    finally:
        cleanup(user_dir)

# YouTube quality callback
async def handle_quality(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if "||" not in query.data:
        return

    key, url = query.data.split("||", 1)

    if key not in QUALITY_MAP:
        await query.edit_message_text("❌ Unknown quality option.")
        return

    label, fmt_args = QUALITY_MAP[key]
    is_audio = key == "audio"

    await query.edit_message_text(
        f"▶️ *Downloading…*\n\n{label}\nThis may take a moment.",
        parse_mode=ParseMode.MARKDOWN,
    )

    user_id  = query.from_user.id
    user_dir = DOWNLOAD_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)

    try:
        file_path = await download(url, fmt_args, user_dir)
        size_mb   = file_path.stat().st_size / (1024 * 1024)
        caption   = f"▶️ *YouTube* — {label}\n📦 {size_mb:.1f} MB  •  🤖 @megasaveroriginalbot"

        await query.edit_message_text("✅ *Done! Sending…*", parse_mode=ParseMode.MARKDOWN)
        await send_file(query.message, file_path, is_audio, caption)
        await query.delete_message()

    except Exception as exc:
        log.error("Download error: %s", exc)
        await query.edit_message_text(error_message(str(exc)), parse_mode=ParseMode.MARKDOWN)

    finally:
        cleanup(user_dir)

# ─── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    log.info("Starting MegaSaver Bot…")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help",  cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.add_handler(CallbackQueryHandler(handle_quality))

    log.info("Polling started.")
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )

if __name__ == "__main__":
    main()
