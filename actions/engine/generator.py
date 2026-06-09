import time

from litellm import completion

from config import (
    LLM_API_BASE,
    LLM_API_KEY,
    LLM_CUSTOM_PROVIDER,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_PROVIDER,
    LLM_TEMPERATURE,
    LLM_TOP_P,
)


class ProgramGenerator:
    def __init__(self, prompter, temperature=LLM_TEMPERATURE, top_p=LLM_TOP_P):
        self.prompter = [prompter]
        self.temperature = temperature
        self.top_p = top_p

    def add_prompter(self, prompter):
        self.prompter.append(prompter)

    def _extract_message_text(self, message):
        if isinstance(message, dict):
            content = message.get("content")
            reasoning = message.get("reasoning_content")
        else:
            content = getattr(message, "content", None)
            reasoning = getattr(message, "reasoning_content", None)
            if content is None and hasattr(message, "model_dump"):
                dumped = message.model_dump()
                content = dumped.get("content")
                reasoning = reasoning or dumped.get("reasoning_content")

        if content and str(content).strip():
            return str(content)
        if reasoning and str(reasoning).strip():
            return str(reasoning)
        return ""

    def _complete(self, text):
        kwargs = {
            "model": LLM_MODEL,
            "messages": [{"role": "user", "content": text}],
            "api_key": LLM_API_KEY,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": LLM_MAX_TOKENS,
            "timeout": 120,
        }
        if LLM_PROVIDER == "vllm":
            kwargs["api_base"] = LLM_API_BASE
            kwargs["extra_body"] = {"include_reasoning": False}
            if LLM_CUSTOM_PROVIDER:
                kwargs["custom_llm_provider"] = LLM_CUSTOM_PROVIDER
            print(f"LLM request -> {LLM_API_BASE} model={LLM_MODEL}")
        response = completion(**kwargs)
        choice = response.choices[0]
        output_text = self._extract_message_text(choice.message)
        if not output_text.strip():
            print(
                f"LLM returned empty content "
                f"(finish_reason={getattr(choice, 'finish_reason', 'unknown')})"
            )
        return output_text

    def send_text_to_generate(self, text):
        return self._complete(text)

    def send_text_to_chat(self, text):
        return self._complete(text)

    def generate(self, inputs, index=0):
        prompt = self.prompter[index](*inputs)
        exponential_backoff = 1
        empty_retries = 0
        while True:
            try:
                output_text = self._complete(prompt)
                if output_text and output_text.strip():
                    print(f"output_text: {output_text}")
                    return output_text.strip(), None
                empty_retries += 1
                if empty_retries >= 3:
                    print("LLM returned empty output after 3 attempts.")
                    return None, None
                print("LLM returned empty output; retrying...")
                time.sleep(2 * empty_retries)
            except Exception as exc:
                print(f"Request failed: {exc}. Waiting before retrying...")
                time.sleep(16 * exponential_backoff)
                exponential_backoff *= 2
                continue


class ProgramGenerator_openai(ProgramGenerator):
    def __init__(self, prompter, temperature=LLM_TEMPERATURE, top_p=LLM_TOP_P, local=False):
        self.local = local
        if not local:
            super().__init__(prompter, temperature=temperature, top_p=top_p)
        else:
            self.prompter = prompter

    def generate(self, inputs):
        if self.local:
            return inputs, None
        return super().generate(inputs, index=0)
