#!/usr/bin/env python3
"""
簡化測試腳本 - 測試資料庫功能
"""

import os
import sys
from pathlib import Path

# 添加專案根目錄到Python路徑
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 添加虛擬環境
venv_path = project_root / 'venv' / 'bin'
if venv_path.exists():
    os.environ['PATH'] = str(venv_path) + ':' + os.environ['PATH']

def test_database_functionality():
    """測試資料庫基本功能"""
    print("🧪 測試資料庫功能")
    print("=" * 30)

    try:
        # 模擬Railway環境變數
        os.environ['DATABASE_URL'] = 'sqlite:///test_simple.db'

        # 匯入應用
        from main import app, db, TicketState, init_database, get_state_value, set_state_value

        print("✅ 成功匯入應用模組")

        # 在應用上下文中測試
        with app.app_context():
            print("📊 初始化資料庫...")
            db.create_all()
            print("✅ 資料庫表創建完成")

            # 測試資料庫操作
            print("🔄 測試資料庫操作...")

            # 測試設定值
            set_state_value('test_key', 'test_value')
            value = get_state_value('test_key')
            assert value == 'test_value', f"期望 'test_value', 得到 {value}"
            print("✅ 基本資料庫操作正常")

            # 測試叫號系統初始化
            init_database()
            print("✅ 資料庫初始化完成")

            # 測試叫號系統狀態
            current = get_state_value('current')
            waiting = get_state_value('waiting', [])
            missed = get_state_value('missed', [])
            next_no = get_state_value('next_no', 1)

            assert current is None, f"current 應該是 None, 得到 {current}"
            assert waiting == [], f"waiting 應該是 [], 得到 {waiting}"
            assert missed == [], f"missed 應該是 [], 得到 {missed}"
            assert next_no == 1, f"next_no 應該是 1, 得到 {next_no}"

            print("✅ 叫號系統狀態初始化正常")

            # 測試狀態更新
            set_state_value('waiting', [1, 2, 3])
            set_state_value('current', 1)
            set_state_value('next_no', 4)

            assert get_state_value('waiting') == [1, 2, 3]
            assert get_state_value('current') == 1
            assert get_state_value('next_no') == 4

            print("✅ 狀態更新功能正常")

        print("\n🎉 所有資料庫測試通過！")
        print("📊 程式碼邏輯正確，可以放心部署到Railway")

        return True

    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # 清理測試資料庫
        if os.path.exists('test_simple.db'):
            os.remove('test_simple.db')
            print("🧹 測試資料庫已清理")

if __name__ == "__main__":
    success = test_database_functionality()
    sys.exit(0 if success else 1)





