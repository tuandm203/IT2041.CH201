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
