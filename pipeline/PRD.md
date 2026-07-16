# PRD: Monetization & Movie Posting Pipeline Bot

## 1. Component Overview
The **Pipeline** component (`pipeline/`) is a state-preserving Telegram bot engine that acts as the monetization and publishing tier of the movie distribution system. It watches a staging channel (`https://t.me/videos_down`), uploads raw files to the `@DiskWalaFileUploaderBot` to get download links, upscales the video thumbnails 2x using Pillow, and publishes the final post to the public channel (`https://t.me/allpost1234`) using the visual format of **Image 1**.

---

## 2. Goals & User Requirements
*   **Sequential Chronological Processing**: Scrapes video messages from oldest to newest.
*   **Duplicate Elimination**: Must NEVER re-upload a movie to the DiskWala bot if the bot is restarted mid-process. It must store sent states in SQLite and lookup past replies.
*   **Target Caption Deduplication**: Must check if a movie with the exact same caption has already been published to the target channel `https://t.me/allpost1234` before processing. If it exists, the movie must be skipped in the pipeline to prevent duplicate target channel posts.
*   **Precise Reply Correlation**: Matches incoming DiskWala bot links to active processing items by comparing the `reply_to_message_id` on incoming replies with our sent media message ID.
*   **Groq API Reply Parsing**: Incorporates LLM classification (using Groq's Llama 3 API) to analyze DiskWala bot reply messages, determine if they contain links, request retries, or indicate upload errors, making classification resilient to copy/format updates.
*   **Enhanced Thumbnails (Image 1)**: Downloads the movie's default video thumbnail and uses Pillow to upscale it 2x, sharpen it, and boost colors/contrast.
*   **Image 1 Caption Formatting**: Compiles posts exactly as shown in Image 1:
    *   Enhanced thumbnail photo.
    *   Caption: Original video caption + double newlines + divider line (`──────────`) + Clapperboard header (`🎬 Watch Here 👇`) + raw DiskWala URL at the bottom.
    *   **No inline buttons** or keyboards.

---

## 3. Architecture & Code Map
*   **[pipeline_bot.py](file:///c:/Users/ashwani/Desktop/demo/pipeline/pipeline_bot.py)**: The main Pyrogram bot engine implementing the state machine.
*   **[requirements.txt](file:///c:/Users/ashwani/Desktop/demo/pipeline/requirements.txt)**: Core dependencies (`pyrogram`, `tgcrypto`, `Pillow`, `python-dotenv`).
*   **[.env](file:///c:/Users/ashwani/Desktop/demo/pipeline/.env)**: Target bot configurations and channel links.
*   **[pipeline_progress.db](file:///c:/Users/ashwani/Desktop/demo/pipeline/pipeline_progress.db)**: SQLite database tracking progress and upload associations.
*   **[pipeline_session.session](file:///c:/Users/ashwani/Desktop/demo/pipeline/pipeline_session.session)**: Session storage for Pyrogram.
*   **[temp_thumbs/](file:///c:/Users/ashwani/Desktop/demo/pipeline/temp_thumbs)**: Subfolder used for downloading and upscaling thumbnails dynamically.

---

## 4. Key Functions & Logic

### A. SQLite Upload Mapping
*   `save_diskwala_upload(msg_id, sent_msg_id)`: Registers the upload in the database immediately upon sending the file.
*   `get_sent_msg_id(msg_id)`: Checks if a source message has a registered DiskWala upload on restart.

### B. Reply Tracking & Correlation
*   **Live Waiting (Polling)**: The bot is initialized with `no_updates=True` to ignore all incoming events and prevent update-related `ChatIdInvalid` background exceptions. It directly polls the recent chat history with `@DiskWalaFileUploaderBot` and retrieves the replies.
*   **History Lookup (on restart)**: If a video was already sent before restart, the bot scans the recent history of `@DiskWalaFileUploaderBot`. It looks for messages where the `reply_to_message_id` matches our stored `sent_msg_id`.
*   **Groq LLM Reply Classification (`analyze_diskwala_reply_with_groq`)**: Instead of relying solely on regex, the bot posts the uploader's reply text to the Groq API (using model `llama3-8b-8192`) to obtain classification (`status: "link_found" | "retry_requested" | "error" | "unknown"`) and extracts the direct URL.
*   **Rule-Based Fallback**: If the Groq API call fails or times out, the bot seamlessly falls back to local regex search patterns and keyword checks, assuring zero pipeline disruption.

### C. Pillow Image Enhancer (`enhance_thumbnail`)
1.  Upscales the downloaded image by 200% (2x width and height) using `Image.Resampling.LANCZOS`.
2.  Applies `ImageEnhance.Sharpness` (enhanced 1.8x).
3.  Applies `ImageEnhance.Color` (saturated 1.3x).
4.  Applies `ImageEnhance.Contrast` (increased 1.2x).
5.  Applies `ImageEnhance.Brightness` (increased 1.1x).

### D. Target Caption Deduplication Check (`is_caption_already_published`)
Before uploading to DiskWala, the bot checks if the video's caption already exists in the target channel `https://t.me/allpost1234` by:
1. Scanning the target channel's recent history (limit 200 messages).
2. Searching for the original caption text as a substring of any existing target post.
3. If a match is found, the bot logs it, marks the source message ID as sent in the database, saves the progress checkpoint, and skips processing.

### E. Pending Uploads Recovery (`process_pending_uploads`)
On startup and at the beginning of each run loop, the bot checks for any timed-out or skipped uploads by querying `diskwala_uploads` for message IDs that are not present in `sent_messages`. For each pending item:
1. It scans the DiskWala bot chat history (limit 30 messages) for a reply matching the pending `sent_msg_id`.
2. If found, it extracts the link, fetches the original video details, enhances the thumbnail, and publishes the post to the target channel.
3. Marks the message as sent to remove it from the pending queue.

### F. Final Post Publication (`publish_compiled_post`)
Compiles the post with the enhanced thumbnail. Generates the caption using:
```python
if orig_caption:
    caption_text = f"{orig_caption}\n\n──────────\n🎬 Watch Here 👇\n{diskwala_link}"
else:
    caption_text = f"🎬 Watch Here 👇\n{diskwala_link}"
```
Publishes to the channel via `app.send_photo` (or `app.send_message` as fallback if no thumbnail is available).

---

## 5. Database Schema (`pipeline_progress.db`)

### `sent_messages`
Tracks source video IDs published to the public target channel.
*   `msg_id` (`INTEGER PRIMARY KEY`): Source message ID.

### `progress`
Stores scanning progress checkpoint.
*   `key` (`TEXT PRIMARY KEY`): Key named `last_id`.
*   `last_msg_id` (`INTEGER`): ID of the latest source message.

### `diskwala_uploads`
Maps source messages to the message ID sent in DiskWala's chat.
*   `msg_id` (`INTEGER PRIMARY KEY`): Source message ID.
*   `sent_msg_id` (`INTEGER`): Message ID representing the sent media inside `@DiskWalaFileUploaderBot`'s chat.

---

## 6. Environment Configurations (`.env`)

| Variable | Description |
| :--- | :--- |
| `API_ID` | Telegram API ID from my.telegram.org. |
| `API_HASH` | Telegram API Hash from my.telegram.org. |
| `SESSION_NAME` | Pyrogram session filename (`pipeline_session`). |
| `SOURCE_CHAT` | Channel link containing staging videos (`https://t.me/videos_down`). |
| `TARGET_CHAT` | Public channel link for published posts (`https://t.me/allpost1234`). |
| `TARGET_BOT_USERNAME` | Username of the uploader bot (`DiskWalaFileUploaderBot`). |
| `COOLDOWN_BETWEEN_POSTS` | Delay in seconds between posts (default `15`). |
| `DB_FILE` | Database filename (`pipeline_progress.db`). |
| `GROQ_API_KEY` | Groq developer API key for LLM reply analysis. |

---

## 7. Execution Guide
To run the pipeline bot:
```bash
cd pipeline
python pipeline_bot.py
```
To stop the bot, press `Ctrl+C`. The bot will stop the active background tasks, exit the Pyrogram client, and shut down cleanly.
