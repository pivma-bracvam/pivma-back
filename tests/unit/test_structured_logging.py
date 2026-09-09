import json
import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from pivma.core.logging import (
    get_ai_logger,
    get_operational_logger,
    setup_logging,
)


def test_setup_logging_configures_rotating_handlers(tmp_path: Path):
    setup_logging()

    op_logger = logging.getLogger('pivma.operational')
    ai_logger = logging.getLogger('pivma.ai')

    assert len(op_logger.handlers) >= 1
    assert len(ai_logger.handlers) >= 1

    op_handler = next(
        h
        for h in op_logger.handlers
        if isinstance(h, TimedRotatingFileHandler)
    )
    ai_handler = next(
        h
        for h in ai_logger.handlers
        if isinstance(h, TimedRotatingFileHandler)
    )

    expected_backups = 7
    assert op_handler.backupCount == expected_backups
    assert ai_handler.backupCount == expected_backups
    assert op_handler.when == 'MIDNIGHT'
    assert ai_handler.when == 'MIDNIGHT'


def test_operational_logger_emits_valid_jsonl():
    setup_logging()
    logger = get_operational_logger()

    expected_duration = 42.5
    logger.info(
        'test_event',
        correlation_id='corr-123',
        status='SUCCESS',
        duration_ms=expected_duration,
    )

    app_log = Path('logs/application/events.jsonl')
    assert app_log.exists()

    with open(app_log, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    assert len(lines) >= 1
    last_line = json.loads(lines[-1])
    assert last_line['event'] == 'test_event'
    assert last_line['correlation_id'] == 'corr-123'
    assert last_line['status'] == 'SUCCESS'
    assert last_line['duration_ms'] == expected_duration
    assert 'timestamp' in last_line
    assert last_line['level'] == 'info'


def test_ai_logger_emits_valid_jsonl():
    setup_logging()
    logger = get_ai_logger()

    expected_duration = 15.2
    expected_tokens = 120
    logger.info(
        'ai_step_completed',
        correlation_id='corr-ai-456',
        step='context_extraction',
        step_duration_ms=expected_duration,
        tokens_used=expected_tokens,
    )

    ai_log = Path('logs/ai/ai_steps.jsonl')
    assert ai_log.exists()

    with open(ai_log, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    assert len(lines) >= 1
    last_line = json.loads(lines[-1])
    assert last_line['event'] == 'ai_step_completed'
    assert last_line['correlation_id'] == 'corr-ai-456'
    assert last_line['step'] == 'context_extraction'
    assert last_line['step_duration_ms'] == expected_duration
    assert last_line['tokens_used'] == expected_tokens
    assert 'timestamp' in last_line


def test_handler_rollover_retention_limit(tmp_path: Path):
    """Verifica se o TimedRotatingFileHandler respeita o backupCount."""
    log_file = tmp_path / 'test_retention.jsonl'
    backup_count = 7
    handler = TimedRotatingFileHandler(
        filename=str(log_file),
        when='S',
        interval=1,
        backupCount=backup_count,
        encoding='utf-8',
    )
    handler.setFormatter(logging.Formatter('%(message)s'))

    test_logger = logging.getLogger('test_retention')
    test_logger.setLevel(logging.INFO)
    test_logger.addHandler(handler)

    iterations = 10
    for i in range(iterations):
        test_logger.info(f'record-{i}')
        handler.doRollover()

    backups = list(tmp_path.glob('test_retention.jsonl*'))
    max_expected = backup_count + 1
    assert len(backups) <= max_expected
    handler.close()
