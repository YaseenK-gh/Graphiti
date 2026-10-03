import os
import subprocess
import sys
import venv

ROOT = os.path.dirname(os.path.abspath(__file__))
ENV = os.path.join(ROOT, ".build-venv")
PYTHON = os.path.join(ENV, "Scripts", "python.exe")


def ensure_env():
    if not os.path.exists(PYTHON):
        venv.create(ENV, system_site_packages=True, with_pip=True)
    check = subprocess.run([PYTHON, "-m", "PyInstaller", "--version"], capture_output=True)
    if check.returncode:
        subprocess.run([PYTHON, "-m", "pip", "install", "pyinstaller"], check=True)


def build():
    ensure_env()
    assets = os.path.join(ROOT, "assets")
    subprocess.run([
        PYTHON, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", "Graphiti",
        "--icon", os.path.join(assets, "icon", "graphiti.ico"),
        "--add-data", f"{assets}{os.pathsep}assets",
        "--distpath", os.path.join(ROOT, "dist"),
        "--workpath", os.path.join(ROOT, "build"),
        "--specpath", os.path.join(ROOT, "build"),
        os.path.join(ROOT, "main.py"),
    ], cwd=ROOT, check=True)
    print(f"Built {os.path.join(ROOT, 'dist', 'Graphiti.exe')}")


if __name__ == "__main__":
    sys.exit(build())
