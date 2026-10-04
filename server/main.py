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

class Prize(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), default="")
    icon = db.Column(db.String(50), default="🎁")  # emoji 或圖標
    daily_limit = db.Column(db.Integer, default=0)  # 每天最多發放數量，0表示無限制
    weight = db.Column(db.Float, default=1.0)  # 抽獎權重（機率），預設為1.0
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
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
        if not get_state_value('marked'):
            set_state_value('marked', [])

        # 檢查並處理獎品表的遷移問題
        try:
            # 嘗試查詢獎品表，檢查表結構是否正確
            Prize.query.limit(1).all()
            
            # 檢查是否有 weight 欄位，如果沒有則添加
            try:
                # 嘗試查詢 weight 欄位
                db.session.execute(db.text("SELECT weight FROM prize LIMIT 1"))
            except Exception:
                # 如果沒有 weight 欄位，添加它
                print("⚠️ 檢測到缺少 weight 欄位，正在添加...")
                try:
                    db.session.execute(db.text("ALTER TABLE prize ADD COLUMN weight FLOAT DEFAULT 1.0"))
                    db.session.commit()
                    print("✅ 已添加 weight 欄位")
                    
                    # 為現有獎品設置預設權重
                    prizes = Prize.query.all()
                    for prize in prizes:
                        if not hasattr(prize, 'weight') or prize.weight is None:
                            prize.weight = 1.0
                    db.session.commit()
                    print("✅ 已為現有獎品設置預設權重")
                except Exception as alter_error:
                    print(f"⚠️ 添加 weight 欄位失敗: {alter_error}")
                    db.session.rollback()
                    
        except Exception as e:
            # 如果表結構不匹配（缺少欄位），則刪除舊表並重新創建
            print(f"⚠️ 檢測到獎品表結構不匹配: {str(e)}")
            print("正在重建獎品表...")
            try:
                # 刪除舊的 prize 表
                Prize.__table__.drop(db.engine, checkfirst=True)
                print("✅ 已刪除舊的獎品表")
            except Exception as drop_error:
                print(f"⚠️ 刪除舊表時發生錯誤: {drop_error}")
            
            # 重新創建表
            try:
                Prize.__table__.create(db.engine, checkfirst=True)
                print("✅ 已重新創建獎品表")
            except Exception as create_error:
                print(f"⚠️ 創建表時發生錯誤: {create_error}")
                # 如果創建失敗，嘗試使用 create_all
                db.create_all()

        # 初始化預設獎品（如果沒有獎品資料）
        try:
            prize_count = Prize.query.count()
        except Exception:
            prize_count = 0
            
        if prize_count == 0:
            default_prizes = [
                {"name": "特大獎", "description": "超級幸運獎品", "icon": "🎊", "daily_limit": 1, "weight": 0.5},
                {"name": "大獎", "description": "非常棒的獎品", "icon": "🎉", "daily_limit": 2, "weight": 1.0},
                {"name": "中獎", "description": "不錯的獎品", "icon": "🎁", "daily_limit": 5, "weight": 2.0},
                {"name": "小獎", "description": "小確幸獎品", "icon": "✨", "daily_limit": 10, "weight": 3.0},
                {"name": "參加獎", "description": "感謝參與", "icon": "🎈", "daily_limit": 0, "weight": 5.0},
                {"name": "幸運獎", "description": "運氣不錯喔", "icon": "🌟", "daily_limit": 0, "weight": 4.0},
                {"name": "安慰獎", "description": "下次一定會更好", "icon": "💪", "daily_limit": 0, "weight": 6.0},
                {"name": "再接再厲", "description": "繼續努力", "icon": "🔥", "daily_limit": 0, "weight": 6.0},
                {"name": "下次一定", "description": "機會總是留給準備好的人", "icon": "🎯", "daily_limit": 0, "weight": 6.0},
                {"name": "祝你好運", "description": "祝你下次好運", "icon": "🍀", "daily_limit": 0, "weight": 6.0},
                {"name": "銘謝惠顧", "description": "感謝光臨", "icon": "🙏", "daily_limit": 0, "weight": 8.0},
                {"name": "銘謝惠顧", "description": "歡迎下次再來", "icon": "🙏", "daily_limit": 0, "weight": 8.0}
            ]

            for prize_data in default_prizes:
                prize = Prize(
                    name=prize_data["name"],
                    description=prize_data["description"],
                    icon=prize_data["icon"],
                    daily_limit=prize_data["daily_limit"],
                    weight=prize_data.get("weight", 1.0),
                    is_active=True
                )
                db.session.add(prize)
            db.session.commit()
            print("✅ 已初始化預設獎品資料")

        # 初始化每日發放記錄
        today = datetime.date.today().isoformat()
        if not get_state_value(f'daily_prizes_{today}'):
            set_state_value(f'daily_prizes_{today}', {})

