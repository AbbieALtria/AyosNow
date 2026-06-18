import os
import sys

from gunicorn.app.wsgiapp import run


if __name__ == "__main__":
    port = os.getenv("PORT", "8000")
    workers = os.getenv("WEB_CONCURRENCY", "3")
    sys.argv = [
        "gunicorn",
        "ayosnow.wsgi:application",
        "--bind",
        f"0.0.0.0:{port}",
        "--workers",
        workers,
    ]
    run()
