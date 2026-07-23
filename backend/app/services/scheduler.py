"""
Scheduler service — entry point cho logic tối ưu thời khóa biểu.

Hiện tại delegate cho optimizer.optimize_schedule().
Các tiêu chí mở rộng (ví dụ: ưu tiên môn học trước, tránh mâu thuẫn lịch)
sẽ được thêm vào optimizer.py.
"""

from app.models.schedule import OptimizeRequest, OptimizeResponse
from app.core.optimizer import optimize_schedule

__all__ = ["optimize_schedule"]
