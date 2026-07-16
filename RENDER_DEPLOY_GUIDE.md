# Demo Bot System — Single-Container Free Render Deployment Guide

Because Render has discontinued the Free Tier for Background Workers (`type: worker`), we have redesigned your deployment to run **100% Free** inside a single Web Service (`demo-panel`).

The Web Service hosts your FastAPI Control Panel, and when you start the bots from the web UI, they run as background subprocesses on the same server.

---

## 🔑 Environment Variables to Enter on Render

When setting up the Blueprint on Render, you only need to fill in values for the **`demo-panel`** service. 

Copy and paste these exact values:

### 1. Core Configs
| Key | Value to Paste | Description |
|-----|----------------|-------------|
| **`API_ID`** | `28675574` | Telegram API ID |
| **`API_HASH`** | `b4086c0ad6e85161beef7a23df4ef3b5` | Telegram API Hash |
| **`MONGO_URI`** | (Paste your MongoDB connection link from MongoDB Atlas) | MongoDB connection URI |

### 2. Login Sessions (Get from your `SESSION_STRINGS_SAVE_THIS.txt`)
| Key | Value to Paste |
|-----|----------------|
| **`SESSION_STRING_SCRAPER`** | Paste the **Scraper Bot** session string |
| **`SESSION_STRING_PIPELINE`** | Paste the **Pipeline Bot** session string |
| **`SESSION_STRING_ORGANIZER`** | Paste the **Organizer Bot** session string |

### 3. Scraper Bot Settings
| Key | Value to Paste | Description |
|-----|----------------|-------------|
| **`SOURCE_CHAT_SCRAPER`** | `-1003913970582` | Source channel ID to scan |
| **`TARGET_CHAT_SCRAPER`** | `https://t.me/videos_down` | Staging channel link |
| **`CHAT_FOLDER_LINK`** | `https://t.me/addlist/fxxS8mNpSC8zYzRl` | Chat folder invite link |
| **`COOLDOWN_SCAN_INTERVAL`** | `600` | Cooldown in seconds between scans |

### 4. Pipeline Bot Settings
| Key | Value to Paste | Description |
|-----|----------------|-------------|
| **`SOURCE_CHAT_PIPELINE`** | `https://t.me/videos_down` | Staging channel link |
| **`TARGET_CHAT_PIPELINE`** | `https://t.me/allpost1234` | Public channel link |
| **`TARGET_BOT_USERNAME`** | `DiskWalaFileUploaderBot` | File uploader username |
| **`COOLDOWN_BETWEEN_POSTS`** | `15` | Cooldown in seconds |
| **`GROQ_API_KEY`** | (Paste your Groq API Key) | Groq Llama 3 key |

### 5. Organizer Bot Settings
| Key | Value to Paste | Description |
|-----|----------------|-------------|
| **`TARGET_CHAT_ORGANIZER`** | `https://t.me/organisepost` | Organizer channel link |
| **`GEMINI_API_KEY`** | (Paste your Gemini API Key) | Gemini key |


---

## 📋 Steps to Deploy on Render

1. Open your Render dashboard and delete the failed Blueprint instance (go to **Blueprints** -> click **demo-bots** -> click **Settings** -> **Delete Blueprint**).
2. Click **New +** -> **Blueprint**.
3. Select the **`lets-make-ashwani / demo-bots`** repository.
4. Render will read the updated `render.yaml` and prompt you for the variables under the single **`demo-panel`** web service.
5. Fill in the keys using the values in the tables above.
6. Click **Apply**.

---

## ⏰ Step 6: Set up Cron-Job.org (To Keep Awake 24/7)

Since we are using a free Web Service, Render will automatically put the container (and the bots) to sleep after 15 minutes of inactivity. 

To keep your bots running 24/7, we must keep it awake:
1. Once `demo-panel` is deployed, copy its public URL (e.g., `https://demo-panel-xxxx.onrender.com`).
2. Go to [cron-job.org](https://cron-job.org/) and create a free account.
3. Click **Create Cron Job**:
   * **Title**: Keep Bots Awake
   * **URL**: `https://your-panel-url.onrender.com/api/status`
   * **Schedule**: Every 12 minutes
4. Click **Create**.

Your single web service container will stay awake indefinitely, and your Scraper, Pipeline, and Organizer bots will run **24/7 in the background completely free of charge!**
