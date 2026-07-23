"""
Excel Parser — Đọc file TKB_KHDT và trả về danh sách CourseGroup.

File TKB_KHDT có 2 sheets:
  - "TKB LT": Danh sách lớp lý thuyết (THỰC HÀNH = 0, TỐ TC)
  - "TKB TH": Danh sách lớp thực hành (THỰC HÀNH = 1, SỐ TC)

Quy tắc ghép:
  - Mỗi MÃ MH trong sheet LT → 1 CourseGroup
  - Lớp TH (từ sheet TH) được linked với lớp LT qua mã lớp:
      TH class code = LT class code + ".1" hoặc + ".2"
  - Nếu 1 môn có lớp TH → has_practical = True,
    user phải chọn 1 trong các lớp TH đó.
  - Không cho phép học LT kỳ này, TH kỳ sau (vì chọn cùng lúc).
"""

import unicodedata
from io import BytesIO
import pandas as pd
from fastapi import UploadFile

from app.models.schedule import CourseGroup, CourseClass


# ── Column aliases ─────────────────────────────────────────────────────
COLUMN_ALIASES = {
    "course_id": [
        "mã_mh", "ma_mh", "mamh", "mã mh",
        "mã_môn", "ma_mon", "mã môn", "course_id", "mã hp", "mã học phần", "code",
    ],
    "course_name": [
        "tên_môn_học", "ten_mon_hoc", "tenmonhoc", "tên môn học",
        "tên_môn", "ten_mon", "tên môn", "course_name", "tên học phần", "name", "tên",
    ],
    "credits": [
        "tố_tc", "to_tc", "totc", "tố tc",
        "số_tc", "so_tc", "số tc",
        "tín_chỉ", "tin_chi", "tín chỉ", "credits", "số tín chỉ", "credit",
    ],
    "class_code": [
        "mã_lớp", "ma_lop", "malop", "mã lớp",
    ],
    "practical": [
        "thực_hành", "thuc_hanh", "thuchanh", "thực hành",
    ],
    "htgd": [
        "htgd", "hình_thức_giảng_dạy", "hinh_thuc_giang_day",
    ],
    "department": [
        "khoa_ql", "khoa ql", "khoa_quản_lý", "khoa quan ly",
    ],
    "note": [
        "ghi_chú", "ghi_chu", "ghichu", "ghi chú", "note", "ghi chu",
    ],
    "day_of_week": [
        "thứ", "thu", "thuoc", "ngày", "ngay", "day", "weekday",
    ],
    "start_period": [
        "tiết_bắt_đầu", "tiet_bat_dau", "tiết bắt đầu", "tiet bat dau",
        "tiết_đầu", "tiet_dau", "start_period", "from_period",
    ],
    "end_period": [
        "tiết_kết_thúc", "tiet_ket_thuc", "tiết kết thúc", "tiet ket thuc",
        "tiết_cuối", "tiet_cuoi", "end_period", "to_period",
    ],
    "periods": [
        "tiết", "tiet", "period", "periods", "các_tiết", "cac_tiet",
    ],
}

# Các hình thức giảng dạy ĐẶC BIỆT (không phải LT cũng không phải TH thông thường)
NON_COURSE_HTGD = {"ĐA", "TTTN", "KLTN", "BT"}

# Header row index (0-based)
HEADER_ROW = 7

# Tên các sheet trong file TKB_KHDT
SHEET_LT = "TKB LT"
SHEET_TH = "TKB TH"


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
    """Tự động quét 15 dòng đầu để tìm dòng chứa tiêu đề cột."""
    df_raw = pd.read_excel(BytesIO(content), header=None, nrows=15, engine="openpyxl")
    for idx, row in df_raw.iterrows():
        row_values = " ".join([str(val).lower() for val in row.dropna().values])
        if any(k in row_values for k in ["mã mh", "ma mh", "mã môn", "tên môn học"]):
            return idx
    return 0


def _has_sheet_names(content: bytes) -> list[str] | None:
    """Kiểm tra xem file Excel có sheet 'TKB LT' và 'TKB TH' không."""
    try:
        xls = pd.ExcelFile(BytesIO(content), engine="openpyxl")
        return xls.sheet_names
    except Exception:
        return None


def _read_sheet(content: bytes, sheet_name: str | None) -> pd.DataFrame:
    """Đọc 1 sheet từ file Excel."""
    if sheet_name:
        df = pd.read_excel(
            BytesIO(content), sheet_name=sheet_name,
            header=HEADER_ROW, engine="openpyxl",
        )
    else:
        header_row = _detect_header_row(content)
        df = pd.read_excel(
            BytesIO(content), header=header_row, engine="openpyxl",
        )
    return df


