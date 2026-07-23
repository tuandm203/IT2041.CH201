"""
Scheduler service — entry point cho logic tối ưu thời khóa biểu.

Hiện tại delegate cho optimizer.optimize_schedule().
Các tiêu chí mở rộng (ví dụ: ưu tiên môn học trước, tránh mâu thuẫn lịch)
sẽ được thêm vào optimizer.py.
"""

from typing import Optional
from app.models.schedule import OptimizeRequest, OptimizeResponse
from app.core.optimizer import optimize_schedule as _optimize

__all__ = ["optimize_schedule"]


def optimize_schedule(
    req: OptimizeRequest,
    practical_map: Optional[dict[str, str]] = None,
) -> OptimizeResponse:
    """Wrapper để gọi optimizer."""
    return _optimize(req, practical_map)
