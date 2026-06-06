"""HTTP application entrypoint."""

from app.interfaces.api import create_app


app = create_app()


def main():
    """Return the configured FastAPI application."""

    return app