def _parse_periods(period_str: str) -> list[int]:
    """Parse chuỗi tiết thành list các tiết số.
    Ví dụ: "1-3" → [1, 2, 3], "1,2,3" → [1, 2, 3], "678" → [6, 7, 8]
    """
    if not period_str or period_str.lower() in ("nan", "none", ""):
        return []
    
    period_str = str(period_str).strip()
    periods = []
    
    # Try to parse range format (e.g., "1-3", "1-5")
    if '-' in period_str:
        try:
            parts = period_str.split('-')
            if len(parts) == 2:
                start = int(float(parts[0].strip()))
                end = int(float(parts[1].strip()))
                periods = list(range(start, end + 1))
        except (ValueError, TypeError):
            pass
    
    # Try to parse comma-separated (e.g., "1,2,3")
    if not periods and ',' in period_str:
        try:
            parts = period_str.split(',')
            for part in parts:
                p = int(float(part.strip()))
                if 1 <= p <= 14:
                    periods.append(p)
        except (ValueError, TypeError):
            pass
    
    # Try individual digits (e.g., "678" → [6, 7, 8])
    if not periods and period_str.isdigit():
        for char in period_str:
            p = int(char)
            if 1 <= p <= 14:
                periods.append(p)
    
    # Try single number
    if not periods:
        try:
            p = int(float(period_str))
            if 1 <= p <= 14:
                periods.append(p)
        except (ValueError, TypeError):
            pass
    
    return sorted(list(set(periods)))


def _parse_theory_row(row, id_col, name_col, class_col, credits_col, htgd_col, dept_col, note_col, day_col=None, start_period_col=None, end_period_col=None, periods_col=None) -> CourseClass | None:
    """Parse 1 dòng từ sheet LT thành CourseClass (hoặc None nếu không hợp lệ)."""
    course_id = str(row[id_col]).strip()
    if not course_id or course_id.lower() in ("nan", "none", ""):
        return None
    course_name = str(row[name_col]).strip()
    if not course_name or course_name.lower() in ("nan", "none"):
        return None
    ma_lop = str(row[class_col]).strip()
    if not ma_lop or ma_lop.lower() in ("nan", "none"):
        return None

    # Tín chỉ
    credits = 0
    if credits_col:
        try:
            val = row[credits_col]
            if pd.notna(val):
                credits = int(float(val))
        except (ValueError, TypeError):
            credits = 0

    # HTGD
    htgd = "LT"
    if htgd_col:
        try:
            val = row[htgd_col]
            if pd.notna(val) and str(val).strip():
                htgd = str(val).strip()
        except (ValueError, TypeError):
            pass

    # Bỏ qua các môn đặc biệt (ĐA, TTTN, KLTN...)
    if htgd in NON_COURSE_HTGD:
        return None

    # Ghi chú
    note = None
    if note_col:
        note_val = row[note_col]
        if pd.notna(note_val) and str(note_val).strip():
            note = str(note_val).strip()

    # Parse schedule slots
    schedule_slots = []
    
    # Method 1: Use "Tiết" column if available (e.g., "1-3" means periods 1,2,3)
    if periods_col:
        try:
            period_val = row[periods_col]
            if pd.notna(period_val) and str(period_val).strip():
                periods_list = _parse_periods(str(period_val).strip())
                if periods_list and day_col:
                    day_val = row[day_col]
                    if pd.notna(day_val):
                        day = int(float(day_val))
                        if 2 <= day <= 7:
                            # Group consecutive periods into slots
                            start_period = periods_list[0]
                            end_period = periods_list[0]
                            for p in periods_list[1:]:
                                if p == end_period + 1:
                                    end_period = p
                                else:
                                    schedule_slots.append((day, start_period, end_period))
                                    start_period = p
                                    end_period = p
                            schedule_slots.append((day, start_period, end_period))
        except (ValueError, TypeError):
            pass
    
    # Method 2: Use start/end period columns if "Tiết" column not available
    if not schedule_slots and day_col and start_period_col and end_period_col:
        try:
            day_val = row[day_col]
            start_val = row[start_period_col]
            end_val = row[end_period_col]
            
            if pd.notna(day_val) and pd.notna(start_val) and pd.notna(end_val):
                day = int(float(day_val))
                start_period = int(float(start_val))
                end_period = int(float(end_val))
                if 2 <= day <= 7 and 1 <= start_period <= end_period:
                    schedule_slots.append((day, start_period, end_period))
        except (ValueError, TypeError):
            pass

    return CourseClass(
        course_id=course_id,
        course_name=course_name,
        ma_lop=ma_lop,
        credits=credits,
        credits_lt=credits,
        credits_th=0,
        is_practical=False,
        htgd=htgd,
        note=note,
        schedule_slots=schedule_slots,
    )