def get_daily_prize_count(prize_id, date_str=None):
    """獲取指定日期的獎品發放數量"""
    if date_str is None:
        date_str = datetime.date.today().isoformat()
    daily_record = get_state_value(f'daily_prizes_{date_str}', {})
    return daily_record.get(str(prize_id), 0)

def increment_daily_prize_count(prize_id):
    """增加指定獎品的每日發放數量"""
    today = datetime.date.today().isoformat()
    daily_record = get_state_value(f'daily_prizes_{today}', {})
    prize_id_str = str(prize_id)

    if prize_id_str not in daily_record:
        daily_record[prize_id_str] = 0
    daily_record[prize_id_str] += 1

    set_state_value(f'daily_prizes_{today}', daily_record)
    return daily_record[prize_id_str]

def can_award_prize(prize):
    """檢查是否可以發放指定獎品"""
    if not prize.is_active:
        return False

    if prize.daily_limit > 0:
        current_count = get_daily_prize_count(prize.id)
        return current_count < prize.daily_limit

    return True

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
        "marked": get_state_value('marked', []),
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
        # 先檢查之前的 current 是否在標記清單中，如果在就取消標記
        previous_current = get_state_value('current')
        if previous_current is not None:
            marked = get_state_value('marked', [])
            if previous_current in marked:
                marked.remove(previous_current)
                set_state_value('marked', marked)
                print(f"✅ 號碼 {previous_current} 已到達，自動取消標記")

        # 設置新的 current
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

        # 如果該號碼也在標記清單中，同時移除標記
        marked = get_state_value('marked', [])
        if number in marked:
            marked.remove(number)
            set_state_value('marked', marked)
            print(f"❌ 從過號清單移除號碼 {number}，同時取消其標記")

        return "", 204
    except ValueError:
        abort(404, description="not found")

@app.route("/reset", methods=["POST"])
def manual_reset():
    """手動歸零 API"""
    set_state_value('current', None)
    set_state_value('missed', [])
    set_state_value('waiting', [])
    set_state_value('marked', [])
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

@app.route("/mark/<int:number>", methods=["POST"])
def mark_number(number):
    """標記號碼 API"""
    marked = get_state_value('marked', [])
    if number not in marked:
        marked.append(number)
        set_state_value('marked', marked)
        print(f"⭐ 標記號碼：{number}")
        return "", 204
    else:
        return "", 204  # 已經標記，不做改變

@app.route("/unmark/<int:number>", methods=["DELETE"])
def unmark_number(number):
    """取消標記號碼 API"""
    marked = get_state_value('marked', [])
    try:
        marked.remove(number)
        set_state_value('marked', marked)
        print(f"❌ 取消標記號碼：{number}")
        return "", 204
    except ValueError:
        abort(404, description="not found")




# === 排程：每天 6 點 or next_no >= 1000 歸零（保留 waiting） ===
def reset_scheduler():
    # 台灣時區 (UTC+8)
    taiwan_tz = datetime.timezone(datetime.timedelta(hours=8))
    
    with app.app_context():
        while True:
            # 使用台灣時區獲取當前時間
            now = datetime.datetime.now(taiwan_tz)
            last_reset_date = get_state_value('last_reset_date')
            next_no = get_state_value('next_no', 1)

            # 每日 6 點檢查（只做一次）- 台灣時間早上 6 點
            if now.hour == 6 and now.minute == 0 and (last_reset_date != str(now.date())):
                print(f"⏰ 每日 6 點歸零（台灣時間: {now.strftime('%Y-%m-%d %H:%M:%S')}）")
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

# === 抽獎系統 API ===
@app.route("/prizes")
def get_prizes():
    """獲取獎品列表"""
    prizes = Prize.query.filter_by(is_active=True).order_by(Prize.id).all()
    
    # 計算總權重用於計算機率
    total_weight = sum(p.weight if p.weight and p.weight > 0 else 1.0 for p in prizes)
    
    prize_list = []
    for prize in prizes:
        today_count = get_daily_prize_count(prize.id)
        weight = prize.weight if prize.weight and prize.weight > 0 else 1.0
        probability = (weight / total_weight * 100) if total_weight > 0 else (100.0 / len(prizes) if prizes else 0)
        
        prize_list.append({
            "id": prize.id,
            "name": prize.name,
            "description": prize.description or "",
            "icon": prize.icon,
            "daily_limit": prize.daily_limit,
            "weight": weight,
            "probability": round(probability, 2),  # 機率百分比
            "today_count": today_count,
            "remaining": prize.daily_limit - today_count if prize.daily_limit > 0 else -1  # -1 表示無限制
        })
    return jsonify(prize_list)

