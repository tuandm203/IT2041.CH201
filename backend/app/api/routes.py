"""
API routes — Schedule Optimizer

Endpoints:
  GET  /                    → trang chủ (multi-step form)
  POST /api/parse           → parse file, trả về JSON (danh sách môn + khoa)
  POST /api/parse-full      → parse file + trả về full info (cho các bước form)
  POST /optimize            → nhận file Excel + ràng buộc + profile → trả kết quả
  GET  /progress            → trang tiến độ học tập
  POST /api/progress-data   → API trả dữ liệu cho trang progress
  GET  /health              → health check
"""

from fastapi import APIRouter, Request, File, UploadFile, Form, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi import status

from typing import Literal, Optional
from app.models.schedule import (
    OptimizeRequest, OptimizeResponse, StudentProfile,
    EnglishLevel, DEFAULT_PE_COURSES, TRAINING_SYSTEM_LIST,
    ENGLISH_COURSE_MAP,
)
from app.services.excel_parser import parse_excel_file
from app.services.scheduler import optimize_schedule

router = APIRouter()


# ── Health check ───────────────────────────────────────────────────────────────

@router.get("/health", response_class=JSONResponse)
async def health_check():
    """Kiểm tra service còn sống không."""
    return {"status": "ok", "service": "schedule-optimizer"}


# ── Trang chủ — multi-step form ───────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render trang chủ với multi-step form."""
    return app_templates(request, "index.html")


# ── API: Parse file Excel — trả về full info ─────────────────────────────────

@router.post("/api/parse", response_class=JSONResponse)
async def api_parse(file: UploadFile = File(...)):
    """
    Parse file Excel, trả về JSON với course_groups, departments, và danh sách course_ids.
    Dùng cho bước 1 (upload) + bước 2 (chọn môn đã pass / cải thiện / học lại).
    """
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        return JSONResponse(
            status_code=400,
            content={"error": "Vui lòng tải lên file Excel (.xlsx hoặc .xls)"},
        )

    try:
        course_groups, departments = await parse_excel_file(file)
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"error": f"Lỗi đọc file Excel: {str(e)}"},
        )

    if not course_groups:
        return JSONResponse(
            status_code=400,
            content={"error": "File Excel không có dữ liệu môn học hợp lệ."},
        )

    # Chuyển sang dict để trả về JSON
    groups_data = []
    for g in course_groups:
        groups_data.append({
            "course_id": g.course_id,
            "course_name": g.course_name,
            "total_credits": g.total_credits,
            "has_practical": g.has_practical,
            "department": g.department,
            "note": g.note,
            "theory_classes": [
                {
                    "ma_lop": c.ma_lop,
                    "credits": c.credits,
                    "credits_lt": c.credits_lt,
                    "credits_th": c.credits_th,
                    "htgd": c.htgd,
                }
                for c in g.theory_classes
            ],
            "practical_classes": [
                {
                    "ma_lop": c.ma_lop,
                    "credits": c.credits,
                    "htgd": c.htgd,
                }
                for c in g.practical_classes
            ],
        })

    return JSONResponse(content={
        "course_groups": groups_data,
        "departments": sorted(departments),
        "course_ids": sorted([g.course_id for g in course_groups]),
    })


# ── API: Trả về dữ liệu mẫu cho form (PE courses, training systems, English levels) ────

@router.get("/api/form-data", response_class=JSONResponse)
async def get_form_data():
    """Trả về danh sách các lựa chọn có sẵn cho form."""
    return JSONResponse(content={
        "pe_courses": DEFAULT_PE_COURSES,
        "training_systems": TRAINING_SYSTEM_LIST,
        "english_levels": [
            {"value": "passed", "label": "✅ Đã pass (đạt đầu ra)"},
            {"value": "b2", "label": "B2 - Cao trung cấp (đầu ra)"},
            {"value": "b1", "label": "B1 - Trung cấp (đầu vào)"},
            {"value": "a2", "label": "A2 - Sơ cấp"},
            {"value": "a1", "label": "A1 - Cơ bản"},
        ],
        "english_courses": ENGLISH_COURSE_MAP,
    })


# ── Xử lý tối ưu thời khóa biểu ────────────────────────────────────────────────

