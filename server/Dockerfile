# 使用 Python 3.11 官方映像
FROM python:3.11-slim

# 設置工作目錄
WORKDIR /app

# 複製 requirements.txt
COPY requirements.txt .

# 安裝依賴
RUN pip install --no-cache-dir -r requirements.txt

# 複製所有文件
COPY . .

# 暴露端口
EXPOSE 8080

# 設置環境變數
ENV PORT=8080

# 啟動應用程式
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:app"]
