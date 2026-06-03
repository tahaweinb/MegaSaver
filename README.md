# 🚀 MegaSaver Bot

Telegram bot that downloads videos from **YouTube**, **Instagram**, and **TikTok** with full quality selection per platform. Runs on **Railway** with zero config.

---

## 📁 GitHub File Structure

```
megasaver/
├── bot.py              ← Main bot logic
├── requirements.txt    ← Python dependencies (pinned)
├── nixpacks.toml       ← Tells Railway to install Python + ffmpeg
├── railway.json        ← Railway deploy config (auto-restart etc.)
├── .env.example        ← Token template (safe to commit)
├── .gitignore          ← Excludes .env, __pycache__, temp files
└── README.md
```

---

## 🎛 Quality Options

### ▶️ YouTube
| Button | Resolution |
|--------|-----------|
| 🎬 1080p Full HD | Up to 1080p |
| 🎥 720p HD | Up to 720p |
| 📱 480p Medium | Up to 480p |
| 💾 360p Lite | Up to 360p |
| 🐢 144p Minimal | Up to 144p |
| 🎵 Audio Only MP3 | MP3, best bitrate |

### 📸 Instagram & 🎵 TikTok
| Button | Resolution |
|--------|-----------|
| 🎬 Best Quality | Highest available |
| 🎥 720p | Up to 720p |
| 📱 480p Compressed | Up to 480p |
| 💾 360p Light | Up to 360p |
| 🎵 Audio Only MP3 | MP3, best bitrate |

---

## 🚀 Deploy to Railway

### Step 1 — Create the bot

1. Open Telegram → **@BotFather** → `/newbot`
2. Follow prompts, copy the token

### Step 2 — Enable Group Privacy (for group support)

1. **@BotFather** → `/mybots` → select your bot
2. **Bot Settings** → **Group Privacy** → **Turn Off**

### Step 3 — Push to GitHub

```bash
git init
git add .
git commit -m "initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/megasaver.git
git push -u origin main
```

### Step 4 — Deploy on Railway

1. Go to [railway.app](https://railway.app) → **New Project**
2. Select **Deploy from GitHub repo** → pick `megasaver`
3. Railway auto-detects `nixpacks.toml` and installs everything
4. Go to your service → **Variables** tab → add:
   ```
   BOT_TOKEN = your_token_here
   ```
5. Railway redeploys automatically — bot is live 🎉

---

## 💻 Run Locally

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/megasaver.git
cd megasaver

# 2. Install deps (requires ffmpeg on PATH)
pip install -r requirements.txt

# 3. Run
BOT_TOKEN="your_token_here" python bot.py
```

> **ffmpeg required locally**: `sudo apt install ffmpeg` (Linux) or `brew install ffmpeg` (Mac)

---

## ⚠️ Notes

- Telegram bots have a **50 MB** upload cap — large videos show a warning to pick lower quality
- Instagram private posts and region-locked TikToks won't work
- Keep `yt-dlp` fresh — update `requirements.txt` version every few weeks as platforms change their APIs

---

## 🔄 Updating yt-dlp on Railway

Change the version in `requirements.txt`, commit, push — Railway auto-redeploys.

```
yt-dlp==2024.12.13   ← bump this to latest
```

Check latest: https://github.com/yt-dlp/yt-dlp/releases
