"""Start the local prototype. Run `python run.py --help` for options."""
import argparse
import os
from pathlib import Path


def load_local_env():
    path = Path(__file__).resolve().parent / ".env"
    if path.is_file():
        for line in path.read_text("utf-8-sig").splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            key, separator, value = line.partition("=")
            if separator and key.strip().startswith("HM_"):
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="无靶标自建房变形监测系统 · 本地研究服务")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    load_local_env()
    import uvicorn
    uvicorn.run("backend.app:app", host=args.host, port=args.port, reload=args.reload,
                app_dir=str(Path(__file__).resolve().parent))
