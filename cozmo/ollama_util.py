import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

_INSTALLED_CACHE: tuple[float, list[str]] | None = None


def _fetch_models(ollama_url: str, timeout: float) -> list[str]:
    try:
        req = urllib.request.Request(f"{ollama_url}/api/tags")
        resp = urllib.request.urlopen(req, timeout=timeout)
        data = json.loads(resp.read())
        return sorted([m["name"] for m in data.get("models", [])])
    except Exception:
        return []


def is_ollama_running(timeout: float = 2) -> bool:
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        urllib.request.urlopen(req, timeout=timeout)
        return True
    except Exception:
        return False


def get_ollama_models(ollama_url: str = "http://localhost:11434", timeout: float = 5) -> list[str]:
    """Fetch installed models from Ollama. Results cached for 30s."""
    global _INSTALLED_CACHE
    now = time.time()
    if _INSTALLED_CACHE is not None and (now - _INSTALLED_CACHE[0]) < 30:
        return _INSTALLED_CACHE[1]
    models = _fetch_models(ollama_url, timeout)
    _INSTALLED_CACHE = (now, models)
    return models


def pick_model(installed: list[str], role: str) -> str:
    """Pick best available installed model for given role.

    Roles: chat, coder, vision, research, classifier, router, embedding
    Falls back to first installed model or an empty-model placeholder.
    """
    if not installed:
        return ""

    name_lower = {m: m.lower().replace("-", "").replace("_", "").replace(":", "") for m in installed}

    role_keywords = {
        "vision":      ["vl", "vision", "llava", "cogvlm", "idefics", "minicpm5"],
        "coder":       ["coder", "deepseek", "starcoder", "codestral", "codeqwen",
                        "codegemma", "wizardcoder", "phind"],
        "classifier":  ["minicpm5", "qwen25", "tinyllama", "smollm", "gemma2:2b",
                        "phi3:mini", "llama32:1b", "qwen3:1.7b", "qwen3:0.6b"],
        "router":      ["minicpm5", "qwen25", "tinyllama", "smollm", "gemma2:2b",
                        "phi3:mini", "llama32:1b", "qwen3:1.7b", "qwen3:0.6b"],
        "embedding":   ["nomicembed", "mxbaiembed", "snowflake", "bge"],
        "chat":        [],
        "research":    [],
        "agent":       [],
    }

    keywords = role_keywords.get(role, [])
    best = None
    best_score = -1

    for idx, m in enumerate(installed):
        score = 0
        # Prefer larger models for chat/research/agent
        if role in ("chat", "research", "agent"):
            if "3:" in m or "3.1:" in m or "3.2:" in m:
                score += 10
            for prefix in ("70b", "72b", "120b", "123b", "671b", "400b", "405b", "200b", "180b"):
                if prefix in m.lower():
                    score += 30
                    break
            for prefix in ("32b", "34b", "35b", "30b"):
                if prefix in m.lower():
                    score += 20
                    break
            for prefix in ("14b", "16b", "20b", "21b", "24b", "27b"):
                if prefix in m.lower():
                    score += 10
                    break
        # Keyword matches
        for kw in keywords:
            if kw in name_lower[m]:
                score += 15
        # Penalize quantized for classifier/router (prefer smaller)
        if role in ("classifier", "router") and any(p in m.lower() for p in ("70b", "72b", "32b", "34b")):
            score -= 10

        if score > best_score or (score == best_score and idx < len(installed)):
            best_score = score
            best = m

    return best or installed[0]


def start_ollama() -> subprocess.Popen | None:
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        return subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **kwargs,
        )
    except FileNotFoundError:
        print("Warning: 'ollama' not found on PATH. Start Ollama manually.")
        return None


def stop_ollama(proc: subprocess.Popen | None):
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def wait_for_ollama(max_wait: float = 10) -> bool:
    for _ in range(int(max_wait)):
        if is_ollama_running():
            return True
        time.sleep(1)
    return False


_QUALITY_RANK = [
    "fp16", "bf16",
    "q8_0",
    "q6_K",
    "q5_K_M", "q5_0", "q5_K_S",
    "q4_K_M", "q4_0", "q4_K_S",
    "q3_K_L", "q3_K_M", "q3_K_S",
    "q2_K",
]


def resolve_minicpm5(ollama_url: str = "http://localhost:11434", timeout: float = 3) -> str:
    """Pick the best available MiniCPM5 variant from Ollama's model list."""
    installed = _fetch_models(ollama_url, timeout)
    candidates = [m for m in installed if "minicpm5" in m.lower()]
    if not candidates:
        # Fallback: pick any small model for lightweight mode
        small_candidates = [m for m in installed if any(
            p in m.lower() for p in ("1b", "1.7b", "2b", "3b", "4b"))]
        if small_candidates:
            return pick_model(small_candidates, "chat")
        return pick_model(installed, "chat") if installed else ""

    def sort_key(name: str):
        for rank, tag in enumerate(_QUALITY_RANK):
            if tag in name:
                return rank
        return len(_QUALITY_RANK)
    candidates.sort(key=sort_key)
    return candidates[0]
