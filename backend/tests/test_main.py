import unittest
from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app
from app.services.converter import UnsupportedConversionError


@app.get("/__tests__/unhandled", include_in_schema=False)
def raise_unhandled_error() -> None:
    raise RuntimeError("测试异常")


@app.get("/__tests__/conversion-error", include_in_schema=False)
def raise_conversion_error() -> None:
    raise UnsupportedConversionError("Unsupported conversion: txt -> png")


class GlobalExceptionHandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_unhandled_exception_returns_structured_json_and_traceback(self) -> None:
        with self.assertLogs("app.main", level="ERROR") as captured_logs:
            response = self.client.get("/__tests__/unhandled")

        payload = response.json()
        self.assertEqual(response.status_code, 500)
        self.assertTrue(response.headers["content-type"].startswith("application/json"))
        self.assertEqual(payload["error"], "Internal Server Error")
        self.assertEqual(payload["path"], "/__tests__/unhandled")
        self.assertIn("detail", payload)
        datetime.fromisoformat(payload["timestamp"])
        logs = "\n".join(captured_logs.output)
        self.assertIn("Traceback (most recent call last)", logs)
        self.assertIn("RuntimeError: 测试异常", logs)

    def test_validation_and_http_exceptions_keep_status_codes(self) -> None:
        validation = self.client.get("/api/badcases?page=0")
        missing = self.client.get("/api/badcases/__definitely_missing_case__")

        self.assertEqual(validation.status_code, 422)
        self.assertEqual(validation.json()["error"], "Request Validation Error")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json()["error"], "HTTP Error")

    def test_conversion_exception_contains_error_type(self) -> None:
        response = self.client.get("/__tests__/conversion-error")
        payload = response.json()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(payload["error_type"], "unsupported_format")
        self.assertEqual(payload["severity"], "error")
        self.assertEqual(payload["path"], "/__tests__/conversion-error")


if __name__ == "__main__":
    unittest.main()
