FROM python:3.12-slim

WORKDIR /app

# Cài đặt dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY backend/app/ ./app/

# Copy frontend (templates + static)
COPY frontend/ ./frontend/

# Copy rule, curriculum, and trained model data
COPY data/ ./data/

# Tạo thư mục uploads
RUN mkdir -p /app/uploads

ENV DATA_DIR=/app/data

# Expose port
EXPOSE 8000

# Chạy ứ dụng
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
