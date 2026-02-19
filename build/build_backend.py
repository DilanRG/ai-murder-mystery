"""
PyInstaller build script for the Python backend.
Bundles the FastAPI server + ChromaDB + all assets into a single executable.
"""
import os
import subprocess
import sys
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build" / "_pybuild"

def build():
    """Build the backend into a standalone executable using PyInstaller."""
    print("=" * 60)
    print("  Building AI Murder Mystery — Python Backend")
    print("=" * 60)

    # Ensure PyInstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # Collect data files
    datas = [
        (str(BACKEND_DIR / "characters"), "characters"),
        (str(BACKEND_DIR / "config" / "sampler_presets"), os.path.join("config", "sampler_presets")),
        (str(BACKEND_DIR / "config" / "instruct_presets"), os.path.join("config", "instruct_presets")),
    ]

    # Include .env.example
    env_example = BACKEND_DIR / ".env.example"
    if env_example.exists():
        datas.append((str(env_example), "."))

    # Build the datas argument
    datas_args = []
    for src, dest in datas:
        datas_args.extend(["--add-data", f"{src}{os.pathsep}{dest}"])

    # Hidden imports that PyInstaller might miss
    hidden_imports = [
        "chromadb",
        "chromadb.config",
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "httpx",
        "jinja2",
        "tiktoken",
    ]

    hidden_args = []
    for hi in hidden_imports:
        hidden_args.extend(["--hidden-import", hi])

    # PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--name", "murder-mystery-backend",
        "--distpath", str(DIST_DIR / "backend"),
        "--workpath", str(BUILD_DIR),
        "--specpath", str(BUILD_DIR),
        *datas_args,
        *hidden_args,
        "--collect-submodules", "chromadb",
        "--collect-submodules", "uvicorn",
        str(BACKEND_DIR / "main.py"),
    ]

    print("\nRunning PyInstaller...")
    print(f"  Entry: {BACKEND_DIR / 'main.py'}")
    print(f"  Output: {DIST_DIR / 'backend'}")
    print()

    result = subprocess.run(cmd, cwd=str(BACKEND_DIR))

    if result.returncode == 0:
        print("\n✅ Backend build successful!")
        print(f"   Executable: {DIST_DIR / 'backend' / 'murder-mystery-backend'}")
    else:
        print("\n❌ Backend build failed!")
        sys.exit(1)


if __name__ == "__main__":
    build()
