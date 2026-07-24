# Rule Extraction Pipeline

## Kiến trúc 2 tầng

```
Nguồn dữ liệu                  Tier           Rule types
──────────────────────────────────────────────────────────────────
790/QĐ-ĐHCNTT-2022.pdf  ──►  GLOBAL    ──►  GRADE_SCALE
(1 file duy nhất)                            GPA_CALCULATION
                                             ENROLLMENT_CREDIT_LIMIT
                                             RETAKE_MANDATORY / OPTIONAL
                                             ATTENDANCE_REQUIREMENT
                                             ACADEMIC_WARNING / EXPULSION
                                             GRADUATION_BASE_REQUIREMENT
                                             GRADUATION_RANK / RANK_DOWNGRADE

CTĐT_{major}_{cohort}.pdf ──► CURRICULUM ──► PROGRAM_STRUCTURE
(15 khóa × 9 ngành = ~135 PDF)              COURSE_GROUP_REQUIREMENT
                                             COURSE_PREREQUISITE
                                             COURSE_PRIOR
                                             COURSE_COREQUISITE
                                             COURSE_EQUIVALENT
                                             COURSE_REPLACEMENT
                                             THESIS_ELIGIBILITY  (có thể override)
                                             FOREIGN_LANGUAGE_STANDARD (có thể override)
```

---

## Cấu trúc output sau khi extract

```
data/
├── schemas/
│   ├── hard_rules_schema.json        # Schema định nghĩa
│   ├── hard_rules_sample.json        # Ví dụ minh họa
│   └── extraction_pipeline.md        # File này
│
├── rules/
│   ├── global/
│   │   └── uit_quy_che_790_2022.json # Tất cả GLOBAL rules (1 file)
│   │
│   └── curriculum/
│       ├── K2019/
│       │   ├── CNTT.json
│       │   ├── HTTT.json
│       │   └── ...
│       ├── K2020/
│       │   └── ...
│       └── K2024/
│           ├── CNTT.json
│           └── KHdl.json             # Ngành mới từ K2024
│
└── raw/                              # PDF gốc sau khi crawl
    ├── K2019/
    │   ├── CNTT/
    │   │   └── ctdt_cntt_k2019.pdf
    │   └── ...
    └── ...
```

---

## Những gì cần crawl từ PDF CTĐT

### 1. Bảng danh sách học phần (table chính trong CTĐT)

Mỗi hàng trong bảng cần extract các cột:

| Cột trong PDF        | Field tương ứng              | Rule types tạo ra              |
|----------------------|------------------------------|-------------------------------|
| Mã học phần          | `course_id`                  | —                              |
| Tên học phần         | `course_name`                | —                              |
| Số tín chỉ           | `credits`                    | PROGRAM_STRUCTURE              |
| Loại HP              | `course_type`                | COURSE_GROUP_REQUIREMENT       |
| Học phần tiên quyết  | `prerequisite_ids`           | COURSE_PREREQUISITE            |
| Học phần học trước   | `prior_ids`                  | COURSE_PRIOR                   |
| Học phần song hành   | `corequisite_ids`            | COURSE_COREQUISITE             |
| Ghi chú              | `note`                       | COURSE_EQUIVALENT / REPLACEMENT|

### 2. Thông tin tổng quan CTĐT (đầu trang hoặc trang giới thiệu)

- Tên ngành, mã ngành
- Tổng số tín chỉ yêu cầu
- Thời gian đào tạo thiết kế (số kỳ)
- Cấu trúc khối kiến thức và TC tương ứng

### 3. Điều kiện đặc thù của ngành (thường ở cuối PDF hoặc phần quy định riêng)

- Chuẩn ngoại ngữ đầu ra (nếu khác quy chế)
- Điều kiện làm khóa luận (nếu khác quy chế)
- Môn thay thế / môn tương đương giữa các khóa

---

## Logic phân loại: GLOBAL vs CURRICULUM

```python
# Pseudocode hướng dẫn trích xuất

def classify_rule(rule, source_document):
    if source_document == "790/QĐ-ĐHCNTT-2022":
        return "global"           # Luôn là global
    
    if source_document.startswith("CTĐT"):
        if rule.type in ["COURSE_PREREQUISITE", "COURSE_PRIOR",
                         "COURSE_COREQUISITE", "COURSE_GROUP_REQUIREMENT",
                         "PROGRAM_STRUCTURE"]:
            return "curriculum"   # Luôn là curriculum

        if rule.type in ["THESIS_ELIGIBILITY", "FOREIGN_LANGUAGE_STANDARD"]:
            if overrides_global_value(rule):
                rule.overrides_rule = find_global_rule_id(rule.type)
            return "curriculum"   # Dù có override hay không vẫn là curriculum
```

---

## Xử lý sự không nhất quán mã môn giữa các khóa

Đây là thách thức lớn nhất khi crawl (đã nêu trong slide).

### Vấn đề:
- Môn "DevOps" ở K2021 là tự chọn → K2025 là bắt buộc
- Mã môn thay đổi giữa các khóa dù nội dung tương tự
- Một số môn bị split hoặc merge giữa các khóa

### Cách xử lý trong schema:

```json
// Bước 1: Mỗi CTĐT extract ra course list có course_id NGUYÊN GỐC
// Bước 2: Xây dựng bảng ánh xạ chuẩn hóa

{
  "canonical_course_id": "UIT_DEVOPS",
  "aliases": [
    {"course_id": "IT4090", "cohorts": ["K2019","K2020","K2021"], "type": "elective"},
    {"course_id": "IT4091", "cohorts": ["K2022","K2023"],         "type": "elective"},
    {"course_id": "IT4092", "cohorts": ["K2024","K2025"],         "type": "mandatory"}
  ],
  "equivalent_rule_id": "CR-XXX"
}
```

File ánh xạ này sẽ nằm ở `data/schemas/course_alias_map.json`.

---

## Thứ tự ưu tiên khi apply rules (Priority)

Khi kiểm tra một kế hoạch học tập của SV:

```
1. CURRICULUM rules của đúng {cohort, major}   (cao nhất)
   - Ghi đè GLOBAL nếu có overrides_rule
2. GLOBAL rules                                 (fallback)
   - Áp dụng nếu không có CURRICULUM rule tương ứng
3. Nếu không tìm thấy rule nào → WARNING, không block
```

---

## Ghi chú về các trường đặc biệt khi crawl PDF

| Trường trong PDF          | Cách nhận diện                          | Xử lý                          |
|---------------------------|------------------------------------------|-------------------------------|
| Điểm I (hoãn thi)         | Ký hiệu "I" trong cột điểm              | Không tính ĐTBHK kỳ đó        |
| Điểm BL (bảo lưu)         | Ký hiệu "BL"                            | Tính vào ĐTBC/ĐTBCTL          |
| Điểm R (quy đổi chứng chỉ)| Ký hiệu "R" hoặc ghi chú "Miễn"        | Loại khỏi tập train ML        |
| Môn GDTC, GDQP-AN         | Nhóm học phần điều kiện                 | Không tính vào GPA            |
| Môn Ngoại ngữ (CTĐT)      | Nhóm ngoại ngữ                          | Có lịch thi riêng, tính vào HK2 |
