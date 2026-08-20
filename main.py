"""Run both line_chat service and camera posture detection in one command.

This module starts the Flask relay service from line_chat.py in a background
thread, then starts camera.py in the main thread so both components run
together in a single process.

Usage:
  set LINE_ACCESS_TOKEN=<LINE channel access token>
  set LINE_TARGET_ID=<LINE user/group id>
  set LINE_CHAT_HOST=http://127.0.0.1:5000
  python main.py
"""

import os
import threading
import time


def run_line_chat():
    """Start the line_chat Flask service in a background thread."""
    # Import here so environment variables are available before the service starts.
    from line_chat import app

    # Choose host and port from environment, default to local host on port 5000.
    host = os.environ.get("LINE_CHAT_HOST", "127.0.0.1")
    port = int(os.environ.get("LINE_CHAT_PORT", 5000))

    print(f"Starting line_chat service on {host}:{port}...")

    # Run Flask app in threaded mode. use_reloader=False avoids starting two processes.
    app.run(host=host, port=port, threaded=True, use_reloader=False)


def main():
    """Start the relay service first, then start the camera app."""
    # Start the Flask relay service in a background daemon thread.
    # Daemon thread means it will exit when the main program exits.
    thread = threading.Thread(target=run_line_chat, daemon=True)
    thread.start()

    # Give the Flask service a short moment to open its TCP port before camera.py connects.
    # If the service startup takes longer, increase this value slightly.
    time.sleep(1)

    print("Starting camera posture detector...")

    # Import camera.py after the Flask service has started. camera.py contains the main loop.
    # The import runs the module code immediately, so it begins the posture detector.
    import camera  # noqa: F401


if __name__ == "__main__":
    main()
