"""
PyInstaller entry point for the Tax App.

Handles frozen-bundle path resolution and auto-opens the browser.
"""

import sys
import os
import threading
import webbrowser

# When running from a PyInstaller bundle, sys._MEIPASS points to the
# temporary directory where bundled files are extracted.  We need to
# set the working directory there so that relative imports of data/
# and templates/ work correctly.
if getattr(sys, 'frozen', False):
    os.chdir(sys._MEIPASS)

# Import the Flask app *after* adjusting paths so that web_app.py
# picks up the correct template_folder.
from web_app import app  # noqa: E402


def open_browser():
    """Open the default browser after a short delay to let Flask start."""
    import time
    time.sleep(1.5)
    webbrowser.open('http://localhost:5000')


if __name__ == '__main__':
    threading.Thread(target=open_browser, daemon=True).start()
    print('Starting Tax App — opening browser to http://localhost:5000')
    print('Press Ctrl+C to quit.')
    app.run(debug=False, port=5000)
