"""
MegaSaver Bot — Railway-compatible
Supports: YouTube, Instagram, TikTok
Full quality selection per platform + Audio Only
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

BOT_TOKEN = os.environ["BOT_TOKEN"]          # Required — set in Railway env vars
LOG_LEVEL  = os.getenv("LOG_LEVEL", "INFO")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
)
log = logging.getLogger(__name__)

# Railway containers have /tmp available; use a subdirectory
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
    """Return (platform, url) or (None, None)."""
    for platform, pat in PATTERNS.items():
        m = pat.search(text)
        if m:
            return platform, m.group(0)
    return None, None

# ─── Quality definitions per platform ────────────────────────────────────────

# Each entry: (callback_key, button_label, yt_dlp_format_args)
QUALITIES = {
    "youtube": [
        ("yt_1080", "🎬  1080p  Full HD",  ["-f", "bestvideo[height<=1080][ext=mp4]+bestaudio/best[height<=1080]", "--merge-output-format", "mp4"]),
        ("yt_720",  "🎥  720p  HD",         ["-f", "bestvideo[height<=720][ext=mp4]+bestaudio/best[height<=720]",   "--merge-output-format", "mp4"]),
        ("yt_480",  "📱  480p  Medium",     ["-f", "bestvideo[height<=480][ext=mp4]+bestaudio/best[height<=480]",   "--merge-output-format", "mp4"]),
        ("yt_360",  "💾  360p  Lite",       ["-f", "bestvideo[height<=360][ext=mp4]+bestaudio/best[height<=360]",   "--merge-output-format", "mp4"]),
        ("yt_144",  "🐢  144p  Minimal",    ["-f", "bestvideo[height<=144][ext=mp4]+bestaudio/best[height<=144]",   "--merge-output-format", "mp4"]),
        ("audio",   "🎵  Audio Only  MP3",  ["-x", "--audio-format", "mp3", "--audio-quality", "0"]),
    ],
    "instagram": [
        ("ig_best",  "🎬  Best Quality",    ["-f", "bestvideo+bestaudio/best",                                      "--merge-output-format", "mp4"]),
        ("ig_720",   "🎥  720p",            ["-f", "bestvideo[height<=720]+bestaudio/best[height<=720]",            "--merge-output-format", "mp4"]),
        ("ig_480",   "📱  480p  Compressed",["-f", "bestvideo[height<=480]+bestaudio/best[height<=480]",            "--merge-output-format", "mp4"]),
        ("ig_360",   "💾  360p  Light",     ["-f", "bestvideo[height<=360]+bestaudio/best[height<=360]",            "--merge-output-format", "mp4"]),
        ("audio",    "🎵  Audio Only  MP3", ["-x", "--audio-format", "mp3", "--audio-quality", "0"]),
    ],
    "tiktok": [
        ("tt_best",  "🎬  Best Quality",    ["-f", "bestvideo+bestaudio/best",                                      "--merge-output-format", "mp4"]),
        ("tt_720",   "🎥  720p",            ["-f", "bestvideo[height<=720]+bestaudio/best[height<=720]",            "--merge-output-format", "mp4"]),
        ("tt_480",   "📱  480p  Compressed",["-f", "bestvideo[height<=480]+bestaudio/best[height<=480]",            "--merge-output-format", "mp4"]),
        ("tt_360",   "💾  360p  Light",     ["-f", "bestvideo[height<=360]+bestaudio/best[height<=360]",            "--merge-output-format", "mp4"]),
        ("audio",    "🎵  Audio Only  MP3", ["-x", "--audio-format", "mp3", "--audio-quality", "0"]),
    ],
}

# Flat lookup: key → (label, format_args)
QUALITY_MAP: dict[str, tuple[str, list[str]]] = {
    key: (label, args)
    for entries in QUALITIES.values()
    for key, label, args in entries
}

def build_keyboard(platform: str, url: str) -> InlineKeyboardMarkup:
    rows = []
    entries = QUALITIES.get(platform, [])
    # Pair buttons 2 per row (last one full-width if odd)
    pairs = [entries[i:i+2] for i in range(0, len(entries), 2)]
    for pair in pairs:
        row = [
            InlineKeyboardButton(label, callback_data=f"{key}||{url}")
            for key, label, _ in pair
        ]
        rows.append(row)
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

# ─── Handlers ─────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 *MegaSaver Bot*\n\n"
        "Send any *YouTube*, *Instagram*, or *TikTok* link.\n"
        "I'll show you all available quality options — including audio only.\n\n"
        "Works in DMs and groups ✅",
        parse_mode=ParseMode.MARKDOWN,
    )

async def cmd_help(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🛠 *How MegaSaver works*\n\n"
        "1️⃣ Paste a video link\n"
        "2️⃣ Pick your quality from the buttons\n"
        "3️⃣ Get the file straight in Telegram\n\n"
        "📺 *YouTube* — 1080p / 720p / 480p / 360p / 144p / MP3\n"
        "📸 *Instagram* — Best / 720p / 480p / 360p / MP3\n"
        "🎵 *TikTok* — Best / 720p / 480p / 360p / MP3\n\n"
        "⚠️ Max file size: *50 MB* (Telegram bot limit)",
        parse_mode=ParseMode.MARKDOWN,
    )

async def handle_link(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    platform, url = detect(update.message.text)

    if not platform:
        if update.message.chat.type != "private":
            return  # silently ignore in groups
        await update.message.reply_text(
            "❌ No supported link found.\n"
            "Send a YouTube, Instagram, or TikTok URL."
        )
        return

    emoji = EMOJI[platform]
    keyboard = build_keyboard(platform, url)

    await update.message.reply_text(
        f"{emoji} *{platform.capitalize()} link detected*\n\n"
        f"Choose your quality 👇",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )

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
    platform = detect(url)[0] or "unknown"
    emoji = EMOJI.get(platform, "🌐")

    await query.edit_message_text(
        f"⏳ *Downloading…*\n\n{emoji} {label}\nThis may take a moment.",
        parse_mode=ParseMode.MARKDOWN,
    )

    user_id   = query.from_user.id
    user_dir  = DOWNLOAD_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)

    try:
        file_path    = await download(url, fmt_args, user_dir)
        size_mb      = file_path.stat().st_size / (1024 * 1024)
        is_audio     = key == "audio"

        caption = (
            f"{emoji} *{platform.capitalize()}* — {label}\n"
            f"📦 {size_mb:.1f} MB  •  🤖 @MegaSaverBot"
        )

        await query.edit_message_text("✅ *Done! Sending…*", parse_mode=ParseMode.MARKDOWN)

        with open(file_path, "rb") as fh:
            if is_audio:
                await query.message.reply_audio(
                    audio=fh,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN,
                )
            else:
                await query.message.reply_video(
                    video=fh,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN,
                    supports_streaming=True,
                )

        await query.delete_message()

    except Exception as exc:
        err = str(exc)
        log.error("Download error for %s: %s", url, err)

        if "50m" in err or "File size" in err or "maxfilesize" in err.lower():
            msg = "⚠️ File exceeds *50 MB*.\nTry a lower quality or Audio Only."
        elif "private" in err.lower() or "login" in err.lower():
            msg = "🔒 This content is private or requires a login."
        elif "unavailable" in err.lower() or "removed" in err.lower():
            msg = "❌ This video is unavailable or has been removed."
        else:
            msg = f"❌ Download failed:\n`{err[:300]}`"

        await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN)

    finally:
        cleanup(user_dir)

# ─── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    log.info("Starting MegaSaver Bot…")

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

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
