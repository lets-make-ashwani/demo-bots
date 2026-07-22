# Models
MODEL_LLAMA_3_3_70B = "llama-3.3-70b-versatile"
MODEL_MIXTRAL_8X7B = "mixtral-8x7b-32768"
MODEL_GEMMA2_9B = "gemma2-9b-it"

DEFAULT_MODEL = MODEL_LLAMA_3_3_70B

AVAILABLE_MODELS = {
    MODEL_LLAMA_3_3_70B: "Llama 3.3 70B (Fast & Versatile)",
    MODEL_MIXTRAL_8X7B: "Mixtral 8x7B (Great for Reasoning)",
    MODEL_GEMMA2_9B: "Gemma 2 9B (Lightweight & Efficient)"
}

# Roles
ROLE_SYSTEM = "system"
ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"

# Default Preferences
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_HISTORY_TOKENS = 12000
DEFAULT_MAX_TOKENS = 2048
DEFAULT_LANGUAGE = "en"
