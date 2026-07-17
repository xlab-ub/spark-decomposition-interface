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
GO2_MUJOCO_ROOT = os.environ.get(
    "SPARK_GO2_MUJOCO_ROOT",
    str(Path(__file__).resolve().parent / "robot" / "unitree_mujoco"),
)
GO2_MUJOCO_SCENE = os.environ.get("SPARK_GO2_MUJOCO_SCENE", "")
GO2_MUJOCO_RENDER_WIDTH = int(os.environ.get("SPARK_GO2_MUJOCO_RENDER_WIDTH", "640"))
GO2_MUJOCO_RENDER_HEIGHT = int(os.environ.get("SPARK_GO2_MUJOCO_RENDER_HEIGHT", "360"))
GO2_MUJOCO_RENDER_DT = float(os.environ.get("SPARK_GO2_MUJOCO_RENDER_DT", "0.04"))
GO2_MUJOCO_SIM_DT = float(os.environ.get("SPARK_GO2_MUJOCO_SIM_DT", "0.005"))
GO2_MUJOCO_HEADLESS = _env_bool("SPARK_GO2_MUJOCO_HEADLESS", True)
GO2_MUJOCO_DETECTION_DT = float(os.environ.get("SPARK_GO2_MUJOCO_DETECTION_DT", "0.2"))
GO2_MUJOCO_FIND_TIMEOUT = float(os.environ.get("SPARK_GO2_MUJOCO_FIND_TIMEOUT", "12.0"))
GO2_MUJOCO_FIND_YAW_STEP = float(os.environ.get("SPARK_GO2_MUJOCO_FIND_YAW_STEP", "0.35"))
GO2_MUJOCO_LINEAR_SPEED = float(os.environ.get("SPARK_GO2_MUJOCO_LINEAR_SPEED", "0.4"))
GO2_MUJOCO_ANGULAR_SPEED = float(os.environ.get("SPARK_GO2_MUJOCO_ANGULAR_SPEED", "1.2"))
VIDEO_STREAM_FPS = float(os.environ.get("SPARK_VIDEO_STREAM_FPS", "20"))
VIDEO_JPEG_QUALITY = int(os.environ.get("SPARK_VIDEO_JPEG_QUALITY", "80"))

LLM_PROVIDER = os.environ.get("SPARK_LLM_PROVIDER", "openai").lower()
LLM_MODEL = os.environ.get(
    "SPARK_LLM_MODEL",
    "gpt-4o-mini" if LLM_PROVIDER == "openai" else "hosted_vllm/openai/gpt-oss-20b",
)


def _resolve_request_model(provider, model):
    if provider != "vllm":
        return model
    if model.startswith("hosted_vllm/"):
        return model.removeprefix("hosted_vllm/")
    return model


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
        hosted_model = model.removeprefix("hosted_vllm/")
        if "/" in hosted_model:
            return hosted_model.split("/", 1)[0]
        return "openai"
    if "/" in model:
        return model.split("/", 1)[0]
    return "openai"


LLM_CUSTOM_PROVIDER = _resolve_custom_llm_provider(LLM_PROVIDER, LLM_MODEL)
LLM_REQUEST_MODEL = _resolve_request_model(LLM_PROVIDER, LLM_MODEL)
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
