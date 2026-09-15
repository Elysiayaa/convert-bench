from typing import Literal


Severity = Literal["warning", "error", "critical"]

_WARNING_TYPES = {
    "image_lossy_warning",
    "audio_bitrate_warning",
    "audio_duration_mismatch",
}
_CRITICAL_TYPES = {
    "missing_dependency",
    "converter_error",
    "file_read_error",
    "file_write_error",
}


def severity_for_error_type(error_type: str | None) -> Severity:
    """按照错误类型返回稳定的严重程度，未知类型按普通错误处理。"""

    normalized = (error_type or "unknown").strip().casefold()
    if normalized in _WARNING_TYPES:
        return "warning"
    if normalized in _CRITICAL_TYPES:
        return "critical"
    return "error"
