from __future__ import annotations

import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"
MIN_PYTHON = (3, 11)


def main() -> int:
    if sys.version_info < MIN_PYTHON:
        print(
            "MARA requires Python 3.11 or newer. "
            f"You are running Python {sys.version_info.major}.{sys.version_info.minor}."
        )
        return 1

    print("MARA local launcher")
    ensure_venv()
    python = venv_python()
    run([str(python), "-m", "pip", "install", "--upgrade", "pip"])
    run([str(python), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")])
    ensure_env_file()
    ensure_local_folders()

    print("\nMARA is starting...")
    print("App:     http://127.0.0.1:8000/")
    print("Swagger: http://127.0.0.1:8000/docs")
    print("Health:  http://127.0.0.1:8000/health\n")
    run(
        [
            str(python),
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
            "--reload",
        ],
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    return 0


def ensure_venv() -> None:
    if VENV_DIR.exists():
        print("Using existing .venv")
        return
    print("Creating .venv")
    venv.EnvBuilder(with_pip=True).create(VENV_DIR)


def venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def ensure_env_file() -> None:
    env_file = ROOT / ".env"
    example = ROOT / ".env.example"
    if env_file.exists():
        print("Using existing .env")
        return
    if not example.exists():
        print(".env.example is missing; skipping .env creation")
        return
    shutil.copyfile(example, env_file)
    print("Created .env from .env.example")


def ensure_local_folders() -> None:
    folders = [
        ROOT / "data",
        ROOT / "uploads",
        ROOT / "vectorstore",
        ROOT / "app" / "storage",
        ROOT / "app" / "storage" / "uploads",
        ROOT / "app" / "storage" / "chroma",
    ]
    for folder in folders:
        folder.mkdir(parents=True, exist_ok=True)

    registry_files = [
        ROOT / "data" / "documents.json",
        ROOT / "app" / "storage" / "documents.json",
    ]
    for registry in registry_files:
        if not registry.exists():
            registry.write_text('{"documents": []}', encoding="utf-8")

    print("Local storage folders are ready")


def run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    print(f"$ {' '.join(command)}")
    subprocess.check_call(command, cwd=ROOT, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
