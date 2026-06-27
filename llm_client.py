import os
from ollama import Client as OllamaClient

from config import LLM_CONFIG_PATH, load_json


class LLMClient:
    def __init__(self):
        self.config = load_json(LLM_CONFIG_PATH, default={})
        self.provider = self.config.get("provider", "ollama")
        self.model = self.config.get("model", "qwen2.5:0.5b")
        self.base_url = self.config.get("base_url", "http://127.0.0.1:11434")
        self.temperature = self.config.get("temperature", 0.3)

        os.environ["NO_PROXY"] = "localhost,127.0.0.1"
        os.environ["no_proxy"] = "localhost,127.0.0.1"

    def chat(self, messages: list[dict]) -> str:
        if self.provider == "ollama":
            return self._chat_ollama(messages)

        raise NotImplementedError(f"暂不支持的 LLM provider: {self.provider}")

    def _chat_ollama(self, messages: list[dict]) -> str:
        client = OllamaClient(host=self.base_url)

        response = client.chat(
            model=self.model,
            messages=messages,
            options={
                "temperature": self.temperature
            }
        )

        return response["message"]["content"]