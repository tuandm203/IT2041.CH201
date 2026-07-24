# System Design — Course Recommendation Engine

**Trạng thái:** Kiến trúc đã chốt (2026-07), đang implement trên branch `dangnh`.
**Liên quan:** [research_directions.md](research_directions.md) (bối cảnh & hướng nghiên cứu đã chọn), [schemas/extraction_pipeline.md](schemas/extraction_pipeline.md) (pipeline sinh rule từ PDF).

---

## 1. Mental model

> Cho một sinh viên cụ thể (ngành, khóa, các môn đã hoàn thành) tại một học kỳ cụ thể (có danh sách lớp thực tế đang mở), hệ thống đề xuất **tổ hợp lớp học phần cụ thể** nên đăng ký, tối ưu theo tiến độ tốt nghiệp, đảm bảo tuân thủ 100% quy chế.

Kiến trúc 2 tầng:

```
Tầng 1 — CHỌN MÔN (What)              Tầng 2 — CHỌN LỚP (How)
KG tiên quyết + GP1/GP2 ranking  →    CSP trên TKB_KHDT thật
        ↓                                      ↓
  Danh sách môn nên học kỳ này    →    Lớp cụ thể, conflict-free,
  (đã lọc đủ tiên quyết)                trong trần tín chỉ quy chế
```

**Nguyên tắc thiết kế:** toàn bộ pipeline chỉ dùng dữ liệu thật đã có sẵn trong `data/` — không dùng bảng điểm SV thật (NDA), không dùng synthetic transcript. Phần "học" (GP2) dùng chính `semester` field thật trong khung CTĐT do trường công bố (K2012–K2015) làm nhãn giám sát.

---

## 2. Input / Output

### Input

| Nhóm | Trường | Nguồn |
|---|---|---|
| Hồ sơ SV | ngành (`major`), khóa (`cohort`), danh sách mã môn đã pass | SV tự nhập |
| Ràng buộc | min/max tín chỉ mong muốn kỳ này, `engine` (`gp1`/`gp2`) | SV tự nhập / mặc định |
| Cung thực tế | file TKB_KHDT của kỳ đăng ký (lớp, thứ, tiết, phòng, sĩ số) | `TKB_KHDT_*.xlsx` |
| Khung CTĐT | `knowledge_blocks`, `courses`, `total_credits` theo `{cohort, major}` | `data/programs/` |
| Rule tiên quyết | `COURSE_PREREQUISITE` (hard), `COURSE_PRIOR` (soft) | `data/rules/global/course_prerequisites_catalog.json` |
| Quy chế | trần tín chỉ, cảnh báo học vụ | `data/rules/global/quy_che_790_2022.json` |

### Output

| Thành phần | Nội dung |
|---|---|
| TKB đề xuất | danh sách lớp cụ thể (mã lớp, thứ, tiết, phòng, GV), conflict-free |
| Giải thích | mỗi môn kèm lý do: tiên quyết đã thỏa, unlock N môn, `priority_score` (nếu dùng GP2) |
| Cảnh báo | vượt trần TC, thiếu lớp phù hợp lịch, môn bị chặn do thiếu tiên quyết |

---

## 3. Pipeline tổng quan

```mermaid
flowchart TB
    subgraph DATA["Dữ liệu thật (data/)"]
        RULES["rules/global/\ncourse_prerequisites_catalog.json"]
        PROGRAMS["programs/{cohort}/{major}/\nstandard.json"]
        TKB["TKB_KHDT_*.xlsx\n(lớp thực tế đang mở)"]
    end

    subgraph GRAPH["prereq_graph.py"]
        G["DiGraph tiên quyết\n(hard + soft edges)"]
    end

    subgraph TRAIN["Offline — train 1 lần"]
        FEAT["course_features.py\n(graph_depth, unlock_count,\nis_mandatory, credits, block_category)"]
        LABELS["832 nhãn thật\n(course_id, major) → semester\nK2012–K2015"]
        RANKER_TRAIN["train_ranker.py\nRidge regression, GroupKFold(major)"]
        ARTIFACT["data/models/\ncourse_priority_ranker.joblib"]
    end

    subgraph SERVE["Runtime — mỗi request"]
        ELIG["is_eligible()\nlọc cứng theo completed_courses"]
        GP1["GP1: rank theo unlock_count\n(graph-only baseline)"]
        GP2["GP2: rank theo ranker.score_course()\n(model đã train)"]
        OPT["optimizer.py\n(greedy chọn lớp, credit limit,\nconflict check — đã có sẵn)"]
    end

    RULES --> G
    PROGRAMS --> LABELS
    PROGRAMS --> FEAT
    G --> FEAT
    FEAT --> RANKER_TRAIN
    LABELS --> RANKER_TRAIN
    RANKER_TRAIN --> ARTIFACT

    G --> ELIG
    ELIG --> GP1
    ELIG --> GP2
    ARTIFACT --> GP2
    GP1 --> OPT
    GP2 --> OPT
    TKB --> OPT
    OPT --> OUT["TKB đề xuất + giải thích + cảnh báo"]

    subgraph EVAL["evaluate_recommender.py"]
        LOO["Leave-future-out trên 832 nhãn thật:\nSV giả lập 'đã học kỳ 1..k' →\nso đề xuất GP1/GP2 với môn thật ở kỳ k+1"]
        METRICS["Precision@N / Recall@N\ntheo từng major"]
    end
    LABELS --> LOO
    GP1 -.-> LOO
    GP2 -.-> LOO
    LOO --> METRICS
```

