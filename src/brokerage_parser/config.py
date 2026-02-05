import os
from typing import Optional

class Config:
    # LLM Configuration
    LLM_ENABLED: bool = os.getenv("LLM_ENABLED", "False").lower() == "true"
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "llama3") # Default to llama3, user can change to gpt-4 etc.
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "ollama") # Ollama doesn't need a key usually

    # Other config vars can be added here
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

config = Config()
