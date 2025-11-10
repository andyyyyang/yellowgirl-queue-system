import os
import time
import datetime
from pathlib import Path
from threading import Lock, Thread
from urllib import request

from flask import Flask, jsonify, send_from_directory, abort, request
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

app = Flask(__name__, static_folder=".", static_url_path="")

# 資料庫配置
database_url = os.environ.get('DATABASE_URL')
if database_url:
    # 使用PostgreSQL（Railway或其他環境）
    print(f"使用PostgreSQL資料庫: {database_url[:50]}...")
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    # 本地測試環境使用SQLite
    test_db_name = os.environ.get('TEST_DB_NAME', 'ticket_system_test.db')
    print(f"使用SQLite資料庫: {test_db_name}")
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{test_db_name}'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ─────── 資料庫模型 ─────────────────────────────
class TicketState(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.JSON, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

# ───────────────────────────────────────────────

# ─────── 資料庫操作函數 ─────────────────────────
def get_state_value(key, default=None):
    """獲取狀態值"""
    state_record = TicketState.query.filter_by(key=key).first()
    return state_record.value if state_record else default

def set_state_value(key, value):
    """設置狀態值"""
    state_record = TicketState.query.filter_by(key=key).first()
    if state_record:
        state_record.value = value
    else:
        state_record = TicketState(key=key, value=value)
        db.session.add(state_record)
    db.session.commit()
    return value

def init_database():
    """初始化資料庫"""
    with app.app_context():
        db.create_all()
        # 初始化預設值
        if not get_state_value('current'):
            set_state_value('current', None)
        if not get_state_value('waiting'):
            set_state_value('waiting', [])
        if not get_state_value('missed'):
            set_state_value('missed', [])
        if not get_state_value('next_no'):
            set_state_value('next_no', 1)
        if not get_state_value('last_reset_date'):
            set_state_value('last_reset_date', None)

# ───────────────────────────────────────────────

# === 靜態首頁 ===
@app.route("/")
def index():
    index_path = Path(app.static_folder) / "index.html"
    if index_path.exists():
        return send_from_directory(app.static_folder, "index.html")
    return "<h1>Ticket Server is running</h1>", 200, {"Content-Type": "text/html"}

# === 管理員控制介面 ===
@app.route("/control")
def control():
    control_html = """
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>叫號系統管理控制台</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", sans-serif;
            background: #1a1a1a;
            color: white;
            padding: 20px;
        }
        
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        
        .header h1 {
            font-size: 24px;
            margin-bottom: 10px;
        }
        
        .status-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .status-card {
            background: #2d2d2d;
            padding: 20px;
            border-radius: 12px;
            text-align: center;
        }
        
        .status-card h3 {
            font-size: 16px;
            margin-bottom: 15px;
            color: #ccc;
        }
        
        .current-number {
            font-size: 48px;
            font-weight: bold;
            color: #ffe066;
        }
        
        .next-number {
            font-size: 32px;
            font-weight: bold;
            color: #4CAF50;
        }
        
        .queue-info {
            background: #2d2d2d;
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 30px;
        }
        
        .queue-info h3 {
            margin-bottom: 15px;
            color: #ccc;
        }
        
        .queue-list {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 10px;
            margin-bottom: 15px;
        }
        
        .queue-item {
            background: #3d3d3d;
            padding: 10px;
            border-radius: 8px;
            text-align: center;
            font-size: 18px;
            font-weight: bold;
            min-height: 44px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .missed-list {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 10px;
        }
        
        .missed-item {
            background: #ff5722;
            padding: 10px;
            border-radius: 8px;
            text-align: center;
            font-size: 18px;
            font-weight: bold;
            min-height: 44px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .control-buttons {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            margin-bottom: 30px;
        }
        
        .control-btn {
            background: #3d3d3d;
            border: none;
            color: white;
            padding: 20px;
            border-radius: 12px;
            font-size: 18px;
            cursor: pointer;
            transition: all 0.3s;
            -webkit-tap-highlight-color: transparent;
            touch-action: manipulation;
            user-select: none;
        }
        
        .control-btn:hover, .control-btn:active {
            background: #4d4d4d;
            transform: translateY(-2px);
        }
        
        .control-btn.primary {
            background: #4CAF50;
        }
        
        .control-btn.primary:hover, .control-btn.primary:active {
            background: #45a049;
        }
        
        .control-btn.danger {
            background: #f44336;
        }
        
        .control-btn.danger:hover, .control-btn.danger:active {
            background: #da190b;
        }
        
        .control-btn.warning {
            background: #ff9800;
        }
        
        .control-btn.warning:hover, .control-btn.warning:active {
            background: #e68900;
        }
        
        .action-buttons {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
        }
        
        .action-btn {
            background: #2d2d2d;
            border: none;
            color: white;
            padding: 15px;
            border-radius: 8px;
            font-size: 16px;
            cursor: pointer;
            transition: all 0.3s;
            -webkit-tap-highlight-color: transparent;
            touch-action: manipulation;
            user-select: none;
        }
        
        .action-btn:hover, .action-btn:active {
            background: #3d3d3d;
        }
        
        .action-btn.danger {
            background: #ff5722;
        }
        
        .action-btn.danger:hover, .action-btn.danger:active {
            background: #e64a19;
        }
        
        .status-indicator {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 10px 15px;
            border-radius: 8px;
            font-size: 14px;
            opacity: 0;
            transition: opacity 0.3s;
            z-index: 1000;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }
        
        .status-indicator.success {
            background: #4CAF50;
            color: white;
        }
        
        .status-indicator.error {
            background: #f44336;
            color: white;
        }
        
        @media (max-width: 768px) {
            .status-indicator {
                top: 15px;
                right: 15px;
                left: 15px;
                text-align: center;
                font-size: 13px;
                padding: 12px 15px;
            }
        }
        
        @media (max-width: 480px) {
            .status-indicator {
                top: 10px;
                right: 10px;
                left: 10px;
                font-size: 12px;
                padding: 10px 15px;
            }
        }
        
        @media (max-width: 768px) {
            body {
                padding: 15px;
            }
            
            .header h1 {
                font-size: 20px;
            }
            
            .status-grid {
                grid-template-columns: 1fr;
                gap: 15px;
            }
            
            .status-card {
                padding: 15px;
            }
            
            .current-number {
                font-size: 36px;
            }
            
            .next-number {
                font-size: 28px;
            }
            
            .queue-info {
                padding: 15px;
            }
            
            .queue-list, .missed-list {
                grid-template-columns: repeat(auto-fit, minmax(80px, 1fr));
                gap: 8px;
            }
            
            .queue-item, .missed-item {
                padding: 8px;
                font-size: 16px;
            }
            
            .control-buttons {
                grid-template-columns: 1fr;
                gap: 12px;
            }
            
            .control-btn {
                padding: 18px;
                font-size: 16px;
                min-height: 60px;
            }
            
            .action-buttons {
                grid-template-columns: 1fr;
                gap: 12px;
            }
            
            .action-btn {
                padding: 18px;
                font-size: 16px;
                min-height: 50px;
            }
        }
        
        @media (max-width: 480px) {
            body {
                padding: 10px;
            }
            
            .header {
                margin-bottom: 20px;
            }
            
            .header h1 {
                font-size: 18px;
            }
            
            .status-grid {
                gap: 12px;
                margin-bottom: 20px;
            }
            
            .status-card {
                padding: 12px;
            }
            
            .current-number {
                font-size: 32px;
            }
            
            .next-number {
                font-size: 24px;
            }
            
            .queue-info {
                padding: 12px;
                margin-bottom: 20px;
            }
            
            .queue-list, .missed-list {
                grid-template-columns: repeat(auto-fit, minmax(70px, 1fr));
                gap: 6px;
            }
            
            .queue-item, .missed-item {
                padding: 6px;
                font-size: 14px;
            }
            
            .control-buttons {
                gap: 10px;
                margin-bottom: 20px;
            }
            
            .control-btn {
                padding: 16px;
                font-size: 15px;
                min-height: 55px;
                border-radius: 10px;
            }
            
            .action-buttons {
                gap: 10px;
            }
            
            .action-btn {
                padding: 16px;
                font-size: 15px;
                min-height: 48px;
                border-radius: 8px;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎫 叫號系統管理控制台</h1>
        <p>即時監控和控制叫號狀態</p>
    </div>
    
    <div class="status-grid">
        <div class="status-card">
            <h3>目前叫號</h3>
            <div class="current-number" id="currentNumber">-</div>
        </div>
        <div class="status-card">
            <h3>下一個號碼</h3>
            <div class="next-number" id="nextNumber">-</div>
        </div>
    </div>
    
    <div class="queue-info">
        <h3>等待佇列 (<span id="waitingCount">0</span>)</h3>
        <div class="queue-list" id="waitingList">
            <div class="queue-item">無等待號碼</div>
        </div>
        
        <h3>錯過佇列 (<span id="missedCount">0</span>)</h3>
        <div class="missed-list" id="missedList">
            <div class="queue-item">無錯過號碼</div>
        </div>
    </div>
    
    <div class="control-buttons">
        <button class="control-btn primary" onclick="takeNumber()">
            ➕ 取號
        </button>
        <button class="control-btn warning" onclick="nextNumber()">
            ➡️ 下一個
        </button>
        <button class="control-btn danger" onclick="markMissed()">
            ⏰ 過號
        </button>
    </div>
    
    <div class="action-buttons">
        <button class="action-btn" onclick="goPrevious()">
            ↩️ 返回前一號
        </button>
        <button class="action-btn danger" onclick="manualReset()">
            🔄 手動歸零
        </button>
    </div>
    
    <div class="status-indicator" id="statusIndicator"></div>
    
    <script>
        // 更新狀態顯示
        function updateStatus() {
            fetch('/status')
                .then(response => response.json())
                .then(data => {
                    // 更新目前叫號
                    document.getElementById('currentNumber').textContent = data.current || '-';
                    
                    // 更新下一個號碼
                    document.getElementById('nextNumber').textContent = data.next_no;
                    
                    // 更新等待佇列
                    const waitingList = document.getElementById('waitingList');
                    const waitingCount = document.getElementById('waitingCount');
                    
                    if (data.waiting && data.waiting.length > 0) {
                        waitingCount.textContent = data.waiting.length;
                        waitingList.innerHTML = data.waiting.map(num => 
                            `<div class="queue-item">${num}</div>`
                        ).join('');
                    } else {
                        waitingCount.textContent = '0';
                        waitingList.innerHTML = '<div class="queue-item">無等待號碼</div>';
                    }
                    
                    // 更新錯過佇列
                    const missedList = document.getElementById('missedList');
                    const missedCount = document.getElementById('missedCount');
                    
                    if (data.missed && data.missed.length > 0) {
                        missedCount.textContent = data.missed.length;
                        missedList.innerHTML = data.missed.map(num => 
                            `<div class="missed-item">${num}</div>`
                        ).join('');
                    } else {
                        missedCount.textContent = '0';
                        missedList.innerHTML = '<div class="queue-item">無錯過號碼</div>';
                    }
                })
                .catch(error => {
                    console.error('更新狀態失敗:', error);
                });
        }
        
        // 顯示狀態訊息
        function showStatus(message, type = 'success') {
            const indicator = document.getElementById('statusIndicator');
            indicator.textContent = message;
            indicator.className = `status-indicator ${type}`;
            indicator.style.opacity = '1';
            
            setTimeout(() => {
                indicator.style.opacity = '0';
            }, 3000);
        }
        
        // 取號
        function takeNumber() {
            fetch('/take', { method: 'POST' })
                .then(response => {
                    if (response.ok) {
                        showStatus('✅ 成功取號');
                        updateStatus();
                    } else {
                        showStatus('❌ 取號失敗', 'error');
                    }
                })
                .catch(error => {
                    console.error('取號失敗:', error);
                    showStatus('❌ 取號失敗', 'error');
                });
        }
        
        // 下一個號碼
        function nextNumber() {
            fetch('/next', { method: 'POST' })
                .then(response => {
                    if (response.ok) {
                        showStatus('✅ 已叫下一個號碼');
                        updateStatus();
                    } else {
                        showStatus('❌ 叫號失敗', 'error');
                    }
                })
                .catch(error => {
                    console.error('叫號失敗:', error);
                    showStatus('❌ 叫號失敗', 'error');
                });
        }
        
        // 標記過號
        function markMissed() {
            fetch('/miss', { method: 'POST' })
                .then(response => {
                    if (response.ok) {
                        showStatus('✅ 已標記過號');
                        updateStatus();
                    } else {
                        showStatus('❌ 標記過號失敗', 'error');
                    }
                })
                .catch(error => {
                    console.error('標記過號失敗:', error);
                    showStatus('❌ 標記過號失敗', 'error');
                });
        }
        
        // 返回前一號
        function goPrevious() {
            fetch('/previous', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'ok') {
                        showStatus('✅ ' + data.message);
                        updateStatus();
                    } else {
                        showStatus('❌ ' + data.error, 'error');
                    }
                })
                .catch(error => {
                    console.error('返回前一號失敗:', error);
                    showStatus('❌ 返回前一號失敗', 'error');
                });
        }
        
        // 手動歸零
        function manualReset() {
            if (confirm('確定要手動歸零嗎？這將清空所有狀態！')) {
                fetch('/reset', { method: 'POST' })
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === 'ok') {
                            showStatus('✅ ' + data.message);
                            updateStatus();
                        } else {
                            showStatus('❌ 歸零失敗', 'error');
                        }
                    })
                    .catch(error => {
                        console.error('歸零失敗:', error);
                        showStatus('❌ 歸零失敗', 'error');
                    });
            }
        }
        
        // 頁面載入時更新狀態
        updateStatus();
        
        // 每 3 秒自動更新狀態
        setInterval(updateStatus, 3000);
    </script>
</body>
</html>
"""
    return control_html

# === 健康檢查 ===
@app.route("/healthz")
def healthz():
    return "ok"

# === API ===
@app.route("/status")
def status():
    return jsonify({
        "current": get_state_value('current'),
        "waiting": get_state_value('waiting', []),
        "missed": get_state_value('missed', []),
        "next_no": get_state_value('next_no', 1)
    })

@app.route("/take", methods=["POST"])
def take():
    waiting = get_state_value('waiting', [])
    next_no = get_state_value('next_no', 1)
    waiting.append(next_no)
    set_state_value('waiting', waiting)
    set_state_value('next_no', next_no + 1)
    return "", 204

@app.route("/next", methods=["POST"])
def next_call():
    waiting = get_state_value('waiting', [])
    if waiting:
        current = waiting.pop(0)
        set_state_value('waiting', waiting)
        set_state_value('current', current)
    else:
        set_state_value('current', None)
    return "", 204

@app.route("/miss", methods=["POST"])
def mark_missed():
    current = get_state_value('current')
    if current is not None:
        missed = get_state_value('missed', [])
        waiting = get_state_value('waiting', [])
        missed.append(current)
        set_state_value('missed', missed)
        set_state_value('current', None)
        if waiting:
            new_current = waiting.pop(0)
            set_state_value('waiting', waiting)
            set_state_value('current', new_current)
    return "", 204

@app.route("/missed/<int:number>", methods=["DELETE"])
def delete_missed(number):
    missed = get_state_value('missed', [])
    try:
        missed.remove(number)
        set_state_value('missed', missed)
        return "", 204
    except ValueError:
        abort(404, description="not found")

@app.route("/reset", methods=["POST"])
def manual_reset():
    """手動歸零 API"""
    set_state_value('current', None)
    set_state_value('missed', [])
    set_state_value('waiting', [])
    set_state_value('next_no', 1)
    print("🔄 手動歸零執行")
    return jsonify({"status": "ok", "message": "已手動歸零"}), 200

@app.route("/previous", methods=["POST"])
def go_previous():
    """返回前一號 API"""
    current = get_state_value('current')
    if current is not None:
        # 保存當前號碼
        previous_number = current
        # 將當前號碼放回等待佇列前端
        waiting = get_state_value('waiting', [])
        waiting.insert(0, current)
        set_state_value('waiting', waiting)
        # 從錯過佇列中移除（如果存在）
        missed = get_state_value('missed', [])
        if current in missed:
            missed.remove(current)
            set_state_value('missed', missed)
        set_state_value('current', None)
        print(f"⬅️ 返回前一號：{previous_number}")
        return jsonify({"status": "ok", "message": f"已返回前一號 {previous_number}"}), 200
    else:
        return jsonify({"error": "目前沒有正在叫號"}), 400




# === 排程：每天 6 點 or next_no >= 1000 歸零（保留 waiting） ===
def reset_scheduler():
    with app.app_context():
        while True:
            now = datetime.datetime.now()
            last_reset_date = get_state_value('last_reset_date')
            next_no = get_state_value('next_no', 1)

            # 每日 6 點檢查（只做一次）
            if now.hour == 6 and now.minute == 0 and (last_reset_date != str(now.date())):
                print("⏰ 每日 6 點歸零")
                set_state_value('current', None)
                set_state_value('missed', [])
                set_state_value('next_no', 1)
                set_state_value('last_reset_date', str(now.date()))

            # 若 next_no 達 1000，自動歸零（保留 waiting）
            if next_no >= 1000:
                print("🔁 自動歸零：編號達 1000")
                set_state_value('current', None)
                set_state_value('next_no', 1)

            time.sleep(10)

# === Main ===
if __name__ == "__main__":
    print("🚀 啟動叫號系統應用...")
    print(f"📍 運行環境: {os.environ.get('RAILWAY_ENVIRONMENT', '本地開發')}")
    print(f"🌐 端口: {os.environ.get('PORT', 8080)}")

    try:
        # 初始化資料庫
        print("📊 初始化資料庫...")
        init_database()
        print("✅ 資料庫初始化完成")

        # 啟動排程執行緒
        print("⏰ 啟動排程執行緒...")
        Thread(target=reset_scheduler, daemon=True).start()
        print("✅ 排程執行緒已啟動")

        port = int(os.environ.get("PORT", 8080))
        print(f"🌐 啟動web服務器，端口: {port}")
        app.run(host="0.0.0.0", port=port)

    except Exception as e:
        print(f"❌ 應用啟動失敗: {e}")
        import traceback
        traceback.print_exc()
        raise
