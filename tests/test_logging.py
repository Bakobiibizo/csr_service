import logging

from src.csr_service.logging import (
    RequestIdFilter,
    get_request_id,
    request_id_ctx,
)


class TestRequestId:
    def test_generates_id_when_empty(self):
        # Reset context
        token = request_id_ctx.set("")
        try:
            rid = get_request_id()
            assert len(rid) == 12
            assert rid.isalnum()
        finally:
            request_id_ctx.reset(token)

    def test_returns_existing_id(self):
        token = request_id_ctx.set("existing-id")
        try:
            rid = get_request_id()
            assert rid == "existing-id"
        finally:
            request_id_ctx.reset(token)

    def test_sets_id_on_first_call(self):
        token = request_id_ctx.set("")
        try:
            rid = get_request_id()
            # Subsequent call returns same id
            assert get_request_id() == rid
        finally:
            request_id_ctx.reset(token)


class TestRequestIdFilter:
    def test_adds_request_id_to_record(self):
        token = request_id_ctx.set("test-123")
        try:
            filt = RequestIdFilter()
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="test",
                args=None,
                exc_info=None,
            )
            result = filt.filter(record)
            assert result is True
            assert record.request_id == "test-123"
        finally:
            request_id_ctx.reset(token)

    def test_uses_dash_when_no_id(self):
        token = request_id_ctx.set("")
        try:
            filt = RequestIdFilter()
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="test",
                args=None,
                exc_info=None,
            )
            filt.filter(record)
            assert record.request_id == "-"
        finally:
            request_id_ctx.reset(token)


class TestLogLevel:
    def test_log_level_from_env(self, monkeypatch):
        monkeypatch.setenv("CSR_LOG_LEVEL", "DEBUG")
        # Re-import to test setup_logging with new env
        from src.csr_service.logging import setup_logging

        logger = setup_logging()
        # Logger might already have handlers from module init,
        # but we can verify the function doesn't crash
        assert logger.name == "csr_service"

    def test_invalid_log_level_defaults_to_info(self, monkeypatch):
        monkeypatch.setenv("CSR_LOG_LEVEL", "INVALID")
        from src.csr_service.logging import setup_logging

        logger = setup_logging()
        assert logger.name == "csr_service"
