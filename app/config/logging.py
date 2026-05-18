import os
import sys
from loguru import logger

def setup_logging(level: str = "INFO"):
    os.makedirs("logs", exist_ok=True)
    logger.remove()

    # Stdout avec encodage UTF-8 force (evite erreurs sur Windows avec caracteres russes/francais)
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    logger.add(
        sys.stdout,
        level=level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
    )
    logger.add(
        "logs/job_bot.log",
        rotation="1 day",
        retention="7 days",
        level=level,
        encoding="utf-8",
    )
