/* Schedule Optimizer — Frontend JS */

document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("optimizeForm");
    const submitBtn = document.getElementById("submitBtn");

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
