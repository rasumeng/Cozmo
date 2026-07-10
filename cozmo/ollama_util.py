import json
import subprocess
import sys
import time
import urllib.error
import urllib.request


def is_ollama_running(timeout: float = 2) -> bool:
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        urllib.request.urlopen(req, timeout=timeout)
        return True
    except Exception:
        return False


def get_ollama_models(timeout: float = 5) -> list[str]:
    try:
        resp = urllib.request.urlopen("http://localhost:11434/api/tags", timeout=timeout)
        data = json.loads(resp.read())
        return sorted([m["name"] for m in data.get("models", [])])
    except Exception:
        return []


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
    try:
        req = urllib.request.Request(f"{ollama_url}/api/tags")
        resp = urllib.request.urlopen(req, timeout=timeout)
        data = json.loads(resp.read())
        candidates = [m["name"] for m in data.get("models", []) if "minicpm5" in m["name"].lower()]
    except Exception:
        candidates = []
    if not candidates:
        return "openbmb/minicpm5"

    def sort_key(name: str):
        for rank, tag in enumerate(_QUALITY_RANK):
            if tag in name:
                return rank
        return len(_QUALITY_RANK)  # unknown tags go last
    candidates.sort(key=sort_key)
    return candidates[0]