def _parse_practical_row(row, id_col, name_col, class_col, credits_col, htgd_col, note_col, day_col=None, start_period_col=None, end_period_col=None, periods_col=None) -> CourseClass | None:
    """Parse 1 dòng từ sheet TH thành CourseClass (hoặc None nếu không hợp lệ)."""
    course_id = str(row[id_col]).strip()
    if not course_id or course_id.lower() in ("nan", "none", ""):
        return None
    course_name = str(row[name_col]).strip()
    if not course_name or course_name.lower() in ("nan", "none"):
        return None
    ma_lop = str(row[class_col]).strip()
    if not ma_lop or ma_lop.lower() in ("nan", "none"):
        return None

    credits = 0
    if credits_col:
        try:
            val = row[credits_col]
            if pd.notna(val):
                credits = int(float(val))
        except (ValueError, TypeError):
            credits = 0

    htgd = "HT"
    if htgd_col:
        try:
            val = row[htgd_col]
            if pd.notna(val) and str(val).strip():
                htgd = str(val).strip()
        except (ValueError, TypeError):
            pass

    if htgd in NON_COURSE_HTGD:
        return None

    note = None
    if note_col:
        note_val = row[note_col]
        if pd.notna(note_val) and str(note_val).strip():
            note = str(note_val).strip()

    # Parse schedule slots
    schedule_slots = []
    
    # Method 1: Use "Tiết" column if available
    if periods_col:
        try:
            period_val = row[periods_col]
            if pd.notna(period_val) and str(period_val).strip():
                periods_list = _parse_periods(str(period_val).strip())
                if periods_list and day_col:
                    day_val = row[day_col]
                    if pd.notna(day_val):
                        day = int(float(day_val))
                        if 2 <= day <= 7:
                            # Group consecutive periods into slots
                            start_period = periods_list[0]
                            end_period = periods_list[0]
                            for p in periods_list[1:]:
                                if p == end_period + 1:
                                    end_period = p
                                else:
                                    schedule_slots.append((day, start_period, end_period))
                                    start_period = p
                                    end_period = p
                            schedule_slots.append((day, start_period, end_period))
        except (ValueError, TypeError):
            pass
    
    # Method 2: Use start/end period columns
    if not schedule_slots and day_col and start_period_col and end_period_col:
        try:
            day_val = row[day_col]
            start_val = row[start_period_col]
            end_val = row[end_period_col]
            
            if pd.notna(day_val) and pd.notna(start_val) and pd.notna(end_val):
                day = int(float(day_val))
                start_period = int(float(start_val))
                end_period = int(float(end_val))
                if 2 <= day <= 7 and 1 <= start_period <= end_period:
                    schedule_slots.append((day, start_period, end_period))
        except (ValueError, TypeError):
            pass

    return CourseClass(
        course_id=course_id,
        course_name=course_name,
        ma_lop=ma_lop,
        credits=credits,
        credits_lt=0,
        credits_th=credits,
        is_practical=True,
        htgd=htgd,
        note=note,
        schedule_slots=schedule_slots,
    )


