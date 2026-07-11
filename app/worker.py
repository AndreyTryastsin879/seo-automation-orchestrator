from app.interfaces.worker.runner import run_worker
from app.core.logging import configure_logging


if __name__ == "__main__":
    configure_logging(service="worker")
    run_worker()
