import re

class InputSanitizer:
    """
    Sanitizes user input by cleaning control characters, null bytes, and potentially malicious inputs.
    """
    @staticmethod
    def sanitize(text: str) -> str:
        if not text:
            return ""
        # Remove null bytes
        cleaned = text.replace("\x00", "")
        # Remove common control characters that could break parsing, preserving standard whitespace
        cleaned = re.sub(r"[\x01-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]", "", cleaned)
        return cleaned.strip()
