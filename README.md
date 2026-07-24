# DDSwithData — Hệ thống Hỗ trợ Lập lộ trình Học tập & Đăng ký Môn học

**Môn học:** Data-Driven Systems (DDS)
**Trường:** Đại học Công nghệ Thông tin — ĐHQG TP.HCM (UIT)
**Nhóm:** 13 — Đinh Minh Tuấn (250201097) | GVHD: Lê Thanh Tùng

---

## Chạy Demo

Ứng dụng là 1 FastAPI backend phục vụ luôn frontend (Jinja2 + Bootstrap) — **không có server frontend riêng để chạy**, chỉ cần khởi động backend. Vào trang chủ: chọn ngành/khóa/(tùy chọn) hướng chuyên ngành, upload file thời khóa biểu thật, chọn engine **GP1** (luật & đồ thị) hoặc **GP2** (mô hình đã train) → nhận đề xuất môn học kèm giải thích.

### Cách 1 — Docker (khuyến nghị, không cần cài Python)

Yêu cầu: [Docker Desktop](https://www.docker.com/products/docker-desktop/) đang chạy.

```bash
./setup.sh
# hoặc thủ công:
docker compose up --build -d
```

Mở **http://localhost:8000**. Xem log: `docker compose logs -f`. Dừng: `docker compose down`.

### Cách 2 — Chạy local không cần Docker

Yêu cầu: Python 3.11–3.13 (Python 3.14 hiện chưa có sẵn wheel cho một số thư viện — sẽ phải build từ source rất lâu, nên tránh nếu có bản Python khác).

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt

cd backend
uvicorn app.main:app --reload --port 8000
```

Mở **http://localhost:8000**. Backend tự đọc `data/`, `frontend/templates`, `frontend/static` theo đường dẫn tương đối tới repo root — không cần biến môi trường nào thêm khi chạy local.

### Thử ngay trong UI

1. Vào http://localhost:8000
2. Upload file `TKB_KHDT_25-12-2024_1735115467_HK_2_NH2024.xlsx` có sẵn ở thư mục gốc repo (danh sách lớp thật đang mở HK2 2024–2025, gồm cả lớp lý thuyết + thực hành)
3. Chọn ngành, khóa tuyển sinh, các môn đã hoàn thành
4. (Tùy chọn) chọn định hướng chuyên ngành — hệ thống dùng GTE embedding để ưu tiên môn liên quan
5. Chọn engine **GP1** hoặc **GP2**, bấm đề xuất — so sánh thử cả hai với cùng input

### Kiểm thử / tái lập kết quả (chạy từ thư mục gốc repo, không cần `cd`)

```bash
python scripts/evaluate_recommender.py   # so sánh GP1 vs GP2 (leave-future-out trên 832 nhãn thật)
python scripts/test_optimizer_cases.py   # 4 case sinh viên thật: thiếu tiếng Anh, học lại, thiếu tiên quyết, tiến độ bình thường
python scripts/test_track_weighting.py   # chứng minh track-weighting đổi thứ tự đề xuất (cần mạng để tải model GTE lần đầu)
python scripts/train_ranker.py           # train lại model GP2 — không bắt buộc, artifact đã có sẵn ở data/models/
```

Kiến trúc chi tiết: [docs/system_design.md](docs/system_design.md).

---

## Phạm vi dữ liệu (Data Scope)

### Trường & Hệ đào tạo
- **Trường:** Đại học Công nghệ Thông tin UIT (ĐHQG-HCM)
- **Hệ:** Đại học chính quy (hệ tín chỉ)

### Khóa học (Cohorts)
Phủ toàn bộ các khóa có chương trình đào tạo riêng trên cổng student.uit.edu.vn.

| Khóa | Năm nhập học | Ghi chú |
|------|-------------|---------|
| K2012 | 2012 | |
| K2013 | 2013 | |
| K2014 | 2014 | |
| K2015 | 2015 | |
| K2016 | 2016 | |
| K2017 | 2017 | |
| K2018 | 2018 | |
| K2019 | 2019 | |
| K2020 | 2020 | |
| K2021 | 2021 | |
| K2022 | 2022 | |
| K2023 | 2023 | |
| K2024 | 2024 | Thêm ngành KHdl |
| K2025 | 2025 | |
| K2026 | 2026 | |

> Các khóa K2011 trở về trước dùng chung khung CTĐT cũ, không có trang riêng — không đưa vào scope.

### Ngành đào tạo (Majors)
| Mã | Tên ngành |
|----|-----------|
| ATTT | An toàn Thông tin |
| CNTT | Công nghệ Thông tin |
| HTTT | Hệ thống Thông tin |
| KHdl | Khoa học Dữ liệu _(từ K2024)_ |
| KHMT | Khoa học Máy tính |
| KTMT | Kỹ thuật Máy tính |
| KTPM | Kỹ thuật Phần mềm |
| MMT&TTDL | Mạng máy tính & Truyền thông Dữ liệu |
| TMDT | Thương mại Điện tử |

---

## Cấu trúc thư mục

```
data/
├── raw/                        # Dữ liệu thô gốc
│   ├── K2019/
│   │   ├── ATTT/
│   │   ├── CNTT/
│   │   ├── HTTT/
│   │   ├── KHMT/
│   │   ├── KTMT/
│   │   ├── KTPM/
│   │   ├── MMT&TTDL/
│   │   └── TMDT/
│   ├── K2020/ ... K2023/       # Cùng cấu trúc như K2019
│   └── K2024/
│       ├── ...                 # Tất cả ngành trên
│       └── KHdl/              # Thêm Khoa học Dữ liệu từ K2024
├── processed/                  # Dữ liệu đã làm sạch & chuẩn hóa
└── external/                   # Khung CTĐT, Knowledge Graph
```

---

## Nguồn dữ liệu

### 1. Khung Chương trình Đào tạo & Sơ đồ Ràng buộc
- **Nguồn:** Website Phòng Đào tạo UIT
- **Định dạng:** JSON / CSV
- **Quy mô:** ~10 chương trình, ~400 mã môn học
- **Vai trò:** Xây dựng Knowledge Graph, thiết lập luật ràng buộc (tiên quyết, song hành, tín chỉ tối thiểu/tối đa)

### 2. Lịch sử Học tập & Bảng điểm Sinh viên
- **Nguồn:** Hệ thống quản lý học vụ UIT (mô phỏng/chuẩn hóa)
- **Định dạng:** SQL / CSV (bảng quan hệ)
- **Quy mô:** 50–100 SV các khóa trước, ~5.000–10.000 dòng điểm chi tiết
- **Vai trò:** Đánh giá GPA trung bình, độ khó từng môn học

---

## Mục tiêu hệ thống

Hệ thống hỗ trợ sinh viên và cố vấn học tập:
- **Gợi ý lộ trình:** Danh sách môn nên đăng ký học kỳ tới kèm số tín chỉ tối ưu
- **Cảnh báo rủi ro:** Vi phạm tiên quyết, quá tải tín chỉ, nguy cơ cảnh báo học vụ
- **Phục hồi sau rủi ro:** Kịch bản học bù/học lại tối ưu hóa thời gian tốt nghiệp

## Hai giải pháp đề xuất

| | GP1: Luật & Đồ thị | GP2: Machine Learning |
|---|---|---|
| Tuân thủ quy chế | 100% | Tương đối |
| Cá nhân hóa | Thấp | Cao |
| Giải thích được | Rõ ràng | Khó |
| Chi phí tính toán | Thấp | Cao |
