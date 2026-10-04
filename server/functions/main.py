# Welcome to Cloud Functions for Firebase for Python!
# To get started, simply uncomment the below code or create your own.
# Deploy with `firebase deploy`

from firebase_functions import https_fn
from firebase_functions.options import set_global_options
from firebase_admin import initialize_app
import json
import datetime

# 初始化 Firebase Admin
initialize_app()

# 設置全域選項
set_global_options(max_instances=10)

# 共享狀態（在實際生產環境中應該使用資料庫）
state = {
    "current": None,
    "waiting": [],
    "missed": [],
    "next_no": 1,
    "last_reset_date": None
}

# === API 端點 ===

@https_fn.on_request()
def status(req: https_fn.Request) -> https_fn.Response:
    """狀態 API"""
    if req.method != "GET":
        return https_fn.Response("Method not allowed", status=405)
    
    return https_fn.Response(
        json.dumps(state),
        status=200,
        headers={
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        }
    )

@https_fn.on_request()
def take(req: https_fn.Request) -> https_fn.Response:
    """取號 API"""
    if req.method == "OPTIONS":
        return https_fn.Response("", status=200, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        })
    
    if req.method != "POST":
        return https_fn.Response("Method not allowed", status=405)
    
    state["waiting"].append(state["next_no"])
    state["next_no"] += 1
    
    return https_fn.Response("", status=204, headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    })

@https_fn.on_request()
def next_call(req: https_fn.Request) -> https_fn.Response:
    """下一個號碼 API"""
    if req.method == "OPTIONS":
        return https_fn.Response("", status=200, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        })
    
    if req.method != "POST":
        return https_fn.Response("Method not allowed", status=405)
    
    if state["waiting"]:
        state["current"] = state["waiting"].pop(0)
    else:
        state["current"] = None
    
    return https_fn.Response("", status=204, headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    })

@https_fn.on_request()
def mark_missed(req: https_fn.Request) -> https_fn.Response:
    """標記過號 API"""
    if req.method == "OPTIONS":
        return https_fn.Response("", status=200, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        })
    
    if req.method != "POST":
        return https_fn.Response("Method not allowed", status=405)
    
    if state["current"] is not None:
        state["missed"].append(state["current"])
        state["current"] = None
        if state["waiting"]:
            state["current"] = state["waiting"].pop(0)
    
    return https_fn.Response("", status=204, headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    })

@https_fn.on_request()
def manual_reset(req: https_fn.Request) -> https_fn.Response:
    """手動歸零 API"""
    if req.method == "OPTIONS":
        return https_fn.Response("", status=200, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        })
    
    if req.method != "POST":
        return https_fn.Response("Method not allowed", status=405)
    
    state["current"] = None
    state["waiting"] = []
    state["missed"] = []
    state["next_no"] = 1
    
    return https_fn.Response(
        json.dumps({"status": "ok", "message": "已手動歸零"}),
        status=200,
        headers={
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        }
    )

@https_fn.on_request()
def go_previous(req: https_fn.Request) -> https_fn.Response:
    """返回前一號 API"""
    if req.method == "OPTIONS":
        return https_fn.Response("", status=200, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        })
    
    if req.method != "POST":
        return https_fn.Response("Method not allowed", status=405)
    
    if state["current"] is not None:
        previous_number = state["current"]
        state["waiting"].insert(0, state["current"])
        if state["current"] in state["missed"]:
            state["missed"].remove(state["current"])
        state["current"] = None
        
        return https_fn.Response(
            json.dumps({"status": "ok", "message": f"已返回前一號 {previous_number}"}),
            status=200,
            headers={
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
        )
    else:
        return https_fn.Response(
            json.dumps({"error": "目前沒有正在叫號"}),
            status=400,
            headers={
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
        )