@app.route("/draw", methods=["POST"])
def draw_prize():
    """抽獎邏輯"""
    import random

    # 獲取用戶 IP 地址（用於區分不同用戶）
    user_ip = request.remote_addr
    # 如果使用代理，嘗試從 X-Forwarded-For 獲取真實 IP
    if request.headers.get('X-Forwarded-For'):
        user_ip = request.headers.get('X-Forwarded-For').split(',')[0].strip()
    
    # 檢查8小時內是否已經抽過獎（基於用戶 IP）
    now = datetime.datetime.utcnow()
    user_draw_key = f'draw_timestamp_{user_ip}'
    last_draw_timestamp = get_state_value(user_draw_key)
    
    # 8小時 = 8 * 60 * 60 = 28800 秒
    cache_hours = 8
    cache_seconds = cache_hours * 60 * 60
    
    if last_draw_timestamp:
        try:
            # 處理不同格式的時間戳記
            if isinstance(last_draw_timestamp, str):
                # 嘗試解析 ISO 格式字符串
                try:
                    last_draw_time = datetime.datetime.fromisoformat(last_draw_timestamp.replace('Z', '+00:00'))
                    if last_draw_time.tzinfo:
                        last_draw_time = last_draw_time.replace(tzinfo=None)
                except:
                    # 如果不是 ISO 格式，嘗試解析為數字時間戳記（秒）
                    try:
                        timestamp_float = float(last_draw_timestamp)
                        # 判斷是秒還是毫秒（大於 1e10 的是秒，否則可能是毫秒）
                        if timestamp_float > 1e10:
                            last_draw_time = datetime.datetime.fromtimestamp(timestamp_float)
                        else:
                            last_draw_time = datetime.datetime.fromtimestamp(timestamp_float / 1000)
                    except:
                        raise ValueError("無法解析時間戳記格式")
            else:
                # 如果是數字，判斷是秒還是毫秒
                if last_draw_timestamp > 1e10:
                    last_draw_time = datetime.datetime.fromtimestamp(last_draw_timestamp)
                else:
                    last_draw_time = datetime.datetime.fromtimestamp(last_draw_timestamp / 1000)
            
            # 計算時間差（秒）
            time_diff = (now - last_draw_time).total_seconds()
            
            if time_diff < cache_seconds:
                # 還未超過8小時
                remaining_hours = (cache_seconds - time_diff) / 3600
                return jsonify({
                    "id": -1,
                    "name": f"距離上次抽獎還需等待 {remaining_hours:.1f} 小時"
                })
        except Exception as e:
            print(f"⚠️ 解析抽獎時間戳記失敗: {e}")
            # 如果解析失敗，清除舊記錄，允許抽獎
            set_state_value(user_draw_key, None)

    # 從資料庫獲取可用的獎品（只選擇可以發放的獎品）
    all_prizes = Prize.query.filter_by(is_active=True).all()
    available_prizes = [p for p in all_prizes if can_award_prize(p)]

    if not available_prizes:
        return jsonify({
            "id": -1,
            "name": "目前沒有可用的獎品，請稍後再試"
        })

    # 使用加權隨機選擇獎品
    # 計算總權重
    total_weight = sum(p.weight if p.weight and p.weight > 0 else 1.0 for p in available_prizes)
    
    if total_weight <= 0:
        # 如果總權重為0或負數，使用均等機率
        selected_prize = random.choice(available_prizes)
    else:
        # 生成0到總權重之間的隨機數
        random_value = random.uniform(0, total_weight)
        current_weight = 0
        
        # 根據權重選擇獎品
        for prize in available_prizes:
            weight = prize.weight if prize.weight and prize.weight > 0 else 1.0
            current_weight += weight
            if random_value <= current_weight:
                selected_prize = prize
                break
        else:
            # 如果沒有選中（理論上不應該發生），選擇最後一個
            selected_prize = available_prizes[-1]

    # 增加每日發放計數
    increment_daily_prize_count(selected_prize.id)

    # 記錄該用戶的抽獎時間戳記（UTC時間）
    set_state_value(user_draw_key, now.isoformat())
    
    # 記錄該用戶的獎品（可選，用於顯示上次抽獎結果）
    user_prize_key = f'last_prize_{user_ip}'
    prize_data = {
        "id": selected_prize.id,
        "name": selected_prize.name,
        "icon": selected_prize.icon
    }
    set_state_value(user_prize_key, prize_data)

    print(f"🎉 用戶 {user_ip} 抽獎結果: {selected_prize.name} (ID: {selected_prize.id})")

    return jsonify(prize_data)

