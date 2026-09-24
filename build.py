"""
Builds a standalone Streamer Buddy executable with PyInstaller.

    python build.py              one-file build for the current OS
    python build.py --onedir     folder build (starts faster)
    python build.py --console    keep a console window, for debugging

PyInstaller does not cross-compile: run this on Windows to get a
.exe, on Linux to get a Linux binary. The GitHub Actions workflow in
.github/workflows/release.yml builds both on tagged releases.

Most of what follows exists because this app's dependencies hide
things from PyInstaller's static analysis:

  - keyring finds its backends through entry points, which get
    stripped from a frozen app. Without the hidden imports below,
    saved API keys silently stop working in the built version.
  - PyAV ships FFmpeg shared libraries and sounddevice ships
    PortAudio; neither is an `import` PyInstaller can see, so the
    binaries have to be collected explicitly.
  - aiortc's crypto stack (cryptography, pylibsrtp, google-crc32c)
    and aioice's DNS/interface lookups are likewise loaded late.
"""

import sys
import shutil
import argparse
import subprocess
from pathlib import Path


APP_NAME = "StreamerBuddy"
ENTRY_POINT = "main.py"

ROOT = Path(__file__).parent.resolve()


# Imported at runtime in ways PyInstaller can't see.
HIDDEN_IMPORTS = [
    # keyring backend discovery is entry-point based and does not
    # survive freezing; core/credentials.py picks one by platform, so
    # every platform's backend has to be present in the bundle.
    "keyring.backends.Windows",
    "keyring.backends.macOS",
    "keyring.backends.SecretService",
    "keyring.backends.chainer",
    "keyring.backends.fail",
    # Linux SecretService talks D-Bus through these.
    "secretstorage",
    "jeepney",
    "jeepney.io.blocking",
    # aiortc / aioice load these lazily.
    "aioice",
    "dnspython",
    "ifaddr",
    "pylibsrtp",
    "google_crc32c",
]

# Packages whose compiled libraries must be copied in wholesale.
COLLECT_ALL = [
    "av",            # bundles FFmpeg
    "sounddevice",   # bundles PortAudio
    "aiortc",
]


def build(onefile=True, console=False):
    for stale in ("build", "dist"):
        shutil.rmtree(ROOT / stale, ignore_errors=True)

    command = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name", APP_NAME,
        "--onefile" if onefile else "--onedir",
        "--console" if console else "--windowed",
    ]

    for module in HIDDEN_IMPORTS:
        command += ["--hidden-import", module]

    for package in COLLECT_ALL:
        command += ["--collect-all", package]

    command.append(str(ROOT / ENTRY_POINT))

    print("Running:", " ".join(command), "\n")
    subprocess.run(command, check=True, cwd=ROOT)

    produced = sorted(
        path for path in (ROOT / "dist").iterdir()
        if path.is_file() or path.is_dir()
    )

    print("\nBuilt:")
    for path in produced:
        if path.is_file():
            size = path.stat().st_size / 1_000_000
            print(f"  {path}  ({size:.0f} MB)")
        else:
            print(f"  {path}{'/'}")


def main():
    parser = argparse.ArgumentParser(description="Build Streamer Buddy")
    parser.add_argument(
        "--onedir",
        action="store_true",
        help="build a folder instead of a single file (starts faster)",
    )
    parser.add_argument(
        "--console",
        action="store_true",
        help="keep a console window attached, for debugging a build",
    )
    args = parser.parse_args()

    build(onefile=not args.onedir, console=args.console)


if __name__ == "__main__":
    main()
