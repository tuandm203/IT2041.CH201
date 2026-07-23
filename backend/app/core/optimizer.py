"""
Optimizer core logic — placeholder cho thuật toán đề xuất môn học.

Hiện tại chứa logic cơ bản. Các tiêu chí mở rộng sẽ được thêm vào đây:
  - Ưu tiên môn chưa học
  - Cân bằng tín chỉ giữa các nhóm kiến thức
  - Tránh xung đột thời gian (nếu có dữ liệu lịch)
  - Tối ưu số môn gần với min_credits
"""

from app.models.schedule import OptimizeRequest, OptimizeResponse, ScheduleItem


def optimize_schedule(req: OptimizeRequest) -> OptimizeResponse:
    """
    Thuật toán đề xuất môn học cơ bản.

    Chiến lược (greedy):
      1. Sắp xếp môn theo tín chỉ tăng dần (ưu tiên môn ít TC để linh hoạt)
      2. Chọn môn cho đến khi đạt min_credits
      3. Dừng nếu vượt max_credits hoặc max_courses
      4. Ghi chú lý do đề xuất cho từng môn
    """
    courses = list(req.courses)
    # Sắp xếp: môn ít tín chỉ trước (greedy để linh hoạt điều chỉnh)
    courses_sorted = sorted(courses, key=lambda c: (c.credits, c.course_id))

    selected: list[ScheduleItem] = []
    not_selected: list[ScheduleItem] = []
    total_credits = 0
    warnings: list[str] = []

    for c in courses_sorted:
        # Kiểm tra max_courses
        if req.max_courses is not None and len(selected) >= req.max_courses:
            not_selected.append(_to_item(c, "Đã đạt số môn tối đa"))
            continue

        # Kiểm tra max_credits
        if total_credits + c.credits > req.max_credits:
            not_selected.append(_to_item(c, f"Thêm {c.credits} TC sẽ vượt quá max ({req.max_credits} TC)"))
            continue

        # Chọn môn
        total_credits += c.credits
        selected.append(_to_item(c, f"Chọn để đạt gần min ({req.min_credits} TC), hiện tại {total_credits} TC"))

    # Cảnh báo nếu chưa đạt min_credits
    if total_credits < req.min_credits:
        warnings.append(
            f"Tổng TC đã chọn ({total_credits}) chưa đạt tối thiểu ({req.min_credits}). "
            "Có thể tăng max_credits hoặc thêm môn."
        )

    # Cảnh báo nếu còn môn chưa chọn nhưng đã đủ TC
    if not_selected and total_credits >= req.min_credits:
        warnings.append(
            f"Đã đủ {total_credits} TC (>= min {req.min_credits}). "
            f"{len(not_selected)} môn chưa được chọn."
        )

    message = (
        f"Đề xuất {len(selected)} môn, tổng {total_credits} TC "
        f"(min: {req.min_credits}, max: {req.max_credits})"
    )

    return OptimizeResponse(
        total_credits=total_credits,
        total_courses=len(selected),
        selected=selected,
        not_selected=not_selected,
        warnings=warnings,
        message=message,
    )


def _to_item(course, reason: str) -> ScheduleItem:
    """Convert Course → ScheduleItem."""
    return ScheduleItem(
        course_id=course.course_id,
        course_name=course.course_name,
        credits=course.credits,
        reason=reason,
    )
