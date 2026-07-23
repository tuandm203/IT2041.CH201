"""
Excel parser — đọc file Excel và trả về danh sách Course.

Định dạng file Excel (các cột có thể đặt tên khác nhau, không phân biệt hoa/thường):

  | mã_môn | tên_môn        | tín_chỉ | ghi_chú |
  |--------|----------------|---------|---------|
  | IT001  | Nhập môn IT    | 3       |         |
  | IT002  | Lập trình C    | 4       |         |

Các tên cột được hỗ trợ:
  - Mã môn: "mã_môn", "ma_mon", "mã môn", "course_id", "mã hp", "mã học phần"
  - Tên môn: "tên_môn", "ten_mon", "tên môn", "course_name", "tên học phần"
  - Tín chỉ: "tín_chỉ", "tin_chi", "tín chỉ", "credits", "số tc", "số tín chỉ"
  - Ghi chú: "ghi_chú", "ghi_chu", "ghi chú", "note", "ghi chú"
"""

import pandas as pd
from fastapi import UploadFile

from app.models.schedule import Course


# Ánh xạ tên cột (lowercase, không dấu cách) → key chuẩn
COLUMN_ALIASES = {
    "course_id": ["mã_môn", "ma_mon", "mã môn", "course_id", "mã hp", "mã học phần", "code"],
    "course_name": ["tên_môn", "ten_mon", "tên môn", "course_name", "tên học phần", "name", "tên"],
    "credits": ["tín_chỉ", "tin_chi", "tín chỉ", "credits", "số tc", "số tín chỉ", "credit"],
    "note": ["ghi_chú", "ghi_chu", "ghi chú", "note", "ghi chu"],
}


def _normalize_col_name(name: str) -> str:
    """Chuẩn hóa tên cột: lowercase, bỏ dấu cách, bỏ dấu."""
    import unicodedata
    name = str(name).strip().lower()
    # Bỏ dấu tiếng Việt
    name = unicodedata.normalize("NFD", name)
    name = "".join(c for c in name if unicodedata.category(c) != "Mn")
    # Thay dấu cách bằng _
    name = name.replace(" ", "_")
    return name


def _find_column(df: pd.DataFrame, aliases: list[str]) -> str | None:
    """Tìm tên cột thực sự trong DataFrame dựa trên danh sách alias."""
    normalized_cols = {_normalize_col_name(c): c for c in df.columns}
    for alias in aliases:
        if alias in normalized_cols:
            return normalized_cols[alias]
    return None


async def parse_excel_file(file: UploadFile) -> list[Course]:
    """
    Đọc file Excel và trả về danh sách Course.

    Raises:
      ValueError: Nếu file không có cột mã môn hoặc tên môn.
    """
    # Đọc file
    content = await file.read()
    df = pd.read_excel(content, engine="openpyxl")

    if df.empty:
        raise ValueError("File Excel không có dữ liệu.")

    # Tìm cột
    id_col = _find_column(df, COLUMN_ALIASES["course_id"])
    name_col = _find_column(df, COLUMN_ALIASES["course_name"])
    credits_col = _find_column(df, COLUMN_ALIASES["credits"])
    note_col = _find_column(df, COLUMN_ALIASES["note"])

    if not id_col or not name_col:
        raise ValueError(
            "File Excel phải có cột 'mã_môn' và 'tên_môn'. "
            f"Các cột hiện có: {list(df.columns)}"
        )

    courses: list[Course] = []
    for _, row in df.iterrows():
        course_id = str(row[id_col]).strip()
        if not course_id or course_id.lower() in ("nan", "none", ""):
            continue

        course_name = str(row[name_col]).strip()

        # Tín chỉ: mặc định 3 nếu không có cột hoặc giá trị không hợp lệ
        credits = 3
        if credits_col:
            try:
                credits = int(row[credits_col])
            except (ValueError, TypeError):
                credits = 3

        note = None
        if note_col:
            note_val = row[note_col]
            if pd.notna(note_val) and str(note_val).strip():
                note = str(note_val).strip()

        courses.append(Course(
            course_id=course_id,
            course_name=course_name,
            credits=credits,
            note=note,
        ))

    return courses
