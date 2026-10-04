#!/usr/bin/env python3
"""
資料庫功能測試腳本
"""

import os
import sys
from pathlib import Path

# 添加專案根目錄到Python路徑
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_database():
    """測試資料庫功能"""
    print("🧪 測試資料庫功能")
    print("=" * 30)

    try:
        # 模擬環境變數
        os.environ['DATABASE_URL'] = 'sqlite:///test_ticket.db'

        # 匯入應用
        from main import app, db, TicketState, init_database, get_state_value, set_state_value

        print("✅ 成功匯入應用模組")

        # 在應用上下文中測試
        with app.app_context():
            print("📊 初始化資料庫...")
            db.create_all()
            print("✅ 資料庫初始化完成")

            # 測試設定和獲取值
            print("🔄 測試狀態存取...")

            # 測試基本功能
            set_state_value('test_key', 'test_value')
            value = get_state_value('test_key')
            assert value == 'test_value'
            print("✅ 基本狀態存取測試通過")

            # 測試叫號系統功能
            set_state_value('current', None)
            set_state_value('waiting', [1, 2, 3])
            set_state_value('missed', [])
            set_state_value('next_no', 4)

            current = get_state_value('current')
            waiting = get_state_value('waiting')
            missed = get_state_value('missed')
            next_no = get_state_value('next_no')

            assert current is None
            assert waiting == [1, 2, 3]
            assert missed == []
            assert next_no == 4

            print("✅ 叫號系統狀態測試通過")

            # 測試狀態更新
            waiting.pop(0)
            set_state_value('waiting', waiting)
            set_state_value('current', 1)

            assert get_state_value('waiting') == [2, 3]
            assert get_state_value('current') == 1

            print("✅ 狀態更新測試通過")

        print("\n🎉 所有資料庫測試通過！")
        return True

    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # 清理測試資料庫
        if os.path.exists('test_ticket.db'):
            os.remove('test_ticket.db')
            print("🧹 測試資料庫已清理")

if __name__ == "__main__":
    success = test_database()
    sys.exit(0 if success else 1)





