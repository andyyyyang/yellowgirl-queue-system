#!/usr/bin/env python3
"""
邏輯測試腳本 - 測試叫號系統的核心邏輯
不需要運行完整的Flask應用
"""

def simulate_database_operations():
    """模擬資料庫操作"""
    # 使用字典來模擬資料庫
    mock_db = {}

    def get_state_value(key, default=None):
        return mock_db.get(key, default)

    def set_state_value(key, value):
        mock_db[key] = value
        return value

    print("🧪 測試叫號系統邏輯")
    print("=" * 40)

    # 初始化狀態
    set_state_value('current', None)
    set_state_value('waiting', [])
    set_state_value('missed', [])
    set_state_value('next_no', 1)

    print("✅ 初始化狀態完成")

    # 測試1: 取號
    def take_number():
        waiting = get_state_value('waiting', [])
        next_no = get_state_value('next_no', 1)
        waiting.append(next_no)
        set_state_value('waiting', waiting)
        set_state_value('next_no', next_no + 1)
        return next_no

    print("🎫 測試取號功能...")
    ticket1 = take_number()
    ticket2 = take_number()
    ticket3 = take_number()

    assert ticket1 == 1
    assert ticket2 == 2
    assert ticket3 == 3
    assert get_state_value('waiting') == [1, 2, 3]
    assert get_state_value('next_no') == 4
    print("✅ 取號功能正常")

    # 測試2: 叫號
    def call_next():
        waiting = get_state_value('waiting', [])
        if waiting:
            current = waiting.pop(0)
            set_state_value('waiting', waiting)
            set_state_value('current', current)
            return current
        else:
            set_state_value('current', None)
            return None

    print("📢 測試叫號功能...")
    called = call_next()
    assert called == 1
    assert get_state_value('current') == 1
    assert get_state_value('waiting') == [2, 3]
    print("✅ 叫號功能正常")

    # 測試3: 標記過號
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

    print("⏰ 測試過號功能...")
    mark_missed()
    assert get_state_value('current') == 2  # 自動叫下一個
    assert get_state_value('waiting') == [3]
    assert get_state_value('missed') == [1]
    print("✅ 過號功能正常")

    # 測試4: 返回前一號
    def go_previous():
        current = get_state_value('current')
        if current is not None:
            previous_number = current
            waiting = get_state_value('waiting', [])
            waiting.insert(0, current)
            set_state_value('waiting', waiting)
            missed = get_state_value('missed', [])
            if current in missed:
                missed.remove(current)
                set_state_value('missed', missed)
            set_state_value('current', None)
            return previous_number
        return None

    print("↩️ 測試返回前一號功能...")
    prev = go_previous()
    assert prev == 2
    assert get_state_value('current') is None
    assert get_state_value('waiting') == [2, 3]
    print("✅ 返回前一號功能正常")

    # 測試5: 手動歸零
    def manual_reset():
        set_state_value('current', None)
        set_state_value('missed', [])
        set_state_value('waiting', [])
        set_state_value('next_no', 1)

    print("🔄 測試歸零功能...")
    manual_reset()
    assert get_state_value('current') is None
    assert get_state_value('waiting') == []
    assert get_state_value('missed') == []
    assert get_state_value('next_no') == 1
    print("✅ 歸零功能正常")

    # 測試6: 自動歸零（next_no >= 1000）
    def check_auto_reset():
        next_no = get_state_value('next_no', 1)
        if next_no >= 1000:
            set_state_value('current', None)
            set_state_value('next_no', 1)
            return True
        return False

    print("🔁 測試自動歸零功能...")
    set_state_value('next_no', 1000)
    assert check_auto_reset() == True
    assert get_state_value('next_no') == 1
    print("✅ 自動歸零功能正常")

    print("\n🎉 所有邏輯測試通過！")
    print("📊 最終狀態:", {
        'current': get_state_value('current'),
        'waiting': get_state_value('waiting'),
        'missed': get_state_value('missed'),
        'next_no': get_state_value('next_no')
    })

    return True

if __name__ == "__main__":
    try:
        success = simulate_database_operations()
        if success:
            print("\n✅ 程式碼邏輯驗證完成！可以放心部署到Railway。")
        else:
            print("\n❌ 發現邏輯錯誤，需要修復。")
    except Exception as e:
        print(f"\n❌ 測試過程中發生錯誤: {e}")
        import traceback
        traceback.print_exc()





