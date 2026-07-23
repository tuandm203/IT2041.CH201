"""
Pydantic data models cho Schedule Optimizer.
"""

from typing import Optional
from pydantic import BaseModel, Field


class Course(BaseModel):
    """Môn học trong file Excel."""
    course_id: str = Field(..., description="Mã môn (ví dụ: IT001)")
    course_name: str = Field(..., description="Tên môn")
    credits: int = Field(..., ge=0, description="Số tín chỉ")
    note: Optional[str] = Field(None, description="Ghi chú (nếu có)")


class OptimizeRequest(BaseModel):
    """Request body cho endpoint /optimize."""
    min_credits: int = Field(..., ge=1, le=50, description="Số TC tối thiểu")
    max_credits: int = Field(..., ge=1, le=50, description="Số TC tối đa")
    max_courses: Optional[int] = Field(None, ge=1, le=20, description="Số môn tối đa")
    courses: list[Course] = Field(..., min_length=1, description="Danh sách môn học")


class ScheduleItem(BaseModel):
    """Một môn học trong kết quả đề xuất."""
    course_id: str
    course_name: str
    credits: int
    reason: str = Field(..., description="Lý do được đề xuất (explainable)")


class OptimizeResponse(BaseModel):
    """Kết quả tối ưu thời khóa biểu."""
    total_credits: int
    total_courses: int
    selected: list[ScheduleItem]
    not_selected: list[ScheduleItem]
    warnings: list[str] = Field(default_factory=list)
    message: str = ""
