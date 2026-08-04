# Product Requirements Document (PRD): AllDiskWalaPost Workflow Bot

This document outlines the product requirements and technical design for the AllDiskWalaPost Workflow Bot located in the `alldiskwalapost/` directory.

---

## 1. Objective & Scope
The objective is to build a standalone, automated workflow bot (`alldiskwalapost_bot.py`) that reads posts from the source channel `https://t.me/organisepost`, extracts and cleans the movie/series metadata via the **Groq API** using the `llama-3.3-70b-versatile` model, and publishes the compiled clean metadata along with the post's thumbnail to the target channel `https://t.me/diskwalapost`.

---

## 2. Key Features & Functional Requirements

### A. Source Data Scraper
* **Chronological Processing**: Scans posts in the source channel `https://t.me/organisepost` from oldest to newest.
* **Link Filtering**: Only processes posts containing a valid DiskWala watch link (`diskwala.com`).

### B. Groq API Metadata Clean-up
* **Precise Extraction**: Calls Groq API to parse the raw text and extract structured metadata:
  * Title (Cleaned of release group tags/dots)
  * Season & Episodes (Only if it's a web series)
  * Resolution (e.g. 720p, 1080p)
  * Languages (e.g. Hindi, English)
  * Subtitles (e.g. ESub, MSub)
  * Link (DiskWala Link)
* **Omit Empty Fields**: If fields like `Season` or `Episodes` are missing (e.g. for a movie), the bot completely excludes those lines from the final post.

### C. Combined Media Posting
* **Thumbnail Detection**: Downloads the photo from the source channel post if it exists.
* **Photo Post**: If a photo was downloaded, it combines the clean metadata as the caption and posts it as a Photo.
* **Text Post Fallback**: If no photo exists (or download fails), it posts the metadata as a standard text message.

### D. MongoDB State Tracking
* Connects to MongoDB Atlas using the URI from `.env`.
* Saves the current scraping checkpoint (`last_msg_id`) to the `alldiskwalapost_progress` collection.
* Logs processed post IDs to the `alldiskwalapost_processed` collection to ensure that no duplicate posts are sent, even if the script is restarted.

---

## 3. Configuration Environment Variables (`.env`)

| Variable | Description | Example / Default Value |
| :--- | :--- | :--- |
| `API_ID` | Telegram API ID | `28675574` |
| `API_HASH` | Telegram API Hash | `b4086c0ad6e85161beef7a23df4ef3b5` |
| `SESSION_NAME` | Pyrogram session file name | `alldiskwalapost_session` |
| `SOURCE_CHAT` | Source channel link | `https://t.me/organisepost` |
| `TARGET_CHAT` | Target channel link | `https://t.me/diskwalapost` |
| `COOLDOWN_BETWEEN_POSTS` | Sleep duration between posts (seconds) | `15` |
| `SCAN_COOLDOWN` | Sleep duration between channel checks (seconds) | `300` |
| `MONGO_URI` | MongoDB Connection URI | `mongodb+srv://...` |
| `GROQ_API_KEY` | Groq API developer key | `gsk_...` |
| `GROQ_MODEL` | Groq model identifier | `llama-3.3-70b-versatile` |

---

## 4. Execution Guide

### Prerequisite Dependencies
Install the required packages in your Python environment:
```bash
pip install -r requirements.txt
```

### Starting the Bot
Run the bot script from your terminal:
```bash
python alldiskwalapost_bot.py
```

*Note: On your first execution, Pyrogram will ask you to enter your Telegram Phone Number (in international format, e.g., `+911234567890`) and the login code sent to your Telegram application. Once authorized, it will create a local `alldiskwalapost_session.session` file to stay logged in.*
