import json
import logging
import urllib.request
import urllib.error
from typing import Optional, Dict, Any

from brokerage_parser.config import settings

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self):
        self.base_url = settings.LLM_BASE_URL
        self.api_key = settings.LLM_API_KEY
        self.model = settings.LLM_MODEL
        self.enabled = settings.LLM_ENABLED


    def complete(self, prompt: str, json_schema: Optional[Dict] = None) -> str:
        """
        Send a completion request to the LLM.

        Args:
            prompt: The text prompt.
            json_schema: Optional JSON schema to enforce structure (if supported by backend).

        Returns:
            The content string from the LLM response.
        """
        if not self.enabled:
            logger.warning("LLMClient called but LLM_ENABLED is False.")
            return ""

        url = f"{self.base_url}/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        # Construct payload
        messages = [
            {"role": "system", "content": "You are a helpful assistant that extracts data from documents. Return ONLY the requested value."},
            {"role": "user", "content": prompt}
        ]

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False
        }

        if json_schema:
            # OpenAI / Ollama compatible "format": "json" or specific schema support
            # For broad compatibility, we'll request JSON mode if schema is provided
            payload["response_format"] = {"type": "json_object"}
            # Append schema instruction to prompt if not implicit
            messages[0]["content"] += f" Output valid JSON matching this schema: {json.dumps(json_schema)}"

        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")

            with urllib.request.urlopen(req) as response:
                response_body = response.read().decode("utf-8")
                response_json = json.loads(response_body)

                # Extract content
                # Std OpenAI format: choices[0].message.content
                if "choices" in response_json and len(response_json["choices"]) > 0:
                    content = response_json["choices"][0]["message"]["content"]
                    return content.strip()
                else:
                    logger.error(f"Unexpected LLM response format: {response_body}")
                    return ""

        except urllib.error.URLError as e:
            logger.error(f"LLM request failed: {e}")
            return ""
        except Exception as e:
            logger.error(f"LLM processing error: {e}")
            return ""
