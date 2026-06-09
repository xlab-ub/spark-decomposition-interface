import os
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


def _env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes")


RASA_TEST = _env_bool("SPARK_RASA_TEST", True)
WEB_SERVER = _env_bool("SPARK_WEB_SERVER", True)
TTS_ON = _env_bool("SPARK_TTS_ON", False)
DATABASE_ON = _env_bool("SPARK_DATABASE_ON", False)
FIND_SIMILAR = _env_bool("SPARK_FIND_SIMILAR", False)
GPT_WITH_LOCAL_LLM = _env_bool("SPARK_GPT_WITH_LOCAL_LLM", True)

ROBOT_BACKEND = os.environ.get("SPARK_ROBOT_BACKEND", "noop").lower()

LLM_PROVIDER = os.environ.get("SPARK_LLM_PROVIDER", "openai").lower()
LLM_MODEL = os.environ.get(
    "SPARK_LLM_MODEL",
    "gpt-4o-mini" if LLM_PROVIDER == "openai" else "hosted_vllm/openai/gpt-oss-20b",
)
def _normalize_api_base(api_base):
    api_base = (api_base or "").rstrip("/")
    if not api_base:
        return api_base
    if not api_base.endswith("/v1"):
        api_base = f"{api_base}/v1"
    return api_base


LLM_API_BASE = _normalize_api_base(
    os.environ.get(
        "SPARK_LLM_API_BASE",
        "http://localhost:8000/v1" if LLM_PROVIDER == "vllm" else "",
    )
)

if LLM_PROVIDER == "vllm" and LLM_API_BASE:
    os.environ.setdefault("HOSTED_VLLM_API_BASE", LLM_API_BASE)


def _resolve_custom_llm_provider(provider, model):
    if provider != "vllm":
        return None
    if model.startswith("hosted_vllm/"):
        return None
    if "/" in model:
        return model.split("/", 1)[0]
    return "openai"


LLM_CUSTOM_PROVIDER = _resolve_custom_llm_provider(LLM_PROVIDER, LLM_MODEL)
LLM_API_KEY = os.environ.get(
    "SPARK_LLM_API_KEY",
    os.environ.get("OPENAI_API_KEY", "EMPTY"),
)
LLM_TEMPERATURE = float(os.environ.get("SPARK_LLM_TEMPERATURE", "0.5"))
LLM_TOP_P = float(os.environ.get("SPARK_LLM_TOP_P", "0.9"))
LLM_MAX_TOKENS = int(os.environ.get("SPARK_LLM_MAX_TOKENS", "2048"))

RASA_SERVER_URL = os.environ.get("RASA_SERVER_URL", "http://localhost:15005")
WEB_SERVER_PORT = int(os.environ.get("WEB_SERVER_PORT", "9999"))
DUCKLING_URL = os.environ.get("DUCKLING_URL", "http://localhost:19999")

STT_URL = os.environ.get("SPARK_STT_URL", "http://localhost:9009/transcribe")
TTS_URL = os.environ.get("SPARK_TTS_URL", "http://localhost:19099/synthesize")

DATABASE_USER = os.environ.get("SPARK_DATABASE_USER", "default_user")

_custom_provider_log = LLM_CUSTOM_PROVIDER or "auto"
print(
    f"Spark LLM config: provider={LLM_PROVIDER}, model={LLM_MODEL}, "
    f"api_base={LLM_API_BASE if LLM_PROVIDER == 'vllm' else 'default'}, "
    f"custom_llm_provider={_custom_provider_log}"
)
