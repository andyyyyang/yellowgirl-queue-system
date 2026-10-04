#!/usr/bin/env python3
"""
API測試腳本 - 測試叫號系統的所有功能
"""

import requests
import time
import json
import os
import sys
from pathlib import Path

# 添加專案根目錄到Python路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_api():
    """測試所有API端點"""
    base_url = "http://localhost:8080"

    print("🚀 開始測試叫號系統API")
    print("=" * 50)

    try:
        # 測試1: 檢查初始狀態
        print("📊 測試1: 檢查初始狀態")
        response = requests.get(f"{base_url}/status")
        if response.status_code == 200:
            data = response.json()
            print("✅ 初始狀態:", data)
            assert data['current'] is None
            assert data['waiting'] == []
            assert data['missed'] == []
            assert data['next_no'] == 1
        else:
            print(f"❌ 狀態檢查失敗: {response.status_code}")
            return False

        # 測試2: 取號
        print("\n🎫 測試2: 取號")
        response = requests.post(f"{base_url}/take")
        if response.status_code == 204:
            print("✅ 取號成功")
        else:
            print(f"❌ 取號失敗: {response.status_code}")
            return False

        # 檢查狀態 - 應該有一個等待號碼
        response = requests.get(f"{base_url}/status")
        data = response.json()
        print("📊 取號後狀態:", data)
        assert data['waiting'] == [1]
        assert data['next_no'] == 2

        # 測試3: 叫號
        print("\n📢 測試3: 叫號")
        response = requests.post(f"{base_url}/next")
        if response.status_code == 204:
            print("✅ 叫號成功")
        else:
            print(f"❌ 叫號失敗: {response.status_code}")
            return False

        # 檢查狀態 - 號碼1應該移到current
        response = requests.get(f"{base_url}/status")
        data = response.json()
        print("📊 叫號後狀態:", data)
        assert data['current'] == 1
        assert data['waiting'] == []

        # 測試4: 標記過號
        print("\n⏰ 測試4: 標記過號")
        response = requests.post(f"{base_url}/miss")
        if response.status_code == 204:
            print("✅ 標記過號成功")
        else:
            print(f"❌ 標記過號失敗: {response.status_code}")
            return False

        # 檢查狀態 - 號碼1應該移到missed
        response = requests.get(f"{base_url}/status")
        data = response.json()
        print("📊 過號後狀態:", data)
        assert data['current'] is None
        assert data['missed'] == [1]

        # 測試5: 再次取號
        print("\n🎫 測試5: 再次取號")
        response = requests.post(f"{base_url}/take")
        response = requests.post(f"{base_url}/take")
        response = requests.post(f"{base_url}/next")
        print("✅ 再次取號並叫號")

        # 測試6: 返回前一號
        print("\n↩️ 測試6: 返回前一號")
        response = requests.post(f"{base_url}/previous")
        if response.status_code == 200:
            data = response.json()
            print("✅ 返回前一號成功:", data['message'])
        else:
            print(f"❌ 返回前一號失敗: {response.status_code}")
            return False

        # 測試7: 手動歸零
        print("\n🔄 測試7: 手動歸零")
        response = requests.post(f"{base_url}/reset")
        if response.status_code == 200:
            data = response.json()
            print("✅ 歸零成功:", data['message'])
        else:
            print(f"❌ 歸零失敗: {response.status_code}")
            return False

        # 檢查最終狀態
        response = requests.get(f"{base_url}/status")
        data = response.json()
        print("📊 最終狀態:", data)
        assert data['current'] is None
        assert data['waiting'] == []
        assert data['missed'] == []
        assert data['next_no'] == 1

        print("\n🎉 所有測試通過！")
        return True

    except Exception as e:
        print(f"❌ 測試過程中發生錯誤: {e}")
        return False

if __name__ == "__main__":
    # 檢查應用是否正在運行
    try:
        response = requests.get("http://localhost:8080/healthz", timeout=5)
        if response.status_code == 200:
            print("✅ 應用正在運行")
        else:
            print("❌ 應用未正確運行")
            print("請先運行: python main.py")
            sys.exit(1)
    except:
        print("❌ 無法連接到應用")
        print("請先運行: python main.py")
        sys.exit(1)

    # 運行測試
    success = test_api()
    sys.exit(0 if success else 1)