@router.post("/optimize", response_class=HTMLResponse)
async def optimize(
    request: Request,
    file: UploadFile = File(...),
    min_credits: int = Form(..., ge=1, le=50),
    max_credits: int = Form(..., ge=1, le=50),
    max_courses: Optional[str] = Form(None),
    practical_choices: Optional[str] = Form(None),
    department: Optional[str] = Form(None),
    # Student profile fields
    training_system: Optional[str] = Form(None),
    major: Optional[str] = Form(None),
    cohort: Optional[str] = Form(None),
    engine: Literal["gp1", "gp2"] = Form("gp1"),
    english_level: Optional[str] = Form("b1"),
    passed_pe_courses: Optional[str] = Form(None),      # comma-separated
    completed_courses: Optional[str] = Form(None),       # comma-separated
    retake_courses: Optional[str] = Form(None),          # comma-separated
    skip_pe_if_completed: Optional[str] = Form(None),    # "true" or "false"
):
    """
    Nhận file Excel + ràng buộc + thông tin sinh viên → đề xuất thời khóa biểu.
    """
    # Validate file
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        return app_templates(
            request, "index.html",
            error="Vui lòng tải lên file Excel (.xlsx hoặc .xls)",
        )

    # Parse max_courses: chuỗi rỗng → None
    max_courses_int: Optional[int] = None
    if max_courses and max_courses.strip():
        try:
            max_courses_int = int(max_courses.strip())
            if max_courses_int < 1 or max_courses_int > 20:
                max_courses_int = None
        except ValueError:
            max_courses_int = None

    # Parse Excel → list[CourseGroup]
    try:
        course_groups, _ = await parse_excel_file(file)
    except Exception as e:
        return app_templates(
            request, "index.html",
            error=f"Lỗi đọc file Excel: {str(e)}",
        )

    if not course_groups:
        return app_templates(
            request, "index.html",
            error="File Excel không có dữ liệu môn học hợp lệ.",
        )

    # Lọc theo khoa nếu có
    if department and department.strip():
        dept = department.strip().upper()
        course_groups = [g for g in course_groups if g.department and g.department.upper() == dept]

    if not course_groups:
        return app_templates(
            request, "index.html",
            error=f"Không có môn học nào thuộc khoa '{department}'.",
        )

    # Parse practical_choices
    practical_map: dict[str, str] = {}
    if practical_choices:
        for pair in practical_choices.split(","):
            pair = pair.strip()
            if ":" in pair:
                cid, ma_lop = pair.split(":", 1)
                practical_map[cid.strip()] = ma_lop.strip()

    # Parse skip_pe_if_completed
    skip_pe = bool(
        skip_pe_if_completed
        and skip_pe_if_completed.strip().lower() == "true"
    )

    # Parse student profile
    student_profile = StudentProfile(
        training_system=training_system if training_system else None,
        major=major if major else None,
        cohort=cohort if cohort else None,
        english_level=english_level if english_level else "b1",
        passed_pe_courses=_parse_comma_list(passed_pe_courses),
        completed_courses=_parse_comma_list(completed_courses),
        retake_courses=_parse_comma_list(retake_courses),
        skip_pe_if_completed=skip_pe,
    )

    # Build request model
    req = OptimizeRequest(
        min_credits=min_credits,
        max_credits=max_credits,
        max_courses=max_courses_int,
        course_groups=course_groups,
        student=student_profile,
        engine=engine,
    )

    # Run optimizer
    result = optimize_schedule(req, practical_map)

    return app_templates(
        request,
        "result.html",
        result=result,
        show_priority=any(
            item.priority_score is not None for item in result.selected
        ),
    )


# ── API: Progress data ───────────────────────────────────────────────────────

@router.post("/api/progress-data", response_class=JSONResponse)
async def get_progress_data(
    file: UploadFile = File(...),
    training_system: Optional[str] = Form(None),
    english_level: Optional[str] = Form("b1"),
    passed_pe_courses: Optional[str] = Form(None),
    completed_courses: Optional[str] = Form(None),
    retake_courses: Optional[str] = Form(None),
):
    """
    API trả về dữ liệu tiến độ học tập dạng JSON để render dashboard.
    """
    # Parse Excel để lấy danh sách môn
    try:
        course_groups, departments = await parse_excel_file(file)
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"error": f"Lỗi đọc file: {str(e)}"},
        )

    if not course_groups:
        return JSONResponse(
            status_code=400,
            content={"error": "File không có dữ liệu."},
        )

    completed_set = set(c.strip().upper() for c in _parse_comma_list(completed_courses))
    retake_set = set(c.strip().upper() for c in _parse_comma_list(retake_courses))

    # Tính tiến độ
    total_available_credits = sum(g.total_credits for g in course_groups)
    completed_credits = sum(
        g.total_credits for g in course_groups
        if g.course_id.upper() in completed_set
    )
    retake_credits = sum(
        g.total_credits for g in course_groups
        if g.course_id.upper() in retake_set
    )

    # Danh sách môn đã pass
    passed_courses = [
        {"course_id": g.course_id, "course_name": g.course_name, "credits": g.total_credits}
        for g in course_groups if g.course_id.upper() in completed_set
    ]

    # Danh sách môn chưa pass (không trong completed, không retake)
    not_passed_courses = [
        {"course_id": g.course_id, "course_name": g.course_name, "credits": g.total_credits}
        for g in course_groups
        if g.course_id.upper() not in completed_set
        and g.course_id.upper() not in retake_set
    ]

    # PE progress
    pe_passed = _parse_comma_list(passed_pe_courses)
    pe_progress = {
        "passed": pe_passed,
        "passed_count": len(pe_passed),
    }

    # English info
    eng_progress = {
        "level": english_level,
        "is_passed": english_level == "passed",
    }

    return JSONResponse(content={
        "total": {
            "available_credits": total_available_credits,
            "completed_credits": completed_credits,
            "remaining_credits": total_available_credits - completed_credits,
            "total_courses": len(course_groups),
            "completed_courses": len(passed_courses),
            "not_passed_courses": len(not_passed_courses),
        },
        "passed_courses": passed_courses,
        "not_passed_courses": not_passed_courses,
        "retake_courses_count": len(retake_set),
        "pe_progress": pe_progress,
        "english_progress": eng_progress,
        "training_system": training_system,
        "departments": departments,
    })


# ── Trang tiến độ học tập ────────────────────────────────────────────────────

@router.get("/progress", response_class=HTMLResponse)
async def progress_page(request: Request):
    """Render trang tiến độ học tập."""
    return app_templates(request, "progress.html")


# ── Helper ────────────────────────────────────────────────────────────────────

def app_templates(request: Request, template_name: str, **context):
    """Render template với context mặc định."""
    from app.main import templates
    return templates.TemplateResponse(request, template_name, context)


def _parse_comma_list(value: Optional[str]) -> list[str]:
    """Parse chuỗi phân cách bằng dấu phẩy thành list."""
    if not value or not value.strip():
        return []
    return [item.strip() for item in value.split(",") if item.strip()]
