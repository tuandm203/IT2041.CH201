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

            if (majorSelect && selectedCase.major) {
                majorSelect.value = selectedCase.major;
                majorSelect.dispatchEvent(new Event("change"));
            }

            loadSampleTkb();
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
