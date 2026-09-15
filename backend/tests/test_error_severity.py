import unittest

from app.services.error_severity import severity_for_error_type


class ErrorSeverityTests(unittest.TestCase):
    def test_every_error_type_has_expected_severity(self) -> None:
        expected = {
            "image_lossy_warning": "warning",
            "audio_bitrate_warning": "warning",
            "audio_duration_mismatch": "warning",
            "unsupported_format": "error",
            "extension_mismatch": "error",
            "invalid_input": "error",
            "image_decode_error": "error",
            "image_encode_error": "error",
            "missing_dependency": "critical",
            "converter_error": "critical",
            "file_read_error": "critical",
            "file_write_error": "critical",
            "unknown": "error",
        }
        for error_type, severity in expected.items():
            with self.subTest(error_type=error_type):
                self.assertEqual(severity_for_error_type(error_type), severity)


if __name__ == "__main__":
    unittest.main()