def _build_course_groups(
    theory_classes: list[CourseClass],
    practical_classes: list[CourseClass],
    row_department_map: dict[str, str],  # course_id → department
) -> tuple[list[CourseGroup], set[str]]:
    """
    Ghép các lớp LT và TH thành CourseGroup.
    Trả về (groups, departments_set).
    """
    groups: dict[str, CourseGroup] = {}
    all_departments: set[str] = set()

    # Thêm các lớp LT
    for cc in theory_classes:
        dept = row_department_map.get(cc.ma_lop, "")
        if dept:
            all_departments.add(dept.upper())

        if cc.course_id not in groups:
            groups[cc.course_id] = CourseGroup(
                course_id=cc.course_id,
                course_name=cc.course_name,
                total_credits=0,
                theory_classes=[],
                practical_classes=[],
                has_practical=False,
                department=dept.upper() if dept else None,
                note=cc.note,
            )
        groups[cc.course_id].theory_classes.append(cc)

    # Cập nhật department cho các group đã tạo
    for g in groups.values():
        if not g.department:
            # Lấy department từ bất kỳ lớp LT nào
            for tc in g.theory_classes:
                dept = row_department_map.get(tc.ma_lop, "")
                if dept:
                    g.department = dept.upper()
                    all_departments.add(dept.upper())
                    break

    # Xây map: LT class code prefix → CourseGroup
    lt_prefix_map: dict[str, str] = {}
    for g in groups.values():
        for tc in g.theory_classes:
            lt_prefix_map[tc.ma_lop] = g.course_id

    # Thêm các lớp TH
    for cc in practical_classes:
        th_code = cc.ma_lop
        lt_code = th_code

        parts = th_code.rsplit('.', 1)
        if len(parts) == 2 and parts[1].isdigit():
            lt_code = parts[0]

        if lt_code not in lt_prefix_map:
            parts2 = lt_code.rsplit('.', 1)
            if len(parts2) == 2:
                lt_code2 = parts2[0]

        parent_id = lt_prefix_map.get(lt_code)
        if not parent_id:
            for map_key, map_val in lt_prefix_map.items():
                if cc.ma_lop.startswith(map_key + '.') or cc.ma_lop == map_key:
                    parent_id = map_val
                    break

        if not parent_id:
            if cc.course_id not in groups:
                groups[cc.course_id] = CourseGroup(
                    course_id=cc.course_id,
                    course_name=cc.course_name,
                    total_credits=0,
                    theory_classes=[],
                    practical_classes=[],
                    has_practical=False,
                    department=None,
                    note=cc.note,
                )
            parent_id = cc.course_id

        groups[parent_id].practical_classes.append(cc)
        groups[parent_id].has_practical = True

    # Tính total_credits
    for group in groups.values():
        if group.has_practical and group.theory_classes:
            lt_tc = group.theory_classes[0].credits
            th_tc = group.practical_classes[0].credits if group.practical_classes else 0
            group.total_credits = lt_tc + th_tc
        elif group.theory_classes:
            group.total_credits = group.theory_classes[0].credits

    return list(groups.values()), all_departments


def _is_new_file_format(sheet_names: list[str] | None) -> bool:
    """Kiểm tra xem file có phải định dạng TKB_KHDT không (dựa trên tên sheet)."""
    if sheet_names is None:
        return False
    names_lower = [s.strip().lower() for s in sheet_names]
    return "tkb lt" in names_lower or "tkb th" in names_lower


def _parse_new_format(content: bytes) -> tuple[list[CourseGroup], list[str]]:
    """
    Parse file TKB_KHDT (có 2 sheets: TKB LT và TKB TH).
    Trả về (groups, departments_sorted).
    """
    # Đọc sheet LT
    df_lt = _read_sheet(content, SHEET_LT)

    # Tìm cột cho sheet LT
    id_col = _find_column(df_lt, COLUMN_ALIASES["course_id"])
    name_col = _find_column(df_lt, COLUMN_ALIASES["course_name"])
    class_col = _find_column(df_lt, COLUMN_ALIASES["class_code"])
    credits_col = _find_column(df_lt, COLUMN_ALIASES["credits"])
    htgd_col = _find_column(df_lt, COLUMN_ALIASES["htgd"])
    dept_col = _find_column(df_lt, COLUMN_ALIASES["department"])
    note_col = _find_column(df_lt, COLUMN_ALIASES["note"])

    if not id_col or not name_col or not class_col:
        raise ValueError(
            f"Sheet '{SHEET_LT}' phải có cột 'MÃ MH', 'TÊN MÔN HỌC' và 'MÃ LỚP'. "
            f"Các cột phát hiện được: {list(df_lt.columns)}"
        )

    # Tìm cột thời khóa biểu (nếu có)
    day_col = _find_column(df_lt, COLUMN_ALIASES["day_of_week"])
    start_period_col = _find_column(df_lt, COLUMN_ALIASES["start_period"])
    end_period_col = _find_column(df_lt, COLUMN_ALIASES["end_period"])
    periods_col = _find_column(df_lt, COLUMN_ALIASES["periods"])

    # Parse theory classes + thu thập department theo ma_lop
    theory_classes: list[CourseClass] = []
    row_department_map: dict[str, str] = {}  # ma_lop → department

    for _, row in df_lt.iterrows():
        cc = _parse_theory_row(row, id_col, name_col, class_col, credits_col, htgd_col, dept_col, note_col, day_col, start_period_col, end_period_col, periods_col)
        if cc:
            theory_classes.append(cc)
            # Lưu department
            if dept_col:
                try:
                    dept_val = row[dept_col]
                    if pd.notna(dept_val) and str(dept_val).strip():
                        row_department_map[cc.ma_lop] = str(dept_val).strip().upper()
                except (ValueError, TypeError):
                    pass

    # Đọc sheet TH
    practical_classes: list[CourseClass] = []
    try:
        df_th = _read_sheet(content, SHEET_TH)
        id_col_th = _find_column(df_th, COLUMN_ALIASES["course_id"])
        name_col_th = _find_column(df_th, COLUMN_ALIASES["course_name"])
        class_col_th = _find_column(df_th, COLUMN_ALIASES["class_code"])
        credits_col_th = _find_column(df_th, COLUMN_ALIASES["credits"])
        htgd_col_th = _find_column(df_th, COLUMN_ALIASES["htgd"])
        note_col_th = _find_column(df_th, COLUMN_ALIASES["note"])

        if id_col_th and name_col_th and class_col_th:
            # Tìm cột thời khóa biểu cho sheet TH
            day_col_th = _find_column(df_th, COLUMN_ALIASES["day_of_week"])
            start_period_col_th = _find_column(df_th, COLUMN_ALIASES["start_period"])
            end_period_col_th = _find_column(df_th, COLUMN_ALIASES["end_period"])
            periods_col_th = _find_column(df_th, COLUMN_ALIASES["periods"])
            
            for _, row in df_th.iterrows():
                cc = _parse_practical_row(
                    row, id_col_th, name_col_th, class_col_th,
                    credits_col_th, htgd_col_th, note_col_th,
                    day_col_th, start_period_col_th, end_period_col_th, periods_col_th
                )
                if cc:
                    practical_classes.append(cc)
    except Exception:
        pass

    # Ghép
    groups, departments = _build_course_groups(theory_classes, practical_classes, row_department_map)
    # Lọc bỏ P.DTDH khỏi danh sách khoa
    filtered_departments = [d for d in departments if d != 'P.DTDH']
    return groups, sorted(filtered_departments)


