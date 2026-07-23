#!/bin/bash
# setup.sh — Cài đặt và chạy Schedule Optimizer bằng Docker
set -e

echo "========================================"
echo "  Schedule Optimizer — Setup"
echo "========================================"
echo ""

# Kiểm tra Docker
if ! command -v docker &> /dev/null; then
    echo "[ERROR] Docker chưa được cài đặt. Vui lòng cài Docker trước."
    exit 1
fi

if ! command -v docker compose &> /dev/null && ! docker compose version &> /dev/null 2>&1; then
    echo "[ERROR] Docker Compose chưa được cài đặt. Vui lòng cài Docker Compose trước."
    exit 1
fi

echo "[1/3] Dừng container cũ (nếu có)..."
docker compose down 2>/dev/null || true

echo "[2/3] Build và khởi động container..."
docker compose up --build -d

echo "[3/3] Hoàn tất!"
echo ""
echo "  Web app:  http://localhost:8000"
echo "  API docs: http://localhost:8000/docs"
echo ""
echo "Để xem logs:  docker compose logs -f"
echo "Để dừng:      docker compose down"
