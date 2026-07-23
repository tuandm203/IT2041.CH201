"""
Optimizer core logic — thuật toán đề xuất môn học.

Hỗ trợ:
  - CourseGroup (gồm lớp LT + lớp TH)
  - Môn có thực hành: user phải chọn 1 lớp TH cụ thể
  - Không cho phép học LT kỳ này, TH kỳ sau
  - Lọc môn đã pass
  - Ưu tiên môn học lại / cải thiện (gộp chung)
  - Gợi ý môn tiếng Anh theo trình độ
  - Bỏ qua môn thể dục nếu đã học xong
"""

from typing import Optional
from app.models.schedule import (
    OptimizeRequest, OptimizeResponse, ScheduleItem, CourseGroup,
    EnglishLevel, ENGLISH_COURSE_MAP, DEFAULT_PE_COURSES,
)


def optimize_schedule(
    req: OptimizeRequest,
    practical_map: Optional[dict[str, str]] = None,
) -> OptimizeResponse:
    """
    Thuật toán đề xuất môn học với các ràng buộc mở rộng.

    Chiến lược:
      1. Lọc các môn đã pass (completed_courses)
      2. Xác định môn học lại/cải thiện (retake) — ưu tiên
      3. Xác định môn tiếng Anh cần học dựa trên trình độ
      4. Bỏ qua môn thể dục nếu đã học xong (skip_pe_if_completed)
      5. Tự động chọn lớp TH đầu tiên nếu user không chọn
      6. Sắp xếp: học lại → môn mới (theo tín chỉ tăng dần)
      7. Chọn môn cho đến khi đạt min_credits
      8. Dừng nếu vượt max_credits hoặc max_courses
    """
    if practical_map is None:
        practical_map = {}

    groups = list(req.course_groups)
    student = req.student
    warnings: list[str] = []
    selected: list[ScheduleItem] = []
    not_selected: list[ScheduleItem] = []
    total_credits = 0

    # ── 1. Lọc môn đã pass ──────────────────────────────────────────
    completed_set: set[str] = set()
    retake_set: set[str] = set()

    if student:
        completed_set = set(c.upper() for c in student.completed_courses)
        retake_set = set(c.upper() for c in student.retake_courses)

    # Lọc bỏ môn đã pass
    filtered_groups: list[CourseGroup] = []
    for g in groups:
        cid_upper = g.course_id.upper()
        if cid_upper in completed_set:
            not_selected.append(_to_item_from_group(
                g, "Môn đã được pass trước đó", category="completed"
            ))
        else:
            filtered_groups.append(g)

    # ── 2. Xác định các nhóm môn ─────────────────────────────────────
    retake_groups: list[CourseGroup] = []
    new_groups: list[CourseGroup] = []
    english_groups: list[CourseGroup] = []
    pe_groups: list[CourseGroup] = []

    # Tập hợp tên môn thể dục (để nhận diện)
    pe_names_lower = set(name.lower() for name in DEFAULT_PE_COURSES)

    for g in filtered_groups:
        cid_upper = g.course_id.upper()

        if cid_upper in retake_set:
            retake_groups.append(g)
        else:
            # Kiểm tra xem có phải môn tiếng Anh không
            is_english = any(
                cid_upper == eng["course_id"].upper()
                for eng_list in ENGLISH_COURSE_MAP.values()
                for eng in eng_list
            )
            if is_english:
                english_groups.append(g)
            else:
                # Kiểm tra xem có phải môn thể dục không
                is_pe = g.course_name.lower() in pe_names_lower or "thể dục" in g.course_name.lower() or "giáo dục thể chất" in g.course_name.lower()
                if is_pe:
                    pe_groups.append(g)
                else:
                    new_groups.append(g)

    # ── 3. Thêm môn tiếng Anh nếu cần ────────────────────────────────
    english_to_add: list[CourseGroup] = []
    if student and student.english_level != EnglishLevel.PASSED:
        level = student.english_level.value
        eng_courses = ENGLISH_COURSE_MAP.get(level, [])
        for eng in eng_courses:
            eng_id = eng["course_id"]
            # Tìm trong english_groups
            found = [g for g in english_groups if g.course_id.upper() == eng_id.upper()]
            if found:
                english_to_add.append(found[0])
            elif eng_id.upper() not in completed_set:
                # Môn tiếng Anh không có trong file Excel → cảnh báo
                warnings.append(
                    f"Môn {eng['course_name']} ({eng_id}) không có trong danh sách kỳ này. "
                    f"Cần {eng['credits']} TC tiếng Anh."
                )

    # ── 4. Xử lý môn thể dục ─────────────────────────────────────────
    pe_to_add: list[CourseGroup] = []
    if student and student.skip_pe_if_completed:
        # Nếu đã học xong thể dục (có ít nhất 1 môn PE đã pass), bỏ qua tất cả môn PE
        if student.passed_pe_courses and len(student.passed_pe_courses) > 0:
            for g in pe_groups:
                not_selected.append(_to_item_from_group(
                    g, "Đã bỏ qua môn thể dục (đã học xong)", category="pe"
                ))
            warnings.append("Đã bỏ qua các môn thể dục vì bạn đã học xong.")
        else:
            # Chưa học xong, vẫn đề xuất môn PE
            pe_to_add = pe_groups
    else:
        # Không bỏ qua, vẫn đề xuất
        pe_to_add = pe_groups

    # ── 5. Sắp xếp: học lại → môn mới (theo TC tăng dần) ────────────
    def sort_key(g: CourseGroup) -> tuple:
        # (priority, credits, course_id)
        if g.course_id.upper() in retake_set:
            priority = 0
        elif any(g.course_id.upper() == eng["course_id"].upper() for eng_list in ENGLISH_COURSE_MAP.values() for eng in eng_list):
            priority = 1
        else:
            priority = 2
        return (priority, g.total_credits, g.course_id)

    all_candidates = retake_groups + english_to_add + pe_to_add + new_groups
    all_candidates.sort(key=sort_key)

    # ── 6. Chọn môn ──────────────────────────────────────────────────
    for g in all_candidates:
        # Kiểm tra môn có thực hành
        chosen_th_class = None
        if g.has_practical:
            chosen_th_ma_lop = practical_map.get(g.course_id)
            if chosen_th_ma_lop:
                # User đã chọn lớp TH cụ thể
                for pc in g.practical_classes:
                    if pc.ma_lop == chosen_th_ma_lop:
                        chosen_th_class = pc
                        break
            else:
                # Tự động chọn lớp TH đầu tiên
                if g.practical_classes:
                    chosen_th_class = g.practical_classes[0]
                    warnings.append(
                        f"Môn {g.course_id} có thực hành, đã tự động chọn lớp {chosen_th_class.ma_lop}"
                    )
            
            if not chosen_th_class:
                not_selected.append(_to_item_from_group(
                    g,
                    f"Môn có thực hành nhưng không có lớp TH khả dụng.",
                    category=_get_category(g, retake_set),
                ))
                continue
            if not g.theory_classes:
                not_selected.append(_to_item_from_group(
                    g, "Môn có thực hành nhưng thiếu lớp lý thuyết.",
                    category=_get_category(g, retake_set),
                ))
                continue

        # Kiểm tra max_courses
        if req.max_courses is not None and len(selected) >= req.max_courses:
            not_selected.append(_to_item_from_group(
                g, "Đã đạt số môn tối đa",
                category=_get_category(g, retake_set),
            ))
            continue

        # Kiểm tra max_credits
        if total_credits + g.total_credits > req.max_credits:
            reason = (
                f"Thêm {g.total_credits} TC sẽ vượt quá max ({req.max_credits} TC)"
            )
            not_selected.append(_to_item_from_group(
                g, reason,
                category=_get_category(g, retake_set),
            ))
            continue

        # Kiểm tra xung đột lịch
        new_slots = []
        if g.theory_classes:
            new_slots.extend(g.theory_classes[0].schedule_slots)
        if chosen_th_class:
            new_slots.extend(chosen_th_class.schedule_slots)
        
        if _has_conflict(new_slots, selected):
            not_selected.append(_to_item_from_group(
                g,
                f"Xung đột lịch với môn đã chọn.",
                category=_get_category(g, retake_set),
            ))
            continue

        # Chọn môn
        total_credits += g.total_credits
        category = _get_category(g, retake_set)

        # Tạo 1 entry cho lớp LT
        lt_slots = []
        if g.theory_classes:
            lt_slots = g.theory_classes[0].schedule_slots
        
        lt_ma_lop = g.theory_classes[0].ma_lop if g.theory_classes else g.course_id
        lt_reason = f"{_get_category_label(category)}: Lớp LT {lt_ma_lop}. Hiện tại {total_credits} TC"
        
        selected.append(ScheduleItem(
            course_id=g.course_id,
            course_name=g.course_name,
            credits=g.theory_classes[0].credits if g.theory_classes else g.total_credits,
            ma_lop=lt_ma_lop,
            reason=lt_reason,
            category=category,
            schedule_slots=lt_slots,
        ))

        # Tạo 1 entry riêng cho lớp TH (nếu có)
        if g.has_practical and chosen_th_class:
            th_slots = chosen_th_class.schedule_slots
            th_ma_lop = chosen_th_class.ma_lop
            th_reason = f"{_get_category_label(category)}: Lớp TH {th_ma_lop}. Hiện tại {total_credits} TC"
            
            selected.append(ScheduleItem(
                course_id=g.course_id,
                course_name=g.course_name + " (TH)",
                credits=chosen_th_class.credits,
                ma_lop=th_ma_lop,
                reason=th_reason,
                category=category,
                schedule_slots=th_slots,
            ))

    # ── 7. Cảnh báo ──────────────────────────────────────────────────
    if total_credits < req.min_credits:
        warnings.append(
            f"Tổng TC đã chọn ({total_credits}) chưa đạt tối thiểu ({req.min_credits}). "
            "Có thể tăng max_credits hoặc thêm môn."
        )

    if not_selected and total_credits >= req.min_credits:
        warnings.append(
            f"Đã đủ {total_credits} TC (>= min {req.min_credits}). "
            f"{len(not_selected)} môn chưa được chọn."
        )

    # Kiểm tra môn học lại/cải thiện có mở trong kỳ này không
    if student and student.retake_courses:
        available_ids = {g.course_id.upper() for g in groups}
        for ret_cid in student.retake_courses:
            if ret_cid.upper() not in available_ids:
                warnings.append(
                    f"Môn {ret_cid} muốn học lại/cải thiện nhưng KHÔNG được mở trong kỳ này."
                )
            elif ret_cid.upper() not in {s.course_id.upper() for s in selected}:
                warnings.append(
                    f"Môn {ret_cid} muốn học lại/cải thiện nhưng chưa được chọn (có thể do vượt ràng buộc)."
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


def _get_category(group: CourseGroup, retake_set: set[str]) -> str:
    """Xác định category của môn."""
    cid = group.course_id.upper()
    if cid in retake_set:
        return "retake"
    else:
        # Kiểm tra môn tiếng Anh
        for eng_list in ENGLISH_COURSE_MAP.values():
            for eng in eng_list:
                if cid == eng["course_id"].upper():
                    return "english"
        # Kiểm tra môn thể dục
        pe_names_lower = set(name.lower() for name in DEFAULT_PE_COURSES)
        if group.course_name.lower() in pe_names_lower or "thể dục" in group.course_name.lower() or "giáo dục thể chất" in group.course_name.lower():
            return "pe"
        return "new"


def _get_category_label(category: str) -> str:
    """Lấy nhãn hiển thị cho category."""
    labels = {
        "retake": "📚 Học lại/Cải thiện",
        "english": "🇬🇧 Tiếng Anh",
        "pe": "🏃 Thể dục",
        "new": "📖 Môn mới",
        "completed": "✅ Đã pass",
    }
    return labels.get(category, category)


def _has_conflict(new_slots: list[tuple[int, int, int]], selected: list[ScheduleItem]) -> bool:
    """
    Kiểm tra xem new_slots có xung đột với các môn đã chọn không.
    Mỗi slot là (day, start_period, end_period).
    """
    # Thu thập tất cả các slot đã dùng
    used_slots = set()
    for item in selected:
        for slot in item.schedule_slots:
            used_slots.add(slot)
    
    # Kiểm tra xung đột
    for new_slot in new_slots:
        if new_slot in used_slots:
            return True
        # Kiểm tra overlap (cùng ngày, có tiết chung)
        new_day, new_start, new_end = new_slot
        for used_slot in used_slots:
            used_day, used_start, used_end = used_slot
            if new_day == used_day:
                # Kiểm tra overlap: [new_start, new_end] overlaps [used_start, used_end]
                if not (new_end < used_start or new_start > used_end):
                    return True
    
    return False


def _to_item_from_group(group: CourseGroup, reason: str, category: str = "new") -> ScheduleItem:
    """Convert CourseGroup → ScheduleItem."""
    ma_lop = group.theory_classes[0].ma_lop if group.theory_classes else group.course_id
    
    # Get schedule slots from theory classes
    schedule_slots = []
    if group.theory_classes:
        schedule_slots = group.theory_classes[0].schedule_slots
    
    return ScheduleItem(
        course_id=group.course_id,
        course_name=group.course_name,
        credits=group.total_credits,
        ma_lop=ma_lop,
        reason=reason,
        category=category,
        schedule_slots=schedule_slots,
    )