---

## 4. Model

### GP1 — Rule & Graph (baseline)
Không train. Ưu tiên môn theo `unlock_count` (số môn hậu duệ trực tiếp/gián tiếp trong đồ thị tiên quyết) — proxy cho "critical path". Thay thế heuristic "sort theo credit tăng dần" của optimizer gốc.

### GP2 — Learning-to-Rank

| | |
|---|---|
| Task | Dự đoán `semester` kỳ vọng của môn → suy ra priority score |
| Label | `semester` thật, K2012–K2015 × 7 ngành = 832 dòng |
| Feature | `graph_depth`, `unlock_count`, `is_mandatory`, `credits`, `block_category` |
| Model | `sklearn.linear_model.Ridge` (giải thích được qua hệ số) |
| Split | `GroupKFold` theo `major` (bắt buộc — các khóa K2012–K2015 gần như trùng khung CTĐT, split theo cohort sẽ leak) |
| Inference | Áp cho khóa/ngành không có label thật (K2019+) dựa trên feature |

---

## 5. Đánh giá

Không dùng synthetic data, không cần user thật thử — dùng chính 832 nhãn thật làm test set qua **leave-future-out**: giả lập SV đã hoàn thành mọi môn có `semester < k` (theo khung chuẩn thật), so top-N đề xuất của GP1/GP2 với tập môn thật ở kỳ `k`. Bổ sung: formal rule-compliance check (100% output thỏa tiên quyết/tín chỉ), và (tùy thời gian) expert review nhỏ với cố vấn học tập.

---

## 6. Sản phẩm

1. Web app (FastAPI + Jinja2, kế thừa `backend/`/`frontend/` hiện có) — nhập hồ sơ SV + TKB kỳ hiện tại → TKB đề xuất kèm giải thích, so sánh GP1/GP2
2. `scripts/train_ranker.py` + artifact `data/models/course_priority_ranker.joblib` — tái lập được
3. `scripts/evaluate_recommender.py` — bảng so sánh GP1 vs GP2
4. Báo cáo/luận văn: phần thực nghiệm GP1 vs GP2 + compliance verification

---

## 7. Ánh xạ tới code (implementation)

| Thành phần | File |
|---|---|
| Đồ thị tiên quyết | `backend/app/services/prereq_graph.py` |
| Feature engineering | `backend/app/services/course_features.py` |
| Train GP2 | `scripts/train_ranker.py` |
| Serve GP2 | `backend/app/services/ranker.py` |
| Model schema (`engine`, `major`, `cohort`, `priority_score`) | `backend/app/models/schedule.py` |
| Lọc tiên quyết + chọn engine ranking | `backend/app/core/optimizer.py` |
| Đánh giá GP1 vs GP2 | `scripts/evaluate_recommender.py` |
| Wiring API | `backend/app/api/routes.py`, `backend/app/main.py` |

Chi tiết spec từng file: xem plan implementation đã chốt (đang thực thi trên branch `dangnh`).

---

## 8. Phạm vi & giới hạn

**Trong scope:** 1 hệ (đại học chính quy), 7 ngành có `semester` label đầy đủ (K2012–K2015) làm train/test chính; các ngành/khóa khác dùng model để infer (không có ground truth riêng để evaluate).

**Ngoài scope (hướng mở rộng):** dự đoán độ khó/rủi ro trượt môn (cần điểm SV thật), tối ưu đa học kỳ (multi-semester planning), cá nhân hóa theo "hướng chuyên ngành" qua course embedding (tham khảo Scholar Inbox — [docs/2025.acl-demo.30.pdf](2025.acl-demo.30.pdf)), real-time cập nhật sĩ số lớp.
