import logging
import threading
from pathlib import Path

from config import Config

logger = logging.getLogger(__name__)
_llm = None
_load_lock = threading.Lock()
_gen_lock = threading.Lock()  # llama.cpp contexts are not thread-safe


class LLMError(Exception):
    pass


def ensure_model() -> Path:
    """Return the local GGUF path, downloading it from Hugging Face on first use."""
    path = Path(Config.MODEL_DIR) / Config.QWEN_FILE
    if path.exists():
        return path
    try:
        from huggingface_hub import hf_hub_download

        Path(Config.MODEL_DIR).mkdir(parents=True, exist_ok=True)
        return Path(hf_hub_download(repo_id=Config.QWEN_REPO, filename=Config.QWEN_FILE,
                                    local_dir=str(Config.MODEL_DIR), token=Config.HF_TOKEN or None))
    except Exception:
        logger.exception("Model download failed")
        raise LLMError("Could not download the Qwen model. Check your internet connection and try again.")


def _get_llm():
    global _llm
    if _llm is None:
        with _load_lock:
            if _llm is None:
                model_path = ensure_model()
                try:
                    from llama_cpp import Llama

                    kwargs = {"model_path": str(model_path), "n_ctx": Config.LLM_CONTEXT, "verbose": False}
                    if Config.LLM_THREADS > 0:
                        kwargs["n_threads"] = Config.LLM_THREADS
                    _llm = Llama(**kwargs)
                except Exception:
                    logger.exception("Model load failed")
                    raise LLMError("Could not load the Qwen model. The file may be corrupted; delete it and retry.")
    return _llm


def generate(messages: list[dict], temperature: float | None = None, max_tokens: int | None = None) -> str:
    llm = _get_llm()
    try:
        with _gen_lock:
            out = llm.create_chat_completion(
                messages=messages,
                temperature=Config.LLM_TEMPERATURE if temperature is None else temperature,
                max_tokens=max_tokens or Config.LLM_MAX_TOKENS,
            )
        return out["choices"][0]["message"]["content"].strip()
    except Exception:
        logger.exception("Generation failed")
        raise LLMError("The model failed to generate a response. Try a shorter question.")
