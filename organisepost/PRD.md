# Product Requirements Document (PRD): Standalone Caption Organizer Bot

This document outlines the product requirements and technical design for the Standalone Caption Organizer Bot located in the `organisepost/` directory.

---

## 1. Objective & Scope
The objective is to build a standalone, resilient, and automated background script (`organizer_bot.py`) that extracts media and links from your chat history with `@DiskWalaFileUploaderBot`, cleans and verifies the metadata (spelling, titles, and release years) via the **Gemini AI API (with Google Search Grounding)**, formats the post using a premium visual style, and publishes the result to the channel `@organisepost`.

This system runs completely independently from the main pipeline bot (`pipeline_bot.py`), ensuring that your core uploading operations are untouched and safe.

---

## 2. Key Features & Functional Requirements

### A. Source Data Extraction (DiskWala Chat History)
* **Chronological Scanning**: The bot scans your direct message history with `@DiskWalaFileUploaderBot` from oldest to newest.
* **Link Matching**: It filters for incoming bot messages containing watch links (`diskwala.com`).
* **Original Message Fetching**: By reading the `reply_to_message_id` on the bot's link reply, the bot resolves the original video file sent to DiskWala. This fetches:
  1. The raw text caption.
  2. The actual video/document file containing the thumbnail.

### B. Image Acquisition & Enhancement (Zero Missing Images)
* **Direct Download**: Downloads the thumbnail using the direct `Thumbnail` object passing method (`app.download_media(media.thumbs[0], ...)`), avoiding expired file references.
* **Pillow Upscaling**: Enhances the downloaded thumbnail by:
  * Upscaling the image dimensions by **2x** using Lanczos resizing.
  * Adjusting sharpness (+1.8), color saturation (+1.3), contrast (+1.2), and brightness (+1.1) to create a premium card appearance.

### C. Gemini AI Verification & Fuzzy Matching
* **Internet Check**: Calls the Gemini API (`gemini-1.5-flash` model) with **Google Search Grounding** (`tools="google_search"`) enabled.
* **Spelling & Fact Correction**: Gemini automatically searches Google to fuzzy-match and correct any spelling typos in the title (e.g., `"Strger Thngs"` ➔ `"Stranger Things"`) and corrects inaccurate release years.
* **Structured Output**: Returns clean metadata fields: Title, Release Year, Content Type (Movie/Web Series), Video Quality, Languages, Genres, and Hashtags.

### D. Premium Visual Caption Layout
* Compiles the corrected details and upscaled image into a standardized, visually striking card layout:
  ```text
  🔥 <TITLE> (<YEAR>)
  ━━━━━━━━━━━━━━━━━━━━━━
  ℹ️ INFO & SPECIFICATIONS:
  🎥 Type: <Movie / Web Series>
  🗣️ Language: <Languages>
  🎭 Genre: <Genres>
  📺 Quality: <Quality>
  ━━━━━━━━━━━━━━━━━━━━━━
  🎬 Watch Here 👇
  <DiskWala Link>
  ━━━━━━━━━━━━━━━━━━━━━━
  <Hashtags>
  ```

---

## 3. Technical Specifications

### A. Session Isolation & Concurrency
* **Session Name**: `organizer_session.session` (completely isolated from the pipeline session, allowing concurrent background runs without SQLite locks).
* **Updates Disabled**: Initialized with `no_updates=True` to ignore live Telegram events, saving bandwidth and preventing event-loop crashes.

### B. SQLite Progress Database (`organizer_progress.db`)
* **Table `processed_replies`**: Tracks the primary key `reply_msg_id` of the processed DiskWala links.
* **Table `progress`**: Holds the current message checkpoint `last_msg_id` of the chat scan.

### C. Resiliency & Rate Limit Handling
* **API Rate Limiting**: The script wraps Gemini API calls in a retry loop. If a `429 Too Many Requests` code is received, it waits exponentially (10s, 20s, 30s) before retrying.
* **Network Fail-Safe**: The main execution loop catches network disconnect exceptions (such as `OSError: Connection lost`), logs them, waits 30 seconds, and retries automatically without crashing.

---

## 4. Configuration Environment Variables (`.env`)

| Variable | Description | Default Value |
| :--- | :--- | :--- |
| `API_ID` | Telegram API ID | *(Provided)* |
| `API_HASH` | Telegram API Hash | *(Provided)* |
| `SESSION_NAME` | Session file name | `organizer_session` |
| `TARGET_CHAT` | Target organized channel link | `https://t.me/organisepost` |
| `TARGET_BOT_USERNAME` | Bot username | `DiskWalaFileUploaderBot` |
| `DB_FILE` | Progress SQLite database filename | `organizer_progress.db` |
| `COOLDOWN_BETWEEN_POSTS` | Sleep duration between uploads (seconds) | `15` |
| `SCAN_COOLDOWN` | Sleep duration between history checks (seconds) | `300` |
| `GEMINI_API_KEY` | Google Generative AI API Key | *(User Provided)* |
