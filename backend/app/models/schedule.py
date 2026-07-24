"""
Pydantic data models cho Schedule Optimizer.
"""

from typing import Optional, List, Tuple, Literal
from pydantic import BaseModel, Field
from enum import Enum


class EnglishLevel(str, Enum):
    """Trình độ tiếng Anh."""
    PASSED = "passed"       # Đã pass đầu ra
    A1 = "a1"               # Cơ bản
    A2 = "a2"               # Sơ cấp
    B1 = "b1"               # Trung cấp (đầu vào ĐH)
    B2 = "b2"               # Cao trung cấp (đầu ra)


class Course(BaseModel):
    """Môn học trong file Excel."""
    course_id: str = Field(..., description="Mã môn (ví dụ: IT001)")
    course_name: str = Field(..., description="Tên môn")
    credits: int = Field(..., ge=0, description="Số tín chỉ")
    note: Optional[str] = Field(None, description="Ghi chú (nếu có)")


class CourseClass(BaseModel):
    """Một lớp học cụ thể (LT hoặc TH) của một môn."""
    course_id: str = Field(..., description="Mã môn")
    course_name: str = Field(..., description="Tên môn")
    ma_lop: str = Field(..., description="Mã lớp (ví dụ: EC201.P21)")
    credits: int = Field(..., ge=0, description="Số tín chỉ")
    credits_lt: int = Field(0, description="Tín chỉ lý thuyết")
    credits_th: int = Field(0, description="Tín chỉ thực hành")
    is_practical: bool = Field(False, description="Có phải lớp thực hành không")
    htgd: str = Field("LT", description="Hình thức giảng dạy (LT/TH/ĐA/...)")
    note: Optional[str] = Field(None, description="Ghi chú")
    # Schedule info: list of (day, start_period, end_period)
    # Day: 2-7 (T2-T7), Period: 1-14 (typical)
    schedule_slots: List[Tuple[int, int, int]] = Field(
        default_factory=list,
        description="Danh sách (thứ, tiết_bắt_đầu, tiết_kết_thúc)"
    )


class CourseGroup(BaseModel):
    """
    Nhóm môn học: gồm 1 lớp LT + (tùy chọn) các lớp TH đi kèm.
    Nếu môn có thực hành, user phải chọn 1 cặp (LT + 1 TH).
    """
    course_id: str = Field(..., description="Mã môn")
    course_name: str = Field(..., description="Tên môn")
    total_credits: int = Field(..., ge=0, description="Tổng tín chỉ (LT + TH)")
    theory_classes: List[CourseClass] = Field(default_factory=list, description="Các lớp lý thuyết")
    practical_classes: List[CourseClass] = Field(default_factory=list, description="Các lớp thực hành")
    has_practical: bool = Field(False, description="Môn này có thực hành không")
    department: Optional[str] = Field(None, description="Khoa quản lý (KHOA QL)")
    note: Optional[str] = Field(None, description="Ghi chú")


class StudentProfile(BaseModel):
    """Thông tin sinh viên cho việc đề xuất thời khóa biểu."""
    training_system: Optional[str] = Field(None, description="Hệ đào tạo (VD: Đại học chính quy)")
    major: Optional[str] = Field(None, description="Mã ngành học (VD: CNTT)")
    cohort: Optional[str] = Field(None, description="Khóa tuyển sinh (VD: K2015)")
    track: Optional[str] = Field(
        None,
        description="Khóa định hướng chuyên ngành (VD: computer_vision)",
    )
    english_level: EnglishLevel = Field(
        EnglishLevel.B1,
        description="Trình độ tiếng Anh: passed (đã pass) / a1 / a2 / b1 / b2"
    )
    passed_pe_courses: List[str] = Field(
        default_factory=list,
        description="Danh sách tên môn thể dục đã pass"
    )
    completed_courses: List[str] = Field(
        default_factory=list,
        description="Danh sách mã môn đã pass (đã học xong)"
    )
    retake_courses: List[str] = Field(
        default_factory=list,
        description="Danh sách mã môn muốn đăng ký học lại hoặc cải thiện điểm"
    )
    skip_pe_if_completed: bool = Field(
        default=False,
        description="Bỏ qua các môn thể dục nếu đã học xong"
    )


