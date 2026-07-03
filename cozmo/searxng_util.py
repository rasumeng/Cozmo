"""SearXNG auto-setup and management utilities."""

import subprocess
import sys
import time
import urllib.request
import urllib.error


SEARXNG_CONTAINER = "cozmo-searxng"
SEARXNG_IMAGE = "searxng/searxng"
SEARXNG_PORT = 8080


def is_docker_available() -> bool:
    """Check if Docker is available on the system."""
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def is_searxng_running(port: int = SEARXNG_PORT, timeout: float = 2) -> bool:
    """Check if SearXNG is running on the specified port."""
    try:
        req = urllib.request.Request(f"http://localhost:{port}/search?q=test&format=json")
        urllib.request.urlopen(req, timeout=timeout)
        return True
    except Exception:
        return False


def start_searxng(port: int = SEARXNG_PORT) -> bool:
    """Start SearXNG container if Docker is available."""
    if not is_docker_available():
        print("Docker not available. SearXNG will not be auto-started.")
        print("Install Docker or use DuckDuckGo backend instead.")
        return False

    if is_searxng_running(port):
        print(f"SearXNG already running on port {port}")
        return True

    print(f"Starting SearXNG on port {port}...")

    try:
        subprocess.run(
            [
                "docker", "run", "-d",
                "--name", SEARXNG_CONTAINER,
                "-p", f"{port}:8080",
                "-e", "SEARXNG_BASE_URL=http://localhost:8080/",
                "--restart", "unless-stopped",
                SEARXNG_IMAGE,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        for _ in range(10):
            time.sleep(1)
            if is_searxng_running(port):
                print(f"SearXNG started successfully on port {port}")
                return True

        print("SearXNG started but may not be ready yet. Check with: docker logs cozmo-searxng")
        return True
    except Exception as e:
        print(f"Failed to start SearXNG: {e}")
        return False


def stop_searxng():
    """Stop SearXNG container."""
    try:
        subprocess.run(
            ["docker", "stop", SEARXNG_CONTAINER],
            capture_output=True,
            text=True,
            timeout=10,
        )
        subprocess.run(
            ["docker", "rm", SEARXNG_CONTAINER],
            capture_output=True,
            text=True,
            timeout=10,
        )
        print("SearXNG stopped and removed.")
    except Exception as e:
        print(f"Error stopping SearXNG: {e}")


def get_searxng_status() -> dict:
    """Get SearXNG status information."""
    docker_available = is_docker_available()
    running = is_searxng_running() if docker_available else False

    return {
        "docker_available": docker_available,
        "running": running,
        "url": f"http://localhost:{SEARXNG_PORT}" if running else None,
        "container": SEARXNG_CONTAINER,
    }


def ensure_searxng(port: int = SEARXNG_PORT) -> str:
    """Ensure SearXNG is running, auto-start if possible. Returns backend URL or empty string."""
    if is_searxng_running(port):
        return f"http://localhost:{port}"

    if is_docker_available():
        if start_searxng(port):
            return f"http://localhost:{port}"

    return ""
