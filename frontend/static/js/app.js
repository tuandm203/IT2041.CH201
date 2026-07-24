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
            trackField.classList.add("d-none");
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
        trackField.classList.remove("d-none");
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

    if (form) {
        form.addEventListener("submit", function (e) {
            const fileInput = document.getElementById("file");
            const minCredits = document.getElementById("min_credits").value;
            const maxCredits = document.getElementById("max_credits").value;

            // Validate file
            if (!fileInput.files || fileInput.files.length === 0) {
                e.preventDefault();
                alert("Vui lòng chọn file Excel trước khi đề xuất.");
                return;
            }

            // Validate min <= max
            if (parseInt(minCredits) > parseInt(maxCredits)) {
                e.preventDefault();
                alert("Số TC tối thiểu không được lớn hơn số TC tối đa.");
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
