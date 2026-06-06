"""Telegram bot entrypoint."""

from app.interfaces.bot.polling import main as run_polling

def main() -> None:
    """Run the Telegram bot in local polling mode."""

    run_polling()


if __name__ == "__main__":
    main()
