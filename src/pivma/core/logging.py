import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import structlog

LOGS_DIR = Path(__file__).resolve().parents[3] / "logs"
APP_LOGS_DIR = LOGS_DIR / "application"
AI_LOGS_DIR = LOGS_DIR / "ai"


def _ensure_dirs() -> None:
    APP_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    AI_LOGS_DIR.mkdir(parents=True, exist_ok=True)


def setup_logging() -> None:
    """Configura logging padrão com structlog e rotação de 7 dias."""
    _ensure_dirs()

    # Processadores padrão do structlog para formatação JSONL limpa
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ]

    structlog.configure(
        processors=shared_processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = logging.Formatter("%(message)s")

    # Handler do Índice Operacional (logs/application/)
    app_log_file = APP_LOGS_DIR / "events.jsonl"
    app_handler = TimedRotatingFileHandler(
        filename=str(app_log_file),
        when="midnight",
        interval=1,
        backupCount=7,
        encoding="utf-8",
    )
    app_handler.setFormatter(formatter)
    app_handler.setLevel(logging.INFO)

    app_logger = logging.getLogger("pivma.operational")
    app_logger.setLevel(logging.INFO)
    if not app_logger.handlers:
        app_logger.addHandler(app_handler)
    app_logger.propagate = False

    # Handler do Log Granular de IA (logs/ai/)
    ai_log_file = AI_LOGS_DIR / "ai_steps.jsonl"
    ai_handler = TimedRotatingFileHandler(
        filename=str(ai_log_file),
        when="midnight",
        interval=1,
        backupCount=7,
        encoding="utf-8",
    )
    ai_handler.setFormatter(formatter)
    ai_handler.setLevel(logging.INFO)

    ai_logger = logging.getLogger("pivma.ai")
    ai_logger.setLevel(logging.INFO)
    if not ai_logger.handlers:
        ai_logger.addHandler(ai_handler)
    ai_logger.propagate = False


def get_operational_logger() -> structlog.stdlib.BoundLogger:
    return structlog.wrap_logger(logging.getLogger("pivma.operational"))


def get_ai_logger() -> structlog.stdlib.BoundLogger:
    return structlog.wrap_logger(logging.getLogger("pivma.ai"))
