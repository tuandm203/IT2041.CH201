import unicodedata
from io import BytesIO
import pandas as pd
from fastapi import UploadFile

from app.models.schedule import Course


# 1. Bổ sung các alias xuất hiện trong file Excel mới
COLUMN_ALIASES = {
    "course_id": [
        "mã_môn", "ma_mon", "mã môn", "course_id", "mã hp", "mã học phần", "code",
        "mã mh", "ma_mh", "mamh"
    ],
    "course_name": [
        "tên_môn", "ten_mon", "tên môn", "course_name", "tên học phần", "name", "tên",
        "tên môn học", "ten_mon_hoc", "tenmonhoc"
    ],
    "credits": [
        "tín_chỉ", "tin_chi", "tín chỉ", "credits", "số tc", "số tín chỉ", "credit",
        "tổ tc", "to_tc", "totc"
    ],
    "note": [
        "ghi_chú", "ghi_chu", "ghi chú", "note", "ghi chu", "ghichu"
    ],
}


def _normalize_str(text: str) -> str:
    """Chuẩn hóa chuỗi: lowercase, bỏ dấu tiếng Việt, chuyển khoảng trắng thành _"""
    if not text:
        return ""
    text = str(text).strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.replace(" ", "_")
    return text


def _find_column(df: pd.DataFrame, aliases: list[str]) -> str | None:
    """Tìm tên cột thực sự trong DataFrame dựa trên danh sách alias."""
    normalized_cols = {_normalize_str(c): c for c in df.columns}
    for alias in aliases:
        norm_alias = _normalize_str(alias)
        if norm_alias in normalized_cols:
            return normalized_cols[norm_alias]
    return None


def _detect_header_row(content: bytes) -> int:
    """Tự động quét 15 dòng đầu để tìm dòng chứa tiêu đề cột chính xác."""
    df_raw = pd.read_excel(BytesIO(content), header=None, nrows=15, engine="openpyxl")
    
    for idx, row in df_raw.iterrows():
        row_values = " ".join([str(val).lower() for val in row.dropna().values])
        # Nếu dòng chứa các từ khóa đặc trưng của tiêu đề
        if any(k in row_values for k in ["mã mh", "ma mh", "mã môn", "tên môn học"]):
            return idx
    return 0  # Mặc định lấy dòng 0 nếu không quét thấy


async def parse_excel_file(file: UploadFile) -> list[Course]:
    """
    Đọc file Excel và trả về danh sách Course.
    """
    content = await file.read()
    
    # Tự động xác định dòng chứa header
    header_row = _detect_header_row(content)
    df = pd.read_excel(BytesIO(content), header=header_row, engine="openpyxl")

    if df.empty:
        raise ValueError("File Excel không có dữ liệu.")

    # Tìm tên các cột trong DF
    id_col = _find_column(df, COLUMN_ALIASES["course_id"])
    name_col = _find_column(df, COLUMN_ALIASES["course_name"])
    credits_col = _find_column(df, COLUMN_ALIASES["credits"])
    note_col = _find_column(df, COLUMN_ALIASES["note"])

    if not id_col or not name_col:
        raise ValueError(
            "File Excel phải có cột 'Mã môn' (MÃ MH) và 'Tên môn' (TÊN MÔN HỌC). "
            f"Các cột phát hiện được: {list(df.columns)}"
        )

    courses: list[Course] = []
    seen_ids = set()  # Bật nếu muốn lọc trùng các môn xuất hiện nhiều lần (do chia nhiều Lớp)

    for _, row in df.iterrows():
        course_id = str(row[id_col]).strip()
        
        # Bỏ qua dòng trống hoặc dòng lặp lại header
        if not course_id or course_id.lower() in ("nan", "none", "", "mã mh"):
            continue

        course_name = str(row[name_col]).strip()
        if not course_name or course_name.lower() in ("nan", "none"):
            continue

        # Lọc trùng môn học (Ví dụ EC201 xuất hiện ở 2 dòng cho lớp P21 và P22)
        # Bỏ comment 2 dòng dưới nếu bạn chỉ muốn giữ lại 1 Môn duy nhất
        # if course_id in seen_ids:
        #     continue
        # seen_ids.add(course_id)

        # Tín chỉ: chuyển dạng float trước rồi mới ép về int để tránh lỗi với '3.0'
        credits = 3
        if credits_col:
            try:
                val = row[credits_col]
                if pd.notna(val):
                    credits = int(float(val))
            except (ValueError, TypeError):
                credits = 3

        # Ghi chú
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