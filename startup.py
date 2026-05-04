"""One-shot launcher: install deps, prep env, start LeadFinder, open browser."""

import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
REQS = ROOT / "requirements.txt"
ENV = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"


def run(cmd, **kw):
    print(f"\n>>> {' '.join(cmd)}")
    return subprocess.run(cmd, check=True, **kw)


def pip_install():
    if not REQS.exists():
        sys.exit(f"missing {REQS}")
    run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
    run([sys.executable, "-m", "pip", "install", "-r", str(REQS)])


def playwright_chromium():
    try:
        run([sys.executable, "-m", "playwright", "install", "chromium"])
    except subprocess.CalledProcessError as e:
        print(f"playwright install failed ({e}); stealth fetcher may not work")


def ensure_env():
    if ENV.exists():
        return
    if ENV_EXAMPLE.exists():
        shutil.copyfile(ENV_EXAMPLE, ENV)
        print(f"created {ENV} from example — add GROQ_API_KEY before running searches")
    else:
        print("no .env or .env.example found; continuing")


def get_url():
    host = os.getenv("HOST", "127.0.0.1")
    port = os.getenv("PORT", "8000")
    if ENV.exists():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("HOST="):
                host = line.split("=", 1)[1].strip()
            elif line.startswith("PORT="):
                port = line.split("=", 1)[1].strip()
    if host in ("0.0.0.0", "::"):
        host = "127.0.0.1"
    return f"http://{host}:{port}"


def open_browser_later(url, delay=2.5):
    def _open():
        time.sleep(delay)
        try:
            webbrowser.open(url)
        except Exception as e:
            print(f"browser open failed: {e}")
    threading.Thread(target=_open, daemon=True).start()


def start_server():
    url = get_url()
    print(f"\n=== LeadFinder starting at {url} ===\nCtrl+C to stop.\n")
    open_browser_later(url)
    os.chdir(ROOT)
    subprocess.run([sys.executable, str(ROOT / "main.py")])


def main():
    print("[1/3] installing python deps")
    pip_install()
    print("[2/3] installing playwright chromium")
    playwright_chromium()
    print("[3/3] preparing .env")
    ensure_env()
    start_server()


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        sys.exit(f"step failed: {e}")
    except KeyboardInterrupt:
        print("\nstopped.")
