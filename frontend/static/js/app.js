/* Schedule Optimizer — Frontend JS */

document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("optimizeForm");
    const submitBtn = document.getElementById("submitBtn");
    const majorSelect = document.getElementById("major");
    const trackSelect = document.getElementById("track");
    const trackField = document.getElementById("trackField");
    let trackProfiles = {};

    function updateTrackOptions() {
        if (!majorSelect || !trackSelect || !trackField) {
            return;
        }

        const anchors = trackProfiles[majorSelect.value] || [];
        trackSelect.innerHTML = '<option value="">— Không chọn định hướng —</option>';

        if (anchors.length === 0) {
            trackSelect.disabled = true;
            trackField.classList.add("hidden");
            return;
        }

        anchors.forEach(function (anchor) {
            const option = document.createElement("option");
            option.value = anchor.key;
            option.textContent = anchor.name;
            option.title = anchor.description || "";
            trackSelect.appendChild(option);
        });
        trackSelect.disabled = false;
        trackField.classList.remove("hidden");
    }

    if (majorSelect) {
        fetch("/api/form-data")
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("Không thể tải dữ liệu ngành học");
                }
                return response.json();
            })
            .then(function (data) {
                trackProfiles = data.track_profiles || {};
                (data.majors || []).forEach(function (major) {
                    const option = document.createElement("option");
                    option.value = major;
                    option.textContent = major;
                    majorSelect.appendChild(option);
                });
                updateTrackOptions();
            })
            .catch(function (error) {
                console.warn("Không thể tải định hướng chuyên ngành:", error);
            });
        majorSelect.addEventListener("change", updateTrackOptions);
    }

    // "Dùng file mẫu có sẵn" — tải file TKB thật đã bundle sẵn trong repo và
    // gán thẳng vào input[type=file] qua DataTransfer (không cần user tự chọn).
    const useSampleBtn = document.getElementById("useSampleBtn");
    const sampleStatus = document.getElementById("sampleStatus");
    const fileInputEl = document.getElementById("file");

    function loadSampleTkb() {
        if (!fileInputEl) return Promise.resolve();
        if (useSampleBtn) {
            useSampleBtn.disabled = true;
            useSampleBtn.textContent = "⏳ Đang tải file mẫu...";
        }
        if (sampleStatus) sampleStatus.textContent = "";

        return fetch("/api/sample-tkb")
            .then(function (response) {
                if (!response.ok) throw new Error("Không tải được file mẫu");
                const disposition = response.headers.get("Content-Disposition") || "";
                const match = disposition.match(/filename="?([^"]+)"?/);
                const filename = match ? match[1] : "TKB_mau.xlsx";
                return response.blob().then(function (blob) { return { blob: blob, filename: filename }; });
            })
            .then(function (result) {
                const file = new File([result.blob], result.filename, {
                    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                });
                const dataTransfer = new DataTransfer();
                dataTransfer.items.add(file);
                fileInputEl.files = dataTransfer.files;

                const fileErr = document.getElementById("fileError");
                if (fileErr) fileErr.classList.remove("show");
                if (sampleStatus) sampleStatus.textContent = "✓ Đã dùng " + result.filename;
                // Gán qua DataTransfer không tự bắn sự kiện "change" như user
                // thật chọn file, nên phải tự cập nhật preview ở đây.
                renderProfilePreview();
            })
            .catch(function (error) {
                if (sampleStatus) sampleStatus.textContent = "Không tải được file mẫu.";
                console.warn("Lỗi tải file mẫu:", error);
            })
            .finally(function () {
                if (useSampleBtn) {
                    useSampleBtn.textContent = "⚡ Dùng file mẫu có sẵn (TKB thật HK2 2024–2025)";
                    useSampleBtn.disabled = false;
                }
            });
    }

    if (useSampleBtn) {
        useSampleBtn.addEventListener("click", loadSampleTkb);
    }

    // Checkbox "Đã hoàn thành GDTC" chỉ hiện 1 field cho người dùng, nhưng
    // backend cần 2 field: skip_pe_if_completed (bool) + passed_pe_courses
    // (phải khác rỗng để logic bỏ qua môn TD thật sự kích hoạt).
    const skipPeCheckbox = document.getElementById("skipPeCheckbox");
    const skipPeHidden = document.getElementById("skip_pe_if_completed");
    const passedPeHidden = document.getElementById("passed_pe_courses");
    if (skipPeCheckbox && skipPeHidden && passedPeHidden) {
        skipPeCheckbox.addEventListener("change", function () {
            skipPeHidden.value = skipPeCheckbox.checked ? "true" : "false";
            passedPeHidden.value = skipPeCheckbox.checked ? "Đã hoàn thành" : "";
        });
    }

    // ── Hồ sơ đang dùng — preview trực quan, cập nhật theo trạng thái form ──
    const previewBody = document.getElementById("profilePreviewBody");
    const englishLevelSelect = document.getElementById("english_level");
    const ENGLISH_LABELS = { passed: "Đã pass đầu ra", a1: "A1", a2: "A2", b1: "B1", b2: "B2" };

    function chipList(csv, emptyText) {
        const items = (csv || "").split(",").map(function (s) { return s.trim(); }).filter(Boolean);
        if (items.length === 0) {
            return '<span class="muted">' + emptyText + '</span>';
        }
        const shown = items.slice(0, 12);
        let html = '<div class="preview-chips">';
        shown.forEach(function (item) { html += '<span class="preview-chip">' + item + '</span>'; });
        if (items.length > shown.length) {
            html += '<span class="preview-chip more">+' + (items.length - shown.length) + ' môn khác</span>';
        }
        html += '</div>';
        return '<span class="preview-value">' + items.length + ' môn</span>' + html;
    }

    function renderProfilePreview() {
        if (!previewBody) return;

        const major = majorSelect ? majorSelect.value : "";
        const cohort = document.getElementById("cohort");
        const trackVal = trackSelect ? trackSelect.value : "";
        const trackLabel = trackSelect && trackSelect.selectedOptions.length
            ? trackSelect.selectedOptions[0].textContent : "";
        const completed = document.getElementById("completed_courses");
        const retake = document.getElementById("retake_courses");
        const minC = document.getElementById("min_credits");
        const maxC = document.getElementById("max_credits");
        const engLabel = englishLevelSelect ? (ENGLISH_LABELS[englishLevelSelect.value] || englishLevelSelect.value) : "B1";
        const fileName = fileInputEl && fileInputEl.files && fileInputEl.files[0] ? fileInputEl.files[0].name : null;

        let html = '<div class="preview-grid">';

        html += '<div class="preview-item"><div class="preview-label">File TKB</div><div class="preview-value">'
            + (fileName ? '✓ ' + fileName : '<span class="muted">Chưa chọn</span>') + '</div></div>';

        html += '<div class="preview-item"><div class="preview-label">Ngành / Khóa</div><div class="preview-value">'
            + (major ? major : '<span class="muted">Không chọn</span>') + (cohort && major ? ' / ' + cohort.value : '')
            + '</div></div>';

        if (trackVal) {
            html += '<div class="preview-item"><div class="preview-label">Định hướng</div><div class="preview-value">' + trackLabel + '</div></div>';
        }

        html += '<div class="preview-item"><div class="preview-label">Trình độ tiếng Anh</div><div class="preview-value">' + engLabel + '</div></div>';

        html += '<div class="preview-item"><div class="preview-label">Ràng buộc tín chỉ</div><div class="preview-value">'
            + (minC ? minC.value : '?') + '–' + (maxC ? maxC.value : '?') + ' TC</div></div>';

        html += '<div class="preview-item"><div class="preview-label">Môn đã hoàn thành</div>'
            + chipList(completed ? completed.value : "", "Chưa có") + '</div>';

        html += '<div class="preview-item"><div class="preview-label">Muốn học lại</div>'
            + chipList(retake ? retake.value : "", "Không có") + '</div>';

        html += '</div>';
        previewBody.innerHTML = html;
    }

    [
        "major", "track", "cohort", "completed_courses", "retake_courses",
        "min_credits", "max_credits", "english_level", "file",
    ].forEach(function (id) {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener("change", renderProfilePreview);
            el.addEventListener("input", renderProfilePreview);
        }
    });
    renderProfilePreview();

    // "Hồ sơ sinh viên mẫu" — điền nhanh ngành/khóa/môn đã học/TC dựa trên
    // data/train/student_case_*.json, kèm luôn file TKB mẫu để demo 1 click
    // thay vì phải tự gõ hàng chục mã môn.
    const sampleCaseSelect = document.getElementById("sampleCase");
    let sampleCases = [];

    if (sampleCaseSelect) {
        fetch("/api/sample-cases")
            .then(function (response) {
                if (!response.ok) throw new Error("Không thể tải hồ sơ mẫu");
                return response.json();
            })
            .then(function (cases) {
                sampleCases = cases || [];
                sampleCases.forEach(function (c, idx) {
                    const option = document.createElement("option");
                    option.value = String(idx);
                    option.textContent = c.case_name + " (" + c.major + "/" + c.cohort + ")";
                    option.title = c.description || "";
                    sampleCaseSelect.appendChild(option);
                });
            })
            .catch(function (error) {
                console.warn("Không thể tải hồ sơ sinh viên mẫu:", error);
            });

        sampleCaseSelect.addEventListener("change", function () {
            if (sampleCaseSelect.value === "") return;
            const selectedCase = sampleCases[parseInt(sampleCaseSelect.value, 10)];
            if (!selectedCase) return;

            const setValue = function (id, value) {
                const el = document.getElementById(id);
                if (el != null && value != null) el.value = value;
            };

            setValue("min_credits", selectedCase.min_credits);
            setValue("max_credits", selectedCase.max_credits);
            setValue("completed_courses", (selectedCase.completed_courses || []).join(", "));
            setValue("retake_courses", (selectedCase.retake_courses || []).join(", "));
            setValue("cohort", selectedCase.cohort);
            if (selectedCase.english_level) setValue("english_level", selectedCase.english_level);

            if (majorSelect && selectedCase.major) {
                majorSelect.value = selectedCase.major;
                majorSelect.dispatchEvent(new Event("change"));
            }

            loadSampleTkb();
            renderProfilePreview();
        });
    }

    const fileError = document.getElementById("fileError");
    const creditError = document.getElementById("creditError");

    if (form) {
        form.addEventListener("submit", function (e) {
            const fileInput = document.getElementById("file");
            const minCredits = document.getElementById("min_credits").value;
            const maxCredits = document.getElementById("max_credits").value;
            let hasError = false;

            if (fileError) fileError.classList.remove("show");
            if (creditError) creditError.classList.remove("show");

            // Validate file
            if (!fileInput.files || fileInput.files.length === 0) {
                if (fileError) fileError.classList.add("show");
                hasError = true;
            }

            // Validate min <= max
            if (parseInt(minCredits) > parseInt(maxCredits)) {
                if (creditError) creditError.classList.add("show");
                hasError = true;
            }

            if (hasError) {
                e.preventDefault();
                return;
            }

            // Show loading
            submitBtn.disabled = true;
            submitBtn.innerHTML = "⏳ Đang xử lý...";
        });
    }

    // Auto-format: nếu người dùng nhập min > max, tự động điều chỉnh
    const minInput = document.getElementById("min_credits");
    const maxInput = document.getElementById("max_credits");

    if (minInput && maxInput) {
        minInput.addEventListener("change", function () {
            if (parseInt(this.value) > parseInt(maxInput.value)) {
                maxInput.value = this.value;
            }
        });
        maxInput.addEventListener("change", function () {
            if (parseInt(this.value) < parseInt(minInput.value)) {
                minInput.value = this.value;
            }
        });
    }
});
