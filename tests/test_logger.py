import json
import logging

from akande.logger import basic_config, JSONFormatter


def test_basic_config_creates_file_handler(tmp_path):
    log_file = tmp_path / "test.log"
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    basic_config(
        filename=str(log_file),
        level=logging.DEBUG,
        log_format="%(message)s",
    )

    logging.debug("test message")
    assert log_file.exists()

    # Clean up handlers
    for handler in root.handlers[:]:
        root.removeHandler(handler)


def test_basic_config_adds_console_handler(tmp_path):
    log_file = tmp_path / "test2.log"
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    basic_config(
        filename=str(log_file),
        level=logging.DEBUG,
        log_format="%(message)s",
    )

    handler_types = [type(h).__name__ for h in root.handlers]
    assert "FileHandler" in handler_types
    assert "StreamHandler" in handler_types

    # Clean up handlers
    for handler in root.handlers[:]:
        root.removeHandler(handler)


def test_basic_config_replaces_existing_handlers(tmp_path):
    log_file = tmp_path / "test3.log"
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    # Call twice — should not duplicate handlers
    basic_config(
        filename=str(log_file),
        level=logging.DEBUG,
        log_format="%(message)s",
    )
    basic_config(
        filename=str(log_file),
        level=logging.DEBUG,
        log_format="%(message)s",
    )

    # Should have exactly 2 handlers (file + console)
    assert len(root.handlers) == 2

    # Clean up handlers
    for handler in root.handlers[:]:
        root.removeHandler(handler)


def test_json_formatter_output():
    formatter = JSONFormatter(service="test-service")
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="Test message",
        args=(),
        exc_info=None,
    )
    output = formatter.format(record)
    data = json.loads(output)
    assert data["level"] == "INFO"
    assert data["service"] == "test-service"
    assert data["message"] == "Test message"
    assert "timestamp" in data


def test_json_formatter_includes_correlation_id():
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="Test",
        args=(),
        exc_info=None,
    )
    record.correlation_id = "abc-123"
    output = formatter.format(record)
    data = json.loads(output)
    assert data["correlation_id"] == "abc-123"


def test_json_formatter_includes_event():
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="Test",
        args=(),
        exc_info=None,
    )
    record.event = "Cache:Accessed"
    output = formatter.format(record)
    data = json.loads(output)
    assert data["event"] == "Cache:Accessed"


def test_json_formatter_includes_extra_data():
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="Test",
        args=(),
        exc_info=None,
    )
    record.extra_data = {"key": "value"}
    output = formatter.format(record)
    data = json.loads(output)
    assert data["data"]["key"] == "value"


def test_json_formatter_handles_exception():
    formatter = JSONFormatter()
    try:
        raise ValueError("test error")
    except ValueError:
        import sys

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error occurred",
            args=(),
            exc_info=sys.exc_info(),
        )
    output = formatter.format(record)
    data = json.loads(output)
    assert data["exception"]["type"] == "ValueError"
    assert data["exception"]["message"] == "test error"


def test_file_handler_uses_json_format(tmp_path):
    log_file = tmp_path / "json_test.log"
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    basic_config(
        filename=str(log_file),
        level=logging.DEBUG,
        log_format="%(message)s",
    )

    logging.info("structured test")

    # Clean up handlers to flush
    for handler in root.handlers[:]:
        handler.flush()
        root.removeHandler(handler)

    content = log_file.read_text().strip()
    # File handler should write JSON
    data = json.loads(content)
    assert data["message"] == "structured test"
    assert data["level"] == "INFO"
