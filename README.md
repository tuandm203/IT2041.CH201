# DDSwithData — Hệ thống Hỗ trợ Lập lộ trình Học tập & Đăng ký Môn học

**Môn học:** Data-Driven Systems (DDS)
**Trường:** Đại học Công nghệ Thông tin — ĐHQG TP.HCM (UIT)
**Nhóm:** 13 — Đinh Minh Tuấn (250201097) | GVHD: Lê Thanh Tùng

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
