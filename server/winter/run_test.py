#!/usr/bin/env python3
"""
測試啟動腳本 - 啟動應用並運行API測試
"""

import os
import sys
import time
import subprocess
import signal
import threading

def start_app():
    """啟動Flask應用"""
    print("🚀 啟動Flask應用...")
    env = os.environ.copy()
    env['FLASK_ENV'] = 'development'
    # 使用唯一的測試資料庫
    import uuid
    test_db_name = f'test_{uuid.uuid4().hex}.db'
    env['TEST_DB_NAME'] = test_db_name

    # 清理舊的測試資料庫
    for f in os.listdir('.'):
        if f.startswith('test_') and f.endswith('.db'):
            try:
                os.remove(f)
            except:
                pass

    # 啟動應用
    process = subprocess.Popen(
        [sys.executable, 'main.py'],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    return process

def wait_for_app(port=8080, timeout=10):
    """等待應用啟動"""
    import socket
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', port))
            sock.close()
            if result == 0:
                return True
        except:
            pass
        time.sleep(0.5)

    return False

def run_tests():
    """運行API測試"""
    print("🧪 運行API測試...")
    result = subprocess.run([sys.executable, 'test_api.py'],
                          capture_output=True, text=True)

    print("測試輸出:")
    print(result.stdout)
    if result.stderr:
        print("錯誤輸出:")
        print(result.stderr)

    return result.returncode == 0

def main():
    """主測試流程"""
    print("🧪 開始叫號系統測試")
    print("=" * 50)

    # 啟動應用
    app_process = start_app()

    try:
        # 等待應用啟動
        print("⏳ 等待應用啟動...")
        if not wait_for_app():
            print("❌ 應用啟動失敗")
            return False

        print("✅ 應用已啟動")

        # 運行測試
        success = run_tests()

        if success:
            print("\n🎉 所有測試通過！")
            return True
        else:
            print("\n❌ 測試失敗")
            return False

    finally:
        # 清理：停止應用
        print("🧹 清理測試環境...")
        app_process.terminate()
        app_process.wait(timeout=5)

        # 刪除測試資料庫
        if os.path.exists('ticket_system_test.db'):
            os.remove('ticket_system_test.db')
            print("✅ 測試資料庫已清理")

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
