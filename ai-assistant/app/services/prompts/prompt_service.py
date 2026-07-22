import os
import yaml
from typing import Dict, Any, Optional
from app.utils.logger import error_logger

class PromptService:
    """
    Service to load, cache, and serve custom system prompts defined in YAML files.
    """
    def __init__(self, prompts_dir: str = "app/prompts"):
        self.prompts_dir = prompts_dir
        self.cache: Dict[str, Dict[str, Any]] = {}

    def load_prompt(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Loads and parses a prompt YAML file. Caches the result in memory.
        """
        if name in self.cache:
            return self.cache[name]
            
        file_path = os.path.join(self.prompts_dir, f"{name}.yaml")
        if not os.path.exists(file_path):
            error_logger.warning(f"Prompt configuration file not found at: {file_path}")
            return None
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if not data or "content" not in data:
                    error_logger.error(f"Prompt YAML format error: Missing 'content' key in {file_path}")
                    return None
                
                self.cache[name] = data
                return data
        except Exception as e:
            error_logger.error(f"Failed to load prompt from {file_path}: {e}")
            return None

    def get_prompt_content(self, name: str = "assistant") -> str:
        """
        Gets the text content of the prompt, falling back to a default if unavailable.
        """
        prompt_data = self.load_prompt(name)
        if prompt_data:
            return prompt_data.get("content", "You are a helpful AI assistant.")
        return "You are a helpful AI assistant."

    def get_prompt_meta(self, name: str = "assistant") -> Dict[str, Any]:
        """
        Gets the metadata (temperature, model, etc.) associated with the prompt.
        """
        prompt_data = self.load_prompt(name)
        if prompt_data:
            return {k: v for k, v in prompt_data.items() if k != "content"}
        return {}
