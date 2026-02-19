"""
Unified build script — builds backend (PyInstaller) then frontend (Electron).
Run from the project root: python build/build.py
"""
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
BUILD_DIR = PROJECT_ROOT / "build"


def build_backend():
    """Build the Python backend with PyInstaller."""
    print("\n" + "=" * 60)
    print("  Step 1: Building Python Backend (PyInstaller)")
    print("=" * 60)
    result = subprocess.run(
        [sys.executable, str(BUILD_DIR / "build_backend.py")],
        cwd=str(BACKEND_DIR),
    )
    if result.returncode != 0:
        print("❌ Backend build failed!")
        sys.exit(1)


def build_frontend(platform=None):
    """Build the Electron frontend with electron-builder."""
    print("\n" + "=" * 60)
    print("  Step 2: Building Electron Frontend")
    print("=" * 60)

    # Ensure node_modules exist
    if not (FRONTEND_DIR / "node_modules").exists():
        print("Installing npm dependencies...")
        subprocess.check_call(["npm", "install"], cwd=str(FRONTEND_DIR), shell=True)

    cmd = ["npx", "electron-builder", "--config", str(BUILD_DIR / "electron-builder.yml")]
    if platform:
        cmd.append(f"--{platform}")

    result = subprocess.run(cmd, cwd=str(FRONTEND_DIR), shell=True)
    if result.returncode != 0:
        print("❌ Frontend build failed!")
        sys.exit(1)

    print("\n✅ Build complete!")
    print(f"   Output: {PROJECT_ROOT / 'dist' / 'electron'}")


if __name__ == "__main__":
    platform = None
    if len(sys.argv) > 1:
        platform = sys.argv[1]  # win, mac, linux

    build_backend()
    build_frontend(platform)
