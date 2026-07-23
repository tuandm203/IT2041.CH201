"""
Helper functions — tiện ích chung.
"""

import unicodedata


def normalize_text(text: str) -> str:
    """
    Chuẩn hóa chuỗi: trim, lowercase, bỏ dấu, bỏ khoảng trắng thừa.
    Dùng để so sánh tên cột, mã môn, v.v.
    """
    if not text:
        return ""
    text = str(text).strip().lower()
    # Bỏ dấu tiếng Việt
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    # Bỏ khoảng trắng thừa
    text = " ".join(text.split())
    return text


def format_credits(credits: int) -> str:
    """Định dạng số tín chỉ: 3 → '3 TC'."""
    return f"{credits} TC"
