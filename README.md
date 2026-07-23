# Schedule Optimizer — Đề xuất thời khóa biểu

Hệ thống web **đề xuất thời khóa biểr** (schedule suggestion) dựa trên file Excel
chứa danh sách môn học kỳ tới, với các ràng buộc về số tín chỉ tối thiểu/tối đa
và các tiêu chí khác.

## Tính năng

- **Nhập file Excel**: tải lên file `.xlsx` chứa danh sách môn học kỳ tới
- **Cấu hình ràng buộc**: số tín chỉ tối thiểu, tối đa, số môn tối đa/kỳ
- **Đề xuất lộ trình**: hệ thống gợi ý danh sách môn nên đăng ký
- **Docker hóa**: chạy toàn bộ hệ thống bằng Docker Compose

## Cấu trúc dự án

```
schedule-optimizer/
├── backend/                     # Backend Python (FastAPI)
│   ├── app/
│   │   ├── api/                 # API routes
│   │   ├── core/                # Cấu hình, optimizer logic
│   │   ├── models/              # Pydantic data models
│   │   ├── services/            # Business logic (Excel parser, scheduler)
│   │   └── utils/               # Helper functions
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                    # Frontend (HTML + CSS + JS)
│   ├── templates/               # Jinja2 HTML templates
│   └── static/                  # CSS, JS
├── docker-compose.yml
├── setup.sh                     # Script cài đặt môi trường
└── README.md
```

## Cài đặt nhanh

### Dùng Docker (khuyên nghị)

```bash
./setup.sh
```

Hoặc thủ công:

```bash
docker compose up --build
```

Truy cập: http://localhost:8000

### Chạy local (không Docker)

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Định dạng file Excel

File Excel cần có các cột sau (tên cột không phân biệt hoa/thường):

| mã_môn | tên_môn        | tín_chỉ | họ_tên_môn | ghi_chú |
|--------|----------------|---------|------------|---------|
| IT001  | Nhập môn IT    | 3       | IT001      |         |
| IT002  | Lập trình C    | 4       | IT002      |         |

## Cấu hình ràng buộc

Thông qua giao diện web, người dùng có thể nhập:
- **Số tín chỉ tối thiểu** (ví dụ: 12)
- **Số tín chỉ tối đa** (ví dụ: 25)
- **Số môn tối đa** (tùy chọn)

## License

MIT
