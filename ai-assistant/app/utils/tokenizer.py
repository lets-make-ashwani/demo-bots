import tiktoken
from app.utils.logger import error_logger

def count_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    """
    Counts the number of tokens in a text string.
    If tiktoken fails, falls back to character-length based approximation (1 token ~= 4 chars).
    """
    if not text:
        return 0
    try:
        encoding = tiktoken.get_encoding(encoding_name)
        return len(encoding.encode(text))
    except Exception as e:
        error_logger.debug(f"Failed to use tiktoken for token counting ({e}), falling back to approximation.")
        # Fallback approximation: 1 token is roughly 4 characters
        return len(text) // 4