def _parse_old_format(content: bytes) -> tuple[list[CourseGroup], list[str]]:
    """
    Parse file định dạng cũ (1 sheet, chỉ có mã môn, tên, tín chỉ, ghi chú).
    """
    header_row = _detect_header_row(content)
    df = pd.read_excel(BytesIO(content), header=header_row, engine="openpyxl")

    id_col = _find_column(df, COLUMN_ALIASES["course_id"])
    name_col = _find_column(df, COLUMN_ALIASES["course_name"])
    credits_col = _find_column(df, COLUMN_ALIASES["credits"])
    note_col = _find_column(df, COLUMN_ALIASES["note"])

    if not id_col or not name_col:
        raise ValueError(
            "File Excel phải có cột 'Mã môn' và 'Tên môn'. "
            f"Các cột phát hiện được: {list(df.columns)}"
        )

    seen_ids = set()
    groups: list[CourseGroup] = []

    for _, row in df.iterrows():
        course_id = str(row[id_col]).strip()
        if not course_id or course_id.lower() in ("nan", "none", ""):
            continue
        course_name = str(row[name_col]).strip()
        if not course_name or course_name.lower() in ("nan", "none"):
            continue
        if course_id in seen_ids:
            continue
        seen_ids.add(course_id)

        credits = 3
        if credits_col:
            try:
                val = row[credits_col]
                if pd.notna(val):
                    credits = int(float(val))
            except (ValueError, TypeError):
                credits = 3

        note = None
        if note_col:
            note_val = row[note_col]
            if pd.notna(note_val) and str(note_val).strip():
                note = str(note_val).strip()

        cc = CourseClass(
            course_id=course_id,
            course_name=course_name,
            ma_lop=course_id,
            credits=credits,
            credits_lt=credits,
            credits_th=0,
            is_practical=False,
            htgd="LT",
            note=note,
        )

        group = CourseGroup(
            course_id=course_id,
            course_name=course_name,
            total_credits=credits,
            theory_classes=[cc],
            practical_classes=[],
            has_practical=False,
            note=note,
        )
        groups.append(group)

    return groups, []


async def parse_excel_file(file: UploadFile) -> tuple[list[CourseGroup], list[str]]:
    """
    Đọc file Excel và trả về (danh_sách_CourseGroup, danh_sách_khoa).
    Tự động nhận dạng định dạng file cũ/mới.
    """
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise ValueError("File không đúng định dạng Excel (.xlsx hoặc .xls)")

    content = await file.read()

    # Kiểm tra tên sheet để nhận dạng định dạng
    sheet_names = _has_sheet_names(content)

    if _is_new_file_format(sheet_names):
        return _parse_new_format(content)
    else:
        return _parse_old_format(content)