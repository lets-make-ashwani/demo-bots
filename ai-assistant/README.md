# Production-Ready AI Assistant Bot Platform

This is an enterprise-grade AI Assistant Telegram Bot built on a clean, scalable, decoupled architecture using **python-telegram-bot**, **Groq API**, and **MongoDB**.

## 🚀 Key Features
* ⚡ **Ultra-Fast LLM Inference:** Powered by Groq (default model `llama-3.3-70b-versatile`).
* 💬 **Multi-Conversation Threads:** Isolates context per session, matching modern ChatGPT-style chat interfaces.
* 🛡️ **Sliding Window Token Memory:** Prunes conversation context based on actual token counts (`tiktoken`) instead of arbitrary message counters.
* 🎭 **Dynamic System Prompts:** Quick personality changes via inline keyboards (loaded dynamically from YAML configurations).
* 🔒 **Security-First Middlewares:** Out-of-the-box support for rate limiting, database authentication, logging, exception recovery, and automated typing indicators.
* 📊 **Operational Telemetry:** Life-cycle logging (`bot.log`, `api.log`, `error.log`) and background analytics aggregation.
* ⚙️ **Modular Clean Architecture:** Completely decouples Telegram delivery mechanics from logic via a `ChatOrchestrator` layer.

---

## 📁 Directory Structure
```text
ai-assistant/
├── app/
│   ├── config/             # Environment configurations (Base, Dev, Prod)
│   ├── database/           # MongoDB Motor driver setup & Collection Repositories
│   ├── handlers/           # Telegram command and chat callback routers
│   ├── middlewares/        # Interceptor decorators (Auth, Rate limit, Logging, Typing)
│   ├── orchestrators/      # Chat Orchestrator (Business logic mapping)
│   ├── prompts/            # Custom System Prompts in YAML formatting
│   ├── security/           # Sanitizers and input length validators
│   ├── services/           # Service abstractions (Memory, Analytics, Prompts, User, LLM)
│   ├── utils/              # Tokenizer, Markdown converter, Logger, Retry wrapper
│   └── bot.py              # Application builder & hook registration
├── deploy/                 # Dockerfile, docker-compose.yml, and Render configuration
├── tests/                  # Unit and Integration test suites using pytest
├── .env.example            # Environment variables placeholder
├── requirements.txt        # Package dependencies
├── README.md               # User documentation
└── run.py                  # Entrypoint execution script
```

---

## 🛠️ Installation & Setup

1. **Clone the repository and go to the directory:**
   ```bash
   cd ai-assistant
   ```

2. **Create and populate `.env`:**
   Copy `.env.example` to `.env` and fill in your keys:
   ```env
   BOT_TOKEN=your_telegram_bot_token
   GROQ_API_KEY=your_groq_api_key
   MONGODB_URI=mongodb://localhost:27017
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the bot:**
   ```bash
   python run.py
   ```

---

## 🐳 Docker Deployment

To launch the bot and MongoDB simultaneously:
```bash
docker-compose -f deploy/docker-compose.yml up --build -d
```

---

## 🧪 Testing

To run the unit test suite:
```bash
pytest
```