# === 獎品管理 API ===
@app.route("/api/prizes", methods=["GET"])
def api_get_prizes():
    """獲取所有獎品（管理用）"""
    prizes = Prize.query.order_by(Prize.id).all()
    today = datetime.date.today().isoformat()
    # 計算總權重用於計算機率
    total_weight = sum(p.weight if p.weight and p.weight > 0 else 1.0 for p in prizes)
    
    prize_list = []
    for prize in prizes:
        today_count = get_daily_prize_count(prize.id)
        weight = prize.weight if prize.weight and prize.weight > 0 else 1.0
        probability = (weight / total_weight * 100) if total_weight > 0 else (100.0 / len(prizes) if prizes else 0)
        
        prize_list.append({
            "id": prize.id,
            "name": prize.name,
            "description": prize.description,
            "icon": prize.icon,
            "daily_limit": prize.daily_limit,
            "weight": weight,
            "probability": round(probability, 2),  # 機率百分比
            "is_active": prize.is_active,
            "today_count": today_count,
            "remaining": prize.daily_limit - today_count if prize.daily_limit > 0 else -1,
            "created_at": prize.created_at.isoformat() if prize.created_at else None,
            "updated_at": prize.updated_at.isoformat() if prize.updated_at else None
        })
    return jsonify(prize_list)

