from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path


ENV_NAME = "embedding-env"
DEFAULT_PORT = 8000


def exe_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def find_project_root() -> Path:
    candidates = [Path.cwd(), exe_dir(), *exe_dir().parents]
    for path in candidates:
        if (
            (path / "main.py").is_file()
            and (path / "config.yaml").is_file()
            and (path / "webapp" / "server.py").is_file()
        ):
            return path
    raise FileNotFoundError(
        "Cannot locate project root. Put this launcher inside the "
        "agentic-study-system directory or its dist subdirectory."
    )


def python_candidates() -> list[Path]:
    override = os.environ.get("AGENTIC_STUDY_PYTHON")
    paths: list[Path] = []
    if override:
        paths.append(Path(override))
    paths.extend(
        [
            Path(r"E:\Anaconda\envs") / ENV_NAME / "python.exe",
            Path.home() / ".conda" / "envs" / ENV_NAME / "python.exe",
        ]
    )
    return paths


def find_env_python() -> Path:
    for path in python_candidates():
        if path.is_file():
            return path
    raise FileNotFoundError(
        f"Cannot find {ENV_NAME} python.exe. Set AGENTIC_STUDY_PYTHON "
        "to the full python.exe path and run the launcher again."
    )


def env_for_python(python_exe: Path) -> dict[str, str]:
    env = os.environ.copy()
    env_root = python_exe.parent
    dll_paths = [
        env_root,
        env_root / "Library" / "bin",
        env_root / "Scripts",
        env_root / "DLLs",
    ]
    env["PATH"] = os.pathsep.join(str(p) for p in dll_paths if p.exists()) + os.pathsep + env.get("PATH", "")
    return env


def port_is_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def wait_and_open(port: int, no_browser: bool) -> None:
    if no_browser:
        return
    url = f"http://127.0.0.1:{port}"
    for _ in range(80):
        try:
            with urllib.request.urlopen(url, timeout=0.5):
                webbrowser.open(url)
                return
        except Exception:
            time.sleep(0.25)
    print(f"Server did not respond yet. Open manually: {url}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="AgenticStudyLauncher",
        description="Launch Agentic Study System from the embedding-env conda environment.",
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Web port, default 8000.")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the browser automatically.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = find_project_root()
    python_exe = find_env_python()
    url = f"http://127.0.0.1:{args.port}"

    print(f"Project: {project_root}")
    print(f"Python:  {python_exe}")
    print(f"URL:     {url}")
    if port_is_open(args.port):
        print(f"Port {args.port} is already in use. If this is the existing app, open {url}.")
        if not args.no_browser:
            webbrowser.open(url)
        return 0

    cmd = [str(python_exe), "main.py", "serve", "--port", str(args.port)]
    opener = threading.Thread(target=wait_and_open, args=(args.port, args.no_browser), daemon=True)
    opener.start()
    proc = subprocess.Popen(cmd, cwd=str(project_root), env=env_for_python(python_exe))
    try:
        return proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
