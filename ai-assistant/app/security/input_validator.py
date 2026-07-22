from app.utils.logger import error_logger

class InputValidator:
    """
    Validates user input text for maximum length and presence.
    """
    @staticmethod
    def validate_message(text: str, max_length: int = 4000) -> bool:
        if not text or not text.strip():
            error_logger.warning("Input validation failed: Empty message.")
            return False
            
        if len(text) > max_length:
            error_logger.warning(
                f"Input validation failed: Message length ({len(text)}) "
                f"exceeds maximum allowed length of {max_length} characters."
            )
            return False
            
        return True