@app.route("/api/prizes", methods=["POST"])
def api_create_prize():
    """新增獎品"""
    data = request.get_json()
    
    if not data or not data.get('name'):
        return jsonify({"error": "獎品名稱是必填的"}), 400

    prize = Prize(
        name=data.get('name'),
        description=data.get('description', ''),
        icon=data.get('icon', '🎁'),
        daily_limit=data.get('daily_limit', 0),
        weight=data.get('weight', 1.0),
        is_active=data.get('is_active', True)
    )
    
    try:
        db.session.add(prize)
        db.session.commit()
        return jsonify({
            "id": prize.id,
            "name": prize.name,
            "description": prize.description,
            "icon": prize.icon,
            "daily_limit": prize.daily_limit,
            "weight": prize.weight,
            "is_active": prize.is_active
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/api/prizes/<int:prize_id>", methods=["PUT"])
def api_update_prize(prize_id):
    """更新獎品"""
    prize = Prize.query.get_or_404(prize_id)
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "請提供更新資料"}), 400

    if 'name' in data:
        prize.name = data['name']
    if 'description' in data:
        prize.description = data.get('description', '')
    if 'icon' in data:
        prize.icon = data['icon']
    if 'daily_limit' in data:
        prize.daily_limit = data['daily_limit']
    if 'weight' in data:
        prize.weight = float(data['weight']) if data['weight'] is not None else 1.0
    if 'is_active' in data:
        prize.is_active = data['is_active']
    
    prize.updated_at = datetime.datetime.utcnow()
    
    try:
        db.session.commit()
        today_count = get_daily_prize_count(prize.id)
        
        # 計算機率百分比
        all_prizes = Prize.query.filter_by(is_active=True).all()
        total_weight = sum(p.weight if p.weight and p.weight > 0 else 1.0 for p in all_prizes)
        weight = prize.weight if prize.weight and prize.weight > 0 else 1.0
        probability = (weight / total_weight * 100) if total_weight > 0 else 0
        
        return jsonify({
            "id": prize.id,
            "name": prize.name,
            "description": prize.description,
            "icon": prize.icon,
            "daily_limit": prize.daily_limit,
            "weight": prize.weight,
            "probability": round(probability, 2),
            "is_active": prize.is_active,
            "today_count": today_count,
            "remaining": prize.daily_limit - today_count if prize.daily_limit > 0 else -1
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/api/prizes/<int:prize_id>", methods=["DELETE"])
def api_delete_prize(prize_id):
    """刪除獎品"""
    prize = Prize.query.get_or_404(prize_id)
    
    try:
        db.session.delete(prize)
        db.session.commit()
        return jsonify({"message": "獎品已刪除"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/api/prizes/reset-daily", methods=["POST"])
def api_reset_daily_count():
    """重置今日獎品發放計數（測試用）"""
    today = datetime.date.today().isoformat()
    set_state_value(f'daily_prizes_{today}', {})
    return jsonify({"message": f"已重置 {today} 的獎品發放計數"}), 200

@app.route("/api/prizes/reset-draw-records", methods=["POST"])
def api_reset_draw_records():
    """清除所有用戶的抽獎紀錄（8小時快取）"""
    now = datetime.datetime.utcnow()
    
    # 清除抽獎時間戳記（這樣後端允許重新抽獎）
    set_state_value('last_draw_timestamp', None)
    
    # 清除最後抽獎記錄
    set_state_value('last_prize', None)
    
    # 清除今日獎品發放計數（重置所有獎品的今日發放數量）
    today = datetime.date.today().isoformat()
    set_state_value(f'daily_prizes_{today}', {})
    
    return jsonify({
        "message": f"已清除所有抽獎紀錄和發放計數。\\n用戶可以在8小時後重新抽獎。\\n注意：用戶瀏覽器的 localStorage 記錄需要用戶重新整理頁面後才會清除。"
    }), 200

@app.route("/api/wheel-mode", methods=["GET"])
def api_get_wheel_mode():
    """獲取轉盤模式開關狀態"""
    wheel_mode_enabled = get_state_value('wheel_mode_enabled', True)  # 預設為開啟
    return jsonify({"enabled": wheel_mode_enabled}), 200

@app.route("/api/wheel-mode", methods=["POST"])
def api_set_wheel_mode():
    """設置轉盤模式開關狀態"""
    data = request.get_json()
    if data is None or 'enabled' not in data:
        return jsonify({"error": "請提供 enabled 參數"}), 400
    
    enabled = bool(data['enabled'])
    set_state_value('wheel_mode_enabled', enabled)
    print(f"🎡 轉盤模式已{'開啟' if enabled else '關閉'}")
    return jsonify({"enabled": enabled, "message": f"轉盤模式已{'開啟' if enabled else '關閉'}"}), 200

# === 獎品管理介面 ===
@app.route("/prize-admin")
def prize_admin():
    """獎品管理後台介面"""
    admin_html = """
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>獎品管理系統</title>
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
        
        .actions {
            display: flex;
            gap: 15px;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }
        
        .btn {
            background: #4CAF50;
            border: none;
            color: white;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 16px;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .btn:hover {
            background: #45a049;
            transform: translateY(-2px);
        }
        
        .btn.secondary {
            background: #2196F3;
        }
        
        .btn.secondary:hover {
            background: #0b7dda;
        }
        
        .btn.danger {
            background: #f44336;
        }
        
        .btn.danger:hover {
            background: #da190b;
        }
        
        .prizes-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .prize-card {
            background: #2d2d2d;
            padding: 20px;
            border-radius: 12px;
            border: 2px solid #3d3d3d;
        }
        
        .prize-card.inactive {
            opacity: 0.6;
            border-color: #555;
        }
        
        .prize-header {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 15px;
        }
        
        .prize-icon {
            font-size: 2rem;
        }
        
        .prize-name {
            font-size: 1.2rem;
            font-weight: bold;
            flex: 1;
        }
        
        .prize-status {
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85rem;
            background: #4CAF50;
        }
        
        .prize-status.inactive {
            background: #666;
        }
        
        .prize-info {
            margin-bottom: 15px;
        }
        
        .prize-info-item {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-size: 0.9rem;
            color: #ccc;
        }
        
        .prize-info-label {
            color: #999;
        }
        
        .prize-actions {
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }
        
        .btn-small {
            padding: 8px 16px;
            font-size: 0.9rem;
            border-radius: 6px;
        }
        
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.7);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }
        
        .modal.active {
            display: flex;
        }
        
        .modal-content {
            background: #2d2d2d;
            padding: 30px;
            border-radius: 12px;
            width: 90%;
            max-width: 500px;
            max-height: 90vh;
            overflow-y: auto;
        }
        
        .modal-header {
            margin-bottom: 20px;
        }
        
        .modal-header h2 {
            font-size: 1.5rem;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 8px;
            color: #ccc;
            font-size: 0.9rem;
        }
        
        .form-group input,
        .form-group textarea {
            width: 100%;
            padding: 10px;
            border: 1px solid #444;
            border-radius: 6px;
            background: #1a1a1a;
            color: white;
            font-size: 1rem;
        }
        
        .form-group textarea {
            resize: vertical;
            min-height: 80px;
        }
        
        .form-actions {
            display: flex;
            gap: 10px;
            justify-content: flex-end;
            margin-top: 20px;
        }
        
        .status-indicator {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            border-radius: 8px;
            font-size: 14px;
            opacity: 0;
            transition: opacity 0.3s;
            z-index: 2000;
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
        
        .status-indicator.show {
            opacity: 1;
        }
        
        .toggle-switch {
            position: relative;
            display: inline-block;
            width: 60px;
            height: 34px;
        }
        
        .toggle-switch input {
            opacity: 0;
            width: 0;
            height: 0;
        }
        
        .toggle-slider {
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: #666;
            transition: 0.3s;
            border-radius: 34px;
        }
        
        .toggle-slider:before {
            position: absolute;
            content: "";
            height: 26px;
            width: 26px;
            left: 4px;
            bottom: 4px;
            background-color: white;
            transition: 0.3s;
            border-radius: 50%;
        }
        
        .toggle-switch input:checked + .toggle-slider {
            background-color: #4CAF50;
        }
        
        .toggle-switch input:checked + .toggle-slider:before {
            transform: translateX(26px);
        }
        
        .toggle-switch input:focus + .toggle-slider {
            box-shadow: 0 0 1px #4CAF50;
        }
        
        @media (max-width: 768px) {
            .prizes-grid {
                grid-template-columns: 1fr;
            }
            
            .actions {
                flex-direction: column;
            }
            
            .btn {
                width: 100%;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎁 獎品管理系統</h1>
        <p>管理抽獎獎品和每日發放限制</p>
    </div>
    
    <div class="actions">
        <button class="btn" onclick="openAddModal()">➕ 新增獎品</button>
        <button class="btn secondary" onclick="loadPrizes()">🔄 重新載入</button>
        <button class="btn danger" onclick="resetDailyCount()">🔄 重置今日計數</button>
        <button class="btn danger" onclick="resetDrawRecords()">🗑️ 清除抽獎紀錄（8小時快取）</button>
    </div>
    
    <div class="settings-card" style="background: #2d2d2d; padding: 20px; border-radius: 12px; margin-bottom: 30px;">
        <h3 style="margin-bottom: 15px; color: #ccc;">⚙️ 系統設定</h3>
        <div class="setting-item" style="display: flex; justify-content: space-between; align-items: center; padding: 15px; background: #3d3d3d; border-radius: 8px;">
            <div>
                <div style="font-weight: bold; margin-bottom: 5px;">🎡 轉盤模式</div>
                <div style="font-size: 0.85rem; color: #999;">控制是否啟用轉盤抽獎功能</div>
            </div>
            <label class="toggle-switch">
                <input type="checkbox" id="wheelModeToggle" onchange="toggleWheelMode()">
                <span class="toggle-slider"></span>
            </label>
        </div>
    </div>
    
    <div class="prizes-grid" id="prizesGrid">
        <div style="text-align: center; color: #999;">載入中...</div>
    </div>
    
    <!-- 新增/編輯獎品 Modal -->
    <div class="modal" id="prizeModal">
        <div class="modal-content">
            <div class="modal-header">
                <h2 id="modalTitle">新增獎品</h2>
            </div>
            <form id="prizeForm" onsubmit="savePrize(event)">
                <input type="hidden" id="prizeId" value="">
                <div class="form-group">
                    <label>獎品名稱 *</label>
                    <input type="text" id="prizeName" required>
                </div>
                <div class="form-group">
                    <label>描述</label>
                    <textarea id="prizeDescription"></textarea>
                </div>
                <div class="form-group">
                    <label>圖標 (Emoji)</label>
                    <input type="text" id="prizeIcon" value="🎁" maxlength="2">
                </div>
                <div class="form-group">
                    <label>每日發放限制 (0 = 無限制)</label>
                    <input type="number" id="prizeDailyLimit" value="0" min="0">
                </div>
                <div class="form-group">
                    <label>中獎機率 (%) *</label>
                    <input type="number" id="prizeProbability" value="10.0" min="0" max="100" step="0.1" required>
                    <div style="font-size: 0.85rem; color: #999; margin-top: 5px;">
                        輸入 0-100 之間的百分比。系統會根據所有啟用獎品的機率自動計算實際中獎機率。
                    </div>
                    <div id="actualProbability" style="font-size: 0.85rem; color: #4CAF50; margin-top: 5px; font-weight: bold;">
                        實際機率：計算中...
                    </div>
                </div>
                <div class="form-group">
                    <label>
                        <input type="checkbox" id="prizeIsActive" checked> 啟用此獎品
                    </label>
                </div>
                <div class="form-actions">
                    <button type="button" class="btn secondary" onclick="closeModal()">取消</button>
                    <button type="submit" class="btn">儲存</button>
                </div>
            </form>
        </div>
    </div>
    
    <div class="status-indicator" id="statusIndicator"></div>
    
    <script>
        let prizes = [];
        
        function showStatus(message, type = 'success') {
            const indicator = document.getElementById('statusIndicator');
            indicator.textContent = message;
            indicator.className = `status-indicator ${type} show`;
            setTimeout(() => {
                indicator.classList.remove('show');
            }, 3000);
        }
        
        function loadPrizes() {
            fetch('/api/prizes')
                .then(r => r.json())
                .then(data => {
                    prizes = data;
                    renderPrizes();
                })
                .catch(e => {
                    console.error('載入獎品失敗:', e);
                    showStatus('載入獎品失敗', 'error');
                });
        }
        
        function renderPrizes() {
            const grid = document.getElementById('prizesGrid');
            if (prizes.length === 0) {
                grid.innerHTML = '<div style="text-align: center; color: #999; grid-column: 1/-1;">尚無獎品，點擊「新增獎品」開始管理</div>';
                return;
            }
            
            grid.innerHTML = prizes.map(prize => `
                <div class="prize-card ${prize.is_active ? '' : 'inactive'}">
                    <div class="prize-header">
                        <span class="prize-icon">${prize.icon || '🎁'}</span>
                        <span class="prize-name">${prize.name}</span>
                        <span class="prize-status ${prize.is_active ? '' : 'inactive'}">
                            ${prize.is_active ? '啟用' : '停用'}
                        </span>
                    </div>
                    <div class="prize-info">
                        <div class="prize-info-item">
                            <span class="prize-info-label">描述：</span>
                            <span>${prize.description || '無'}</span>
                        </div>
                        <div class="prize-info-item">
                            <span class="prize-info-label">每日限制：</span>
                            <span>${prize.daily_limit === 0 ? '無限制' : prize.daily_limit + ' 個'}</span>
                        </div>
                        <div class="prize-info-item">
                            <span class="prize-info-label">今日已發：</span>
                            <span>${prize.today_count || 0} 個</span>
                        </div>
                        <div class="prize-info-item">
                            <span class="prize-info-label">剩餘可發：</span>
                            <span>${prize.remaining === -1 ? '無限制' : (prize.remaining >= 0 ? prize.remaining + ' 個' : '已達上限')}</span>
                        </div>
                        <div class="prize-info-item">
                            <span class="prize-info-label">中獎機率：</span>
                            <span style="color: #4CAF50; font-weight: bold; font-size: 1.1rem;">${prize.probability || 0}%</span>
                        </div>
                    </div>
                    <div class="prize-actions">
                        <button class="btn btn-small secondary" onclick="editPrize(${prize.id})">✏️ 編輯</button>
                        <button class="btn btn-small danger" onclick="deletePrize(${prize.id})">🗑️ 刪除</button>
                    </div>
                </div>
            `).join('');
        }
        
        function openAddModal() {
            document.getElementById('modalTitle').textContent = '新增獎品';
            document.getElementById('prizeForm').reset();
            document.getElementById('prizeId').value = '';
            document.getElementById('prizeIcon').value = '🎁';
            document.getElementById('prizeDailyLimit').value = '0';
            document.getElementById('prizeProbability').value = '10.0';
            document.getElementById('prizeIsActive').checked = true;
            updateActualProbability();
            document.getElementById('prizeModal').classList.add('active');
        }
        
        function editPrize(id) {
            const prize = prizes.find(p => p.id === id);
            if (!prize) return;
            
            document.getElementById('modalTitle').textContent = '編輯獎品';
            document.getElementById('prizeId').value = prize.id;
            document.getElementById('prizeName').value = prize.name;
            document.getElementById('prizeDescription').value = prize.description || '';
            document.getElementById('prizeIcon').value = prize.icon || '🎁';
            document.getElementById('prizeDailyLimit').value = prize.daily_limit || 0;
            // 將權重轉換為百分比顯示（假設權重 = 百分比）
            document.getElementById('prizeProbability').value = prize.weight || 10.0;
            document.getElementById('prizeIsActive').checked = prize.is_active;
            updateActualProbability();
            document.getElementById('prizeModal').classList.add('active');
        }
        
        function closeModal() {
            document.getElementById('prizeModal').classList.remove('active');
        }
        
        // 計算並更新實際機率顯示
        function updateActualProbability() {
            const probabilityInput = document.getElementById('prizeProbability');
            const actualDiv = document.getElementById('actualProbability');
            if (!probabilityInput || !actualDiv) return;
            
            const inputProbability = parseFloat(probabilityInput.value) || 0;
            
            // 獲取所有啟用獎品的機率總和（不包括當前編輯的獎品）
            const currentId = document.getElementById('prizeId').value;
            const activePrizes = prizes.filter(p => p.is_active && p.id.toString() !== currentId);
            const totalProbability = activePrizes.reduce((sum, p) => sum + (p.weight || 10), 0);
            const newTotal = totalProbability + inputProbability;
            
            if (newTotal > 0) {
                const actualProbability = (inputProbability / newTotal * 100).toFixed(2);
                actualDiv.textContent = `實際機率：${actualProbability}%`;
                actualDiv.style.color = '#4CAF50';
            } else {
                actualDiv.textContent = '實際機率：計算中...';
                actualDiv.style.color = '#999';
            }
        }
        
        function savePrize(event) {
            event.preventDefault();
            const id = document.getElementById('prizeId').value;
            // 將百分比轉換為權重（百分比直接作為權重值）
            const probability = parseFloat(document.getElementById('prizeProbability').value) || 10.0;
            const data = {
                name: document.getElementById('prizeName').value,
                description: document.getElementById('prizeDescription').value,
                icon: document.getElementById('prizeIcon').value,
                daily_limit: parseInt(document.getElementById('prizeDailyLimit').value) || 0,
                weight: probability, // 將百分比作為權重
                is_active: document.getElementById('prizeIsActive').checked
            };
            
            const url = id ? `/api/prizes/${id}` : '/api/prizes';
            const method = id ? 'PUT' : 'POST';
            
            fetch(url, {
                method: method,
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            })
            .then(r => r.json())
            .then(result => {
                if (result.error) {
                    showStatus('操作失敗: ' + result.error, 'error');
                } else {
                    showStatus(id ? '獎品已更新' : '獎品已新增', 'success');
                    closeModal();
                    loadPrizes();
                }
            })
            .catch(e => {
                console.error('儲存失敗:', e);
                showStatus('儲存失敗', 'error');
            });
        }
        
        function deletePrize(id) {
            if (!confirm('確定要刪除此獎品嗎？此操作無法復原。')) return;
            
            fetch(`/api/prizes/${id}`, {method: 'DELETE'})
                .then(r => r.json())
                .then(result => {
                    if (result.error) {
                        showStatus('刪除失敗: ' + result.error, 'error');
                    } else {
                        showStatus('獎品已刪除', 'success');
                        loadPrizes();
                    }
                })
                .catch(e => {
                    console.error('刪除失敗:', e);
                    showStatus('刪除失敗', 'error');
                });
        }
        
        function resetDailyCount() {
            if (!confirm('確定要重置今日的獎品發放計數嗎？')) return;
            
            fetch('/api/prizes/reset-daily', {method: 'POST'})
                .then(r => r.json())
                .then(result => {
                    showStatus(result.message || '已重置今日計數', 'success');
                    loadPrizes();
                })
                .catch(e => {
                    console.error('重置失敗:', e);
                    showStatus('重置失敗', 'error');
                });
        }
        
        function resetDrawRecords() {
            if (!confirm('確定要清除所有用戶的抽獎紀錄嗎？\\n\\n這將允許所有用戶在8小時後重新抽獎，並且會重置今日的獎品發放計數。')) return;
            
            fetch('/api/prizes/reset-draw-records', {method: 'POST'})
                .then(r => r.json())
                .then(result => {
                    showStatus(result.message || '已清除今日抽獎紀錄', 'success');
                    loadPrizes();
                })
                .catch(e => {
                    console.error('清除失敗:', e);
                    showStatus('清除失敗', 'error');
                });
        }
        
        // 點擊 modal 背景關閉
        document.getElementById('prizeModal').addEventListener('click', function(e) {
            if (e.target === this) closeModal();
        });
        
        // 載入轉盤模式狀態
        function loadWheelMode() {
            fetch('/api/wheel-mode')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('wheelModeToggle').checked = data.enabled;
                })
                .catch(e => {
                    console.error('載入轉盤模式狀態失敗:', e);
                });
        }
        
        // 切換轉盤模式
        function toggleWheelMode() {
            const enabled = document.getElementById('wheelModeToggle').checked;
            fetch('/api/wheel-mode', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({enabled: enabled})
            })
            .then(r => r.json())
            .then(result => {
                if (result.error) {
                    showStatus('操作失敗: ' + result.error, 'error');
                    // 恢復原狀態
                    document.getElementById('wheelModeToggle').checked = !enabled;
                } else {
                    showStatus(result.message || `轉盤模式已${enabled ? '開啟' : '關閉'}`, 'success');
                }
            })
            .catch(e => {
                console.error('更新轉盤模式失敗:', e);
                showStatus('更新失敗', 'error');
                // 恢復原狀態
                document.getElementById('wheelModeToggle').checked = !enabled;
            });
        }
        
        // 為機率輸入框添加實時更新
        document.addEventListener('DOMContentLoaded', function() {
            const probabilityInput = document.getElementById('prizeProbability');
            if (probabilityInput) {
                probabilityInput.addEventListener('input', updateActualProbability);
            }
        });
        
        // 載入時獲取獎品列表和轉盤模式狀態
        loadPrizes();
        loadWheelMode();
    </script>
</body>
</html>
"""
    return admin_html

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

        # 處理PORT環境變數
        port_str = os.environ.get("PORT", "8080")
        print(f"📝 PORT環境變數: '{port_str}'")

        try:
            port = int(port_str)
            print(f"✅ 解析端口號: {port}")
        except ValueError as e:
            print(f"⚠️ 無效的PORT值: '{port_str}'，使用預設端口8080")
            port = 8080

        # 嘗試啟動服務器，如果端口被佔用則嘗試其他端口
        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                print(f"🌐 嘗試啟動web服務器，端口: {port}")
                app.run(host="0.0.0.0", port=port, debug=False)
                break  # 成功啟動，跳出循環
            except OSError as e:
                if "Address already in use" in str(e) or "address already in use" in str(e).lower():
                    if attempt < max_attempts - 1:
                        port += 1
                        print(f"⚠️ 端口 {port - 1} 已被佔用，嘗試端口 {port}...")
                    else:
                        print(f"❌ 已嘗試 {max_attempts} 個端口，均被佔用。請手動指定可用端口。")
                        raise
                else:
                    raise

    except Exception as e:
        print(f"❌ 應用啟動失敗: {e}")
        import traceback
        traceback.print_exc()
        raise
