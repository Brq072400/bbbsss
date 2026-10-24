"""API 端到端冒烟测试（只用标准库，不依赖 requests/httpx）。

前提：后端已在本机 8000 端口启动（python run.py）
用法：python tools/smoke_api.py [--base http://127.0.0.1:8000]
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import urllib.error
import urllib.request
from typing import Any

BASE = "http://127.0.0.1:8000"
TOKEN = ""
ADMIN_TOKEN = ""
PASSED: list[str] = []
FAILED: list[tuple[str, str]] = []


def call(method: str, path: str, body: Any = None, token: str = "", expect: int = 200) -> Any:
    """发一个请求，返回 data 部分；失败时记录并返回 None。"""
    url = BASE + path
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            status = resp.status
    except urllib.error.HTTPError as exc:  # 4xx/5xx
        raw = exc.read().decode("utf-8", "replace")
        status = exc.code
    except Exception as exc:  # 连接失败等
        FAILED.append((f"{method} {path}", f"连接失败: {exc}"))
        return None

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        FAILED.append((f"{method} {path}", f"非 JSON 响应({status}): {raw[:120]}"))
        return None

    if status != expect:
        FAILED.append((f"{method} {path}", f"状态码 {status} != {expect}：{raw[:160]}"))
        return None
    # 只有期望成功时才要求业务码为 0；期望 403/409 等错误分支时业务码本就非 0
    if expect == 200 and isinstance(payload, dict) and payload.get("code") not in (0, None):
        FAILED.append((f"{method} {path}", f"业务码 {payload.get('code')}: {payload.get('message')}"))
        return None
    PASSED.append(f"{method} {path}")
    return payload.get("data") if isinstance(payload, dict) else payload


def items_of(data: Any) -> list:
    """兼容两种返回形态：分页对象 {items:[...]} 或纯数组 [...]。"""
    if isinstance(data, dict):
        got = data.get("items")
        return got if isinstance(got, list) else []
    return data if isinstance(data, list) else []


def main() -> int:
    """按业务流程串一遍所有模块的接口。"""
    global BASE, TOKEN, ADMIN_TOKEN
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=BASE)
    args = parser.parse_args()
    BASE = args.base.rstrip("/")

    print(f"目标: {BASE}\n")

    # ---------- 系统 ----------
    call("GET", "/")
    # /docs 返回 HTML，单独用裸请求验证即可（不能按 JSON 解析）
    try:
        with urllib.request.urlopen(BASE + "/docs", timeout=20) as resp:
            if resp.status == 200:
                PASSED.append("GET /docs")
            else:
                FAILED.append(("GET /docs", f"状态码 {resp.status}"))
    except Exception as exc:
        FAILED.append(("GET /docs", f"连接失败: {exc}"))

    # ---------- 用户模块 ----------
    uname = f"tester{random.randint(1000, 99999)}"
    phone = f"138{random.randint(10000000, 99999999)}"
    reg = call("POST", "/api/auth/register", {
        "username": uname, "password": "test123456", "nickname": "冒烟测试", "gender": 1,
        "phone": phone, "height": 175, "birthday": "1998-05-20",
    })
    if not reg:
        print("注册失败，后续流程无法继续")
        return report()
    TOKEN = reg["token"]
    call("GET", "/api/auth/me", token=TOKEN)
    call("POST", "/api/auth/login", {"username": uname, "password": "test123456"})
    call("POST", "/api/auth/login", {"account": uname, "password": "test123456"})
    call("GET", "/api/users/profile", token=TOKEN)
    call("PUT", "/api/users/profile", {"nickname": "冒烟测试2", "signature": "干就完了", "city": "上海", "height": 175}, token=TOKEN)
    call("GET", "/api/users/level", token=TOKEN)
    call("GET", "/api/users/level/rules", token=TOKEN)
    call("POST", "/api/users/checkin", token=TOKEN)
    call("POST", "/api/users/checkin", token=TOKEN, expect=409)          # 重复签到应报冲突
    call("GET", "/api/users/checkin/calendar", token=TOKEN)
    call("GET", "/api/users/checkin/stats", token=TOKEN)
    call("GET", "/api/users/notifications", token=TOKEN)
    call("GET", "/api/users/notifications/unread-count", token=TOKEN)
    call("POST", "/api/users/realname", {"real_name": "张三", "id_card": "110101199805201234"}, token=TOKEN)
    call("GET", "/api/users/realname", token=TOKEN)
    call("POST", "/api/auth/password/reset/request", {"phone": phone})

    # ---------- 动作库 ----------
    cats = call("GET", "/api/exercises/categories")
    call("GET", "/api/exercises", token=TOKEN)
    call("GET", "/api/exercises/search?keyword=%E5%8D%A7%E6%8E%A8", token=TOKEN)
    call("GET", "/api/exercises/filter/options", token=TOKEN)
    exer = call("GET", "/api/exercises/1", token=TOKEN)
    call("GET", "/api/exercises/1/related", token=TOKEN)
    for c in items_of(cats)[:1]:
        if c.get("slug"):
            call("GET", f"/api/exercises/category/{c['slug']}", token=TOKEN)

    # ---------- 计划 ----------
    plan = call("POST", "/api/plans/publish", {
        "name": "冒烟测试计划", "description": "自动化测试创建", "goal": "keep_fit",
        "cycle_type": "weekly", "cycle_days": 7, "is_public": True,
        "items": [
            {"day_index": 1, "exercise_id": 1, "sets": 3, "reps": 10, "rest_seconds": 60},
            {"day_index": 1, "exercise_id": 3, "sets": 3, "reps": 12, "rest_seconds": 60},
            {"day_index": 3, "exercise_id": 5, "sets": 4, "reps": 8, "rest_seconds": 90},
        ],
    }, token=TOKEN)
    if plan:
        pid = plan["id"]
        call("GET", "/api/plans/my", token=TOKEN)
        call("GET", f"/api/plans/{pid}", token=TOKEN)
        call("PUT", f"/api/plans/{pid}", {"name": "冒烟测试计划改"}, token=TOKEN)
        item = call("POST", f"/api/plans/{pid}/item", {"day_index": 3, "exercise_id": 7, "sets": 3, "reps": 12}, token=TOKEN)
        if item:
            call("PUT", f"/api/plans/{pid}/item/{item['id']}", {"sets": 4}, token=TOKEN)
            call("DELETE", f"/api/plans/{pid}/item/{item['id']}", token=TOKEN)
        share = call("POST", f"/api/plans/{pid}/share", {"expires_hours": 24}, token=TOKEN)
        if share:
            call("GET", f"/api/plans/share/{share['share_code']}", token=TOKEN)
            call("POST", f"/api/plans/share/{share['share_code']}/import", token=TOKEN)
        call("POST", f"/api/plans/{pid}/favorite", token=TOKEN)
        call("GET", "/api/plans/favorites", token=TOKEN)
        call("DELETE", f"/api/plans/{pid}/favorite", token=TOKEN)
        call("POST", f"/api/plans/{pid}/checkin", {"day_index": 1, "note": "第一天完成"}, token=TOKEN)
        call("GET", f"/api/plans/{pid}/checkin/records", token=TOKEN)
        call("GET", f"/api/plans/{pid}/stats", token=TOKEN)
        call("POST", f"/api/plans/{pid}/reminder", {"remind_time": "07:30", "weekdays": "1,3,5", "enabled": True}, token=TOKEN)
        call("GET", f"/api/plans/{pid}/reminder", token=TOKEN)
    call("GET", "/api/plans/checkin/today", token=TOKEN)
    call("GET", "/api/plans/templates", token=TOKEN)
    tpl = call("GET", "/api/plans/templates/1", token=TOKEN)
    if tpl:
        call("POST", "/api/plans/templates/1/use", token=TOKEN)

    # ---------- 课程 ----------
    call("GET", "/api/courses/categories", token=TOKEN)
    lst = call("GET", "/api/courses/list", token=TOKEN)
    course_items = items_of(lst)
    if course_items:
        cid = course_items[0]["id"]
        call("GET", f"/api/courses/{cid}", token=TOKEN)
        call("GET", f"/api/courses/{cid}/video", token=TOKEN)
        call("POST", f"/api/courses/{cid}/favorite", token=TOKEN)
        call("GET", "/api/courses/favorites", token=TOKEN)
        call("DELETE", f"/api/courses/{cid}/favorite", token=TOKEN)
        call("POST", f"/api/courses/{cid}/rating", {"score": 5}, token=TOKEN)
        call("GET", f"/api/courses/{cid}/rating", token=TOKEN)
        cm = call("POST", f"/api/courses/{cid}/comment", {"content": "课程很好，跟练一个月有明显效果"}, token=TOKEN)
        call("GET", f"/api/courses/{cid}/comments", token=TOKEN)
        call("GET", f"/api/courses/{cid}/related", token=TOKEN)

    # ---------- 运动记录 ----------
    rec = call("POST", "/api/records", {
        "workout_type": "strength", "title": "胸+三头", "duration_min": 45, "calories": 320,
        "feeling": 4, "note": "状态不错",
        "sets": [
            {"exercise_id": 1, "exercise_name": "杠铃卧推", "set_index": 1, "weight": 60, "reps": 10},
            {"exercise_id": 1, "exercise_name": "杠铃卧推", "set_index": 2, "weight": 65, "reps": 8},
            {"exercise_id": 16, "exercise_name": "绳索下压", "set_index": 1, "weight": 25, "reps": 12},
        ],
    }, token=TOKEN)
    if rec:
        rid = rec["id"]
        call("GET", "/api/records", token=TOKEN)
        call("GET", f"/api/records/{rid}", token=TOKEN)
        call("PUT", f"/api/records/{rid}", {"note": "补充备注"}, token=TOKEN)
    call("GET", "/api/records/statistics/monthly", token=TOKEN)
    call("GET", "/api/records/statistics/weekly", token=TOKEN)
    call("GET", "/api/records/statistics/summary", token=TOKEN)
    call("GET", "/api/records/statistics/trend", token=TOKEN)

    # ---------- 数据统计 ----------
    call("POST", "/api/stats/body", {"weight": 72.5, "body_fat": 18.2, "waist": 82}, token=TOKEN)
    call("GET", "/api/stats/body", token=TOKEN)
    call("GET", "/api/stats/body/latest", token=TOKEN)
    call("GET", "/api/stats/bmi?weight=72.5&height=175", token=TOKEN)
    call("GET", "/api/stats/bmi/records", token=TOKEN)
    call("GET", "/api/stats/trend/weight", token=TOKEN)
    call("GET", "/api/stats/trend/body-fat", token=TOKEN)
    call("GET", "/api/stats/calories/balance", token=TOKEN)
    call("GET", "/api/stats/calories/balance/month", token=TOKEN)
    call("GET", "/api/stats/frequency", token=TOKEN)
    call("GET", "/api/stats/dashboard", token=TOKEN)

    # ---------- 社区 ----------
    post = call("POST", "/api/community/posts", {
        "content": "今天完成了胸推 5x5，终于突破 70kg！", "images": [], "topic": "训练日记",
    }, token=TOKEN)
    if post:
        post_id = post["id"]
        call("GET", "/api/community/posts", token=TOKEN)
        call("GET", f"/api/community/posts/{post_id}", token=TOKEN)
        call("POST", f"/api/community/posts/{post_id}/like", token=TOKEN)
        call("POST", f"/api/community/posts/{post_id}/like", token=TOKEN, expect=409)
        call("DELETE", f"/api/community/posts/{post_id}/like", token=TOKEN)
        pc = call("POST", f"/api/community/posts/{post_id}/comment", {"content": "太强了！"}, token=TOKEN)
        call("GET", f"/api/community/posts/{post_id}/comments", token=TOKEN)
    call("GET", "/api/community/feed", token=TOKEN)
    call("GET", "/api/community/recommend", token=TOKEN)
    call("GET", "/api/community/search/users?keyword=tester", token=TOKEN)
    call("GET", "/api/community/users/1", token=TOKEN)
    call("GET", "/api/community/users/1/followers", token=TOKEN)

    # ---------- 饮食 ----------
    call("GET", "/api/diet/foods", token=TOKEN)
    call("GET", "/api/diet/foods/categories", token=TOKEN)
    foods = call("GET", "/api/diet/foods", token=TOKEN)
    food_items = items_of(foods)
    if food_items:
        fid = food_items[0]["id"]
        dr = call("POST", "/api/diet/records", {
            "meal_type": "lunch", "food_id": fid, "amount_g": 200,
        }, token=TOKEN)
        if dr:
            call("PUT", f"/api/diet/records/{dr['id']}", {"amount_g": 250}, token=TOKEN)
            call("DELETE", f"/api/diet/records/{dr['id']}", token=TOKEN)
    call("GET", "/api/diet/records", token=TOKEN)
    call("GET", "/api/diet/records/day", token=TOKEN)
    call("GET", "/api/diet/stats", token=TOKEN)

    # ---------- 后台管理 ----------
    adm = call("POST", "/api/admin/login", {"username": "admin", "password": "admin123456"})
    if adm:
        ADMIN_TOKEN = adm["token"]
        call("GET", "/api/admin/profile", token=ADMIN_TOKEN)
        call("GET", "/api/admin/dashboard", token=ADMIN_TOKEN)
        call("GET", "/api/admin/users", token=ADMIN_TOKEN)
        call("GET", "/api/admin/courses", token=ADMIN_TOKEN)
        call("GET", "/api/admin/comments", token=ADMIN_TOKEN)
        call("GET", "/api/admin/posts", token=ADMIN_TOKEN)
        call("GET", "/api/admin/plans", token=ADMIN_TOKEN)
        call("GET", "/api/admin/realnames", token=ADMIN_TOKEN)
        # 越权校验：普通用户令牌不能访问后台
        call("GET", "/api/admin/users", token=TOKEN, expect=403)

    return report()


def report() -> int:
    """打印测试结果摘要。"""
    print(f"\n通过 {len(PASSED)} 个接口，失败 {len(FAILED)} 个")
    if FAILED:
        print("\n失败明细：")
        for path, reason in FAILED:
            print(f"  ✗ {path}\n      {reason}")
        return 1
    print("全部通过 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
