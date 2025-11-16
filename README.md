# 黃毛丫頭叫號系統

一個簡單的叫號系統，使用Flask + PostgreSQL構建。

## 部署到 Railway

### 1. 創建 Railway 帳戶
前往 [Railway.app](https://railway.app) 註冊帳戶。

### 2. 安裝 Railway CLI
```bash
npm install -g @railway/cli
railway login
```

### 3. 部署應用
```bash
railway init
railway up
```

Railway 會自動：
- 創建 PostgreSQL 資料庫
- 設置環境變數 `DATABASE_URL`
- 部署應用到雲端

### 環境變數說明

Railway 會自動提供以下環境變數：
- `DATABASE_URL`: PostgreSQL 資料庫連接字符串
- `PORT`: 應用運行端口

### 本地開發

1. 安裝依賴：
```bash
pip install -r requirements.txt
```

2. 設置本地 PostgreSQL 資料庫，或使用 Railway 的資料庫 URL

3. 運行應用：
```bash
python main.py
```

## API 端點

- `GET /status` - 獲取當前狀態
- `POST /take` - 取號
- `POST /next` - 叫下一個號碼
- `POST /miss` - 標記過號
- `POST /reset` - 手動歸零
- `POST /previous` - 返回前一號

## 前端

前端文件位於 `public/` 目錄中，Railway 會自動提供靜態文件服務。



