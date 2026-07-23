"""
API routes — Schedule Optimizer

Endpoints:
  GET  /              → trang chủ (form upload)
  POST /optimize      → nhận file Excel + ràng buộc → trả kết quả
  GET  /health        → health check
"""

from fastapi import APIRouter, Request, File, UploadFile, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi import status

from app.models.schedule import OptimizeRequest, OptimizeResponse
from app.services.excel_parser import parse_excel_file
from app.services.scheduler import optimize_schedule

router = APIRouter()


# ── Health check ───────────────────────────────────────────────────────────────

@router.get("/health", response_class=JSONResponse)
async def health_check():
    """Kiểm tra service còn sống không."""
    return {"status": "ok", "service": "schedule-optimizer"}


# ── Trang chủ — form upload ────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render trang chủ với form upload file Excel."""
    return app_templates(request, "index.html")


# ── Xử lý tối ưu thời khóa biểu ────────────────────────────────────────────────

@router.post("/optimize", response_class=HTMLResponse)
async def optimize(
    request: Request,
    file: UploadFile = File(...),
    min_credits: int = Form(..., ge=1, le=50),
    max_credits: int = Form(..., ge=1, le=50),
    max_courses: int = Form(None, ge=1, le=20),
):
    """
    Nhận file Excel + ràng buộc → đề xuất thời khóa biểu.

    Parameters:
      file:        File Excel (.xlsx) chứa danh sách môn học
      min_credits: Số tín chỉ tối thiểu cần đăng ký
      max_credits: Số tín chỉ tối đa được phép đăng ký
      max_courses: Số môn tối đa (tùy chọn)
    """
    # Validate file
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        return app_templates(
            request, "index.html",
            error="Vui lòng tải lên file Excel (.xlsx hoặc .xls)",
        )

    # Parse Excel
    try:
        courses = await parse_excel_file(file)
    except Exception as e:
        return app_templates(
            request, "index.html",
            error=f"Lỗi đọc file Excel: {str(e)}",
        )

    if not courses:
        return app_templates(
            request, "index.html",
            error="File Excel không có dữ liệu môn học hợp lệ.",
        )

    # Build request model
    req = OptimizeRequest(
        min_credits=min_credits,
        max_credits=max_credits,
        max_courses=max_courses,
        courses=courses,
    )

    # Run optimizer
    result = optimize_schedule(req)

    return app_templates(request, "result.html", result=result)


# ── Helper ───────────────────────────────────────────────────────────────────────

def app_templates(request: Request, template_name: str, **context):
    """Render template với context mặc định."""
    from app.main import templates
    return templates.TemplateResponse(request, template_name, context)