class OptimizeRequest(BaseModel):
    """Request body cho endpoint /optimize."""
    min_credits: int = Field(..., ge=1, le=50, description="Số TC tối thiểu")
    max_credits: int = Field(..., ge=1, le=50, description="Số TC tối đa")
    max_courses: Optional[int] = Field(None, ge=1, le=20, description="Số môn tối đa")
    course_groups: List[CourseGroup] = Field(default_factory=list, description="Danh sách nhóm môn học")
    courses: List[Course] = Field(default_factory=list, description="Danh sách môn học (legacy)")
    student: Optional[StudentProfile] = Field(None, description="Thông tin sinh viên")
    engine: Literal["gp1", "gp2"] = Field(
        "gp1",
        description="Bộ máy xếp hạng môn học: gp1 (đồ thị) hoặc gp2 (mô hình Ridge)",
    )


class ScheduleItem(BaseModel):
    """Một môn học trong kết quả đề xuất."""
    course_id: str
    course_name: str
    credits: int
    ma_lop: Optional[str] = Field(None, description="Mã lớp được chọn")
    reason: str = Field(..., description="Lý do được đề xuất (explainable)")
    category: Optional[str] = Field(None, description="Phân loại: new / retake / improvement / english / pe")
    priority_score: Optional[float] = Field(
        None,
        description="Điểm ưu tiên GP2; giá trị lớn hơn được ưu tiên hơn",
    )
    # Schedule info for timetable
    schedule_slots: List[Tuple[int, int, int]] = Field(
        default_factory=list,
        description="Danh sách (thứ, tiết_bắt_đầu, tiết_kết_thúc)"
    )


class OptimizeResponse(BaseModel):
    """Kết quả tối ưu thời khóa biểu."""
    total_credits: int
    total_courses: int
    selected: List[ScheduleItem]
    not_selected: List[ScheduleItem]
    warnings: List[str] = Field(default_factory=list)
    message: str = ""


# ── Danh sách môn thể dục mặc định ──────────────────────────────────────

DEFAULT_PE_COURSES = [
    "Giáo dục thể chất 1 - Bóng đá",
    "Giáo dục thể chất 1 - Bóng chuyền",
    "Giáo dục thể chất 1 - Bơi lội",
    "Giáo dục thể chất 1 - Cầu lông",
    "Giáo dục thể chất 1 - Võ thuật",
    "Giáo dục thể chất 1 - Điền kinh",
    "Giáo dục thể chất 1 - Thể dục nhịp điệu",
    "Giáo dục thể chất 1 - Yoga",
    "Giáo dục thể chất 1 - Golf",
    "Giáo dục thể chất 1 - Cờ vua",
    "Giáo dục thể chất 2 - Bóng đá",
    "Giáo dục thể chất 2 - Bóng chuyền",
    "Giáo dục thể chất 2 - Bơi lội",
    "Giáo dục thể chất 2 - Cầu lông",
    "Giáo dục thể chất 2 - Võ thuật",
    "Giáo dục thể chất 2 - Điền kinh",
    "Giáo dục thể chất 3 - Bóng đá",
    "Giáo dục thể chất 3 - Bóng chuyền",
    "Giáo dục thể chất 3 - Bơi lội",
    "Giáo dục thể chất 3 - Cầu lông",
    "Giáo dục thể chất 3 - Võ thuật",
]

# ── Danh sách hệ đào tạo ────────────────────────────────────────────────

TRAINING_SYSTEM_LIST = [
    "Đại học chính quy",
    "Cao đẳng",
    "Liên thông đại học",
    "Văn bằng 2",
    "Sau đại học",
]

# ── Môn tiếng Anh theo trình độ ─────────────────────────────────────────

ENGLISH_COURSE_MAP: dict[str, List[dict]] = {
    "a1": [
        {"course_id": "ENG01", "course_name": "Tiếng Anh 1 (A1)", "credits": 3},
        {"course_id": "ENG02", "course_name": "Tiếng Anh 2 (A1+)", "credits": 3},
    ],
    "a2": [
        {"course_id": "ENG03", "course_name": "Tiếng Anh 3 (A2)", "credits": 3},
        {"course_id": "ENG04", "course_name": "Tiếng Anh 4 (A2+)", "credits": 3},
    ],
    "b1": [
        {"course_id": "ENG05", "course_name": "Tiếng Anh 5 (B1)", "credits": 3},
        {"course_id": "ENG06", "course_name": "Tiếng Anh 6 (B1+)", "credits": 3},
    ],
    "b2": [
        {"course_id": "ENG07", "course_name": "Tiếng Anh 7 (B2)", "credits": 3},
        {"course_id": "ENG08", "course_name": "Tiếng Anh 8 (B2+)", "credits": 3},
    ],
}
