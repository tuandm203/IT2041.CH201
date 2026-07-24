FROM python:3.12-slim

WORKDIR /app

# Cài đặt dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY backend/app/ ./app/

# Copy frontend (templates + static)
COPY frontend/ ./frontend/

# Copy specialization anchor taxonomy
COPY notebooks/anchor_profiles.json ./notebooks/anchor_profiles.json

# Copy rule, curriculum, and trained model data
COPY data/ ./data/

# Copy the real sample TKB file used for the "Dùng file mẫu" quick-start button
COPY TKB_KHDT_25-12-2024_1735115467_HK_2_NH2024.xlsx ./TKB_KHDT_25-12-2024_1735115467_HK_2_NH2024.xlsx

# Tạo thư mục uploads
RUN mkdir -p /app/uploads

ENV DATA_DIR=/app/data
ENV SAMPLE_TKB_PATH=/app/TKB_KHDT_25-12-2024_1735115467_HK_2_NH2024.xlsx

# Expose port
EXPOSE 8000

# Chạy ứ dụng
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
