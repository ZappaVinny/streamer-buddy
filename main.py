"""
Entry point.

    python main.py              launches the UI
    python main.py --headless   runs the old CLI behaviour

Headless exists so the engine can be exercised without a display, and
is the regression check that core/ still works on its own.
"""

import sys
import time
import argparse

from core.console import ConsoleSink
from core.runtime import Runtime
from core.settings import Settings


def run_headless():
    settings = Settings.load()
    runtime = Runtime(settings, ConsoleSink(settings))

    runtime.start()
    runtime.connect()

    print("Connecting... Ctrl+C to quit.")

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print()
    finally:
        runtime.shutdown()


def run_ui():
    from ui.app import App

    App().run()


def main():
    parser = argparse.ArgumentParser(description="Stream Buddy")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="run without the UI, logging to the terminal"
    )
    args = parser.parse_args()

    if args.headless:
        run_headless()
    else:
        run_ui()


if __name__ == "__main__":
    sys.exit(main())
