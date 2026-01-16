from typing import Dict


class LocalLLMGenerator:
    def __init__(self, model_name: str):
        self.model_name = model_name

    def generate(self, prompt: str, evidence: Dict) -> str:
        raise NotImplementedError(
            "Plug in a local LLM runner (e.g., llama.cpp, vLLM) and implement generate()."
        )
