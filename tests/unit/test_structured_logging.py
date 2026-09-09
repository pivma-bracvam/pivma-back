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
    events = [json.loads(line) for line in lines]
    matching = [e for e in events if e.get('correlation_id') == 'corr-123']
    assert len(matching) >= 1
    target = matching[-1]
    assert target['event'] == 'test_event'
    assert target['correlation_id'] == 'corr-123'
    assert target['status'] == 'SUCCESS'
    assert target['duration_ms'] == expected_duration
    assert 'timestamp' in target
    assert target['level'] == 'info'


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
    events = [json.loads(line) for line in lines]
    matching = [e for e in events if e.get('correlation_id') == 'corr-ai-456']
    assert len(matching) >= 1
    target = matching[-1]
    assert target['event'] == 'ai_step_completed'
    assert target['correlation_id'] == 'corr-ai-456'
    assert target['step'] == 'context_extraction'
    assert target['step_duration_ms'] == expected_duration
    assert target['tokens_used'] == expected_tokens
    assert 'timestamp' in target


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
