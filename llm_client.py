import os

from config import LLM_CONFIG_PATH, load_json


class LLMClient:
    def __init__(self):
        self.config = load_json(LLM_CONFIG_PATH, default={})

        self.provider = self.config.get("provider", "ollama")
        self.model = self.config.get("model", "qwen2.5:0.5b")
        self.base_url = self.config.get("base_url", "http://127.0.0.1:11434")
        self.temperature = self.config.get("temperature", 0.7)
        self.max_tokens = self.config.get("max_tokens", 400)
        self.api_key_env = self.config.get("api_key_env", "DEEPSEEK_API_KEY")

        os.environ["NO_PROXY"] = "localhost,127.0.0.1"
        os.environ["no_proxy"] = "localhost,127.0.0.1"

    def chat(self, messages: list[dict]) -> str:
        if self.provider == "ollama":
            return self._chat_ollama(messages)

        if self.provider in ["openai_compatible", "deepseek"]:
            return self._chat_openai_compatible(messages)

        raise NotImplementedError(f"暂不支持的 LLM provider: {self.provider}")

    def _chat_ollama(self, messages: list[dict]) -> str:
        try:
            from ollama import Client as OllamaClient
        except ImportError as e:
            raise ImportError("未安装 ollama 包，请运行: python -m pip install ollama") from e

        client = OllamaClient(host=self.base_url)

        response = client.chat(
            model=self.model,
            messages=messages,
            options={
                "temperature": self.temperature
            }
        )

        return response["message"]["content"]

    def _chat_openai_compatible(self, messages: list[dict]) -> str:
        try:
            from openai import OpenAI
        except ImportError as e:
            raise ImportError("未安装 openai 包，请运行: python -m pip install -U openai") from e

        api_key = os.environ.get(self.api_key_env)

        if not api_key:
            raise EnvironmentError(
                f"没有读取到环境变量 {self.api_key_env}。\n"
                f"CMD 临时设置：set {self.api_key_env}=你的key\n"
                f"PowerShell 临时设置：$env:{self.api_key_env}=\"你的key\""
            )

       


        client = OpenAI(
            api_key=api_key,
            base_url=self.base_url,
            timeout=30.0,
        )

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=False,
            )
        except Exception as e:
            print("[LLM] DeepSeek API 调用失败")
            raise e


        return response.choices[0].message.content or ""