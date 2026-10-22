"""WSGI 進入點。

開發：  python wsgi.py
正式：  waitress-serve --port=8000 wsgi:app
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app.run(host="127.0.0.1", port=port, debug=app.config.get("DEBUG", False))
