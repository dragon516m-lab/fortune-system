import os
import re
import sys
import json
import logging
import datetime
import uuid
import time
import random
import threading
from pathlib import Path

# ---- エンコーディング設定（全importより先に実行） ----
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

# ---- Werkzeug/Flask のログを完全に無効化 ----
logging.getLogger("werkzeug").disabled = True
logging.getLogger("werkzeug").propagate = False

import anthropic
import requests as http_requests
from flask import Flask, render_template, request, Response, send_file, stream_with_context
from dotenv import load_dotenv
from pathlib import Path

try:
    from supabase import create_client as _sb_create
except ImportError:
    _sb_create = None

from fortune.calculator import calculate_all, format_for_prompt

load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)

app = Flask(__name__)
app.logger.disabled = True

RESULTS_DIR = Path("results")
RESULTS_DIR.mkdir(exist_ok=True)

ORDERS_DIR = Path("orders")
ORDERS_DIR.mkdir(exist_ok=True)
ORDERS_FILE = ORDERS_DIR / "coconala_orders.json"

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
HISTORY_FILE = DATA_DIR / "history.json"

# Supabase（設定があれば使用、なければJSONファイルにフォールバック）
_supabase = None

def get_supabase():
    global _supabase
    if _supabase is not None:
        return _supabase
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_ANON_KEY", "")
    if url and key and _sb_create:
        try:
            _supabase = _sb_create(url, key)
        except Exception:
            _supabase = None
    return _supabase


def load_orders():
    if not ORDERS_FILE.exists():
        return []
    return json.loads(ORDERS_FILE.read_bytes())


def save_orders(orders):
    ORDERS_FILE.write_bytes(
        json.dumps(orders, ensure_ascii=False, indent=2).encode("utf-8")
    )


def load_history_data():
    sb = get_supabase()
    if sb:
        try:
            res = sb.table("history").select("*").order("id").execute()
            return res.data or []
        except Exception:
            pass
    if not HISTORY_FILE.exists():
        return []
    try:
        return json.loads(HISTORY_FILE.read_bytes())
    except Exception:
        return []


def append_history_entry(entry: dict) -> int:
    sb = get_supabase()
    if sb:
        try:
            row = {k: v for k, v in entry.items() if k != "id"}
            res = sb.table("history").insert(row).execute()
            return (res.data[0]["id"]) if res.data else 0
        except Exception:
            pass
    # JSONファイルへフォールバック
    try:
        history = load_history_data()
        next_id = (history[-1]["id"] + 1) if history else 1
        entry["id"] = next_id
        history.append(entry)
        HISTORY_FILE.write_bytes(
            json.dumps(history, ensure_ascii=False, indent=2).encode("utf-8")
        )
        return next_id
    except Exception:
        return 0


FORTUNE_SYSTEM_PROMPT = (
    "\u3042\u306a\u305f\u306f\u56db\u67f1\u63a8\u547d\u30fb"
    "\u6570\u79d8\u8853\u30fb\u52d5\u7269\u5360\u3044\u306b"
    "\u7cbe\u901a\u3057\u305f\u5360\u3044\u5e2b\u3067\u3059\u3002"
    "\u6e29\u304b\u307f\u306e\u3042\u308b\u65e5\u672c\u8a9e\u3067"
    "\u3001\u76f8\u8ac7\u8005\u306b\u5bc4\u308a\u6dfb\u3063\u305f"
    "\u6df1\u307f\u306e\u3042\u308b\u9451\u5b9a\u6587\u3092"
    "\u66f8\u3044\u3066\u304f\u3060\u3055\u3044\u3002"
    "##\u3084**\u306a\u3069\u306e\u30de\u30fc\u30af\u30c0\u30a6\u30f3"
    "\u8a18\u6cd5\u306f\u4e00\u5207\u4f7f\u308f\u306a\u3044\u3067"
    "\u304f\u3060\u3055\u3044\u3002\u898b\u51fa\u3057\u306f"
    "\u3010\u3011\u3067\u56f2\u3093\u3060\u30d7\u30ec"
    "\u30fc\u30f3\u30c6\u30ad\u30b9\u30c8\u3060\u3051\u3092\u4f7f"
    "\u3063\u3066\u304f\u3060\u3055\u3044\u3002"
)

_client = None

def get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY") or None
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


# ---- SSE / JSON ヘルパー（絶対に UnicodeEncodeError を出さない） ----

def _safe_dumps(obj) -> bytes:
    """ensure_ascii=True で JSON シリアライズ → UTF-8 バイト列。
    日本語は \\uXXXX にエスケープされるため ASCII 範囲のみになる。"""
    return json.dumps(obj, ensure_ascii=True).encode("utf-8")


def sse_bytes(payload: dict) -> bytes:
    return b"data: " + _safe_dumps(payload) + b"\n\n"


def json_resp(payload, status: int = 200) -> Response:
    return Response(
        response=_safe_dumps(payload),
        status=status,
        content_type="application/json; charset=utf-8",
    )


def safe_str(obj) -> str:
    """例外オブジェクトを ASCII 安全な文字列に変換する。"""
    try:
        text = repr(obj)
        return text.encode("ascii", errors="backslashreplace").decode("ascii")
    except Exception:
        return "unknown_error"


# ---- ルーティング ----

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/generate-questions", methods=["POST"])
def generate_questions():
    body    = request.get_json(force=True, silent=True) or {}
    concern = str(body.get("concern") or "")

    if not concern:
        return json_resp({"error": "missing_concern"}, 400)

    prompt = (
        "以下の相談内容について、より深い鑑定を行うための掘り下げ質問を3個生成してください。\n\n"
        f"相談内容: {concern}\n\n"
        "質問の種類:\n"
        "- 具体的な状況を聞く\n"
        "- 相手との関係性を聞く（該当する場合）\n"
        "- 一番知りたいことを聞く\n"
        "- 過去の経緯を聞く\n"
        "- 理想の未来を聞く\n\n"
        "丁寧で優しい口調で、お客様が答えやすい質問にしてください。\n"
        "質問のみを番号付きで出力してください。前置きや説明文は一切不要です。\n"
        "各質問は必ず「？」で終わらせてください。"
    )

    try:
        message = get_client().messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = message.content[0].text

        questions = []
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            cleaned = re.sub(r"^[\d]+[.．）)]\s*", "", line)
            cleaned = re.sub(r"^[-・•*＊]\s*", "", cleaned).strip()
            if cleaned and len(cleaned) > 5 and "？" in cleaned:
                questions.append(cleaned)

        return json_resp({"questions": questions})
    except Exception as e:
        return json_resp({"error": safe_str(e)}, 500)


@app.route("/api/fortune", methods=["POST"])
def get_fortune():
    body = request.get_json(force=True, silent=True) or {}

    name               = str(body.get("name") or "")
    birthdate_s        = str(body.get("birthdate") or "")
    concern            = str(body.get("concern") or "")
    detail_context     = str(body.get("detail_context") or "")
    detailed_questions = list(body.get("detailed_questions") or [])
    detailed_answers   = list(body.get("detailed_answers") or [])
    partner_birthdate  = str(body.get("partner_birthdate") or "")
    relationship       = str(body.get("relationship") or "")

    if not birthdate_s or not concern:
        return json_resp({"error": "missing_params"}, 400)

    try:
        bd = datetime.datetime.strptime(birthdate_s, "%Y-%m-%d")
    except ValueError:
        return json_resp({"error": "invalid_date"}, 400)

    try:
        fortune_data = calculate_all(bd.year, bd.month, bd.day)
        prompt       = format_for_prompt(fortune_data, concern, name)
        if detail_context:
            prompt = prompt.replace(
                f"お悩み・ご相談：{concern}",
                f"お悩み・ご相談：\n{detail_context}",
            )
    except Exception as e:
        return json_resp({"error": safe_str(e)}, 500)

    def generate():
        try:
            yield sse_bytes({"status": "connecting"})

            full_text = ""
            with get_client().messages.stream(
                model="claude-opus-4-6",
                max_tokens=16384,
                system=FORTUNE_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                for chunk in stream.text_stream:
                    full_text += chunk
                    yield sse_bytes({"chunk": chunk})

            ts  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            fid = f"fortune_{ts}"

            # doneを先に送ってUIをすぐ更新する
            yield sse_bytes({"done": True, "file_id": fid, "fortune_data": fortune_data})

            # 保存はdone送信後に実施（UIをブロックしない）
            try:
                path = RESULTS_DIR / f"{fid}.json"
                path.write_bytes(json.dumps({
                    "timestamp":    datetime.datetime.now().isoformat(),
                    "name":         name,
                    "birthdate":    birthdate_s,
                    "concern":      concern,
                    "fortune_data": fortune_data,
                    "reading":      full_text,
                }, ensure_ascii=False, indent=2).encode("utf-8"))
            except Exception:
                pass

            append_history_entry({
                "timestamp":           datetime.datetime.now().isoformat(),
                "name":                name,
                "birthdate":           birthdate_s,
                "consultation":        concern,
                "partner_birthdate":   partner_birthdate,
                "relationship":        relationship,
                "detailed_questions":  detailed_questions,
                "detailed_answers":    detailed_answers,
                "result":              full_text,
                "compatibility_result": "",
                "chat_messages":       [],
                "file_id":             fid,
            })

        except Exception as e:
            yield sse_bytes({"error": safe_str(e)})

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/continue", methods=["POST"])
def continue_fortune():
    body         = request.get_json(force=True, silent=True) or {}
    partial_text = str(body.get("partial_text") or "")
    concern      = str(body.get("concern") or "")

    if not partial_text:
        return json_resp({"error": "missing_params"}, 400)

    continuation_prompt = (
        "\u4ee5\u4e0b\u306e\u5360\u3044\u9451\u5b9a\u6587\u306e\u7d9a\u304d\u3092\u66f8\u3044\u3066\u304f\u3060\u3055\u3044\u3002\n"
        "\u3059\u3067\u306b\u66f8\u304b\u308c\u305f\u5185\u5bb9\u306f\u7e70\u308a\u8fd4\u3055\u305a\u3001\u7d9a\u304d\u306e\u672a\u5b8c\u6210\u30bb\u30af\u30b7\u30e7\u30f3\u306e\u307f\u66f8\u3044\u3066\u304f\u3060\u3055\u3044\u3002\n\n"
        "\u3053\u308c\u307e\u3067\u306e\u9451\u5b9a\u6587\uff1a\n"
    ) + partial_text

    def generate():
        try:
            yield sse_bytes({"status": "connecting"})
            with get_client().messages.stream(
                model="claude-opus-4-6",
                max_tokens=8192,
                system=FORTUNE_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": continuation_prompt}],
            ) as stream:
                for chunk in stream.text_stream:
                    yield sse_bytes({"chunk": chunk})
            yield sse_bytes({"done": True})
        except Exception as e:
            yield sse_bytes({"error": safe_str(e)})

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/post-threads", methods=["POST"])
def post_threads():
    access_token = os.environ.get("THREADS_ACCESS_TOKEN", "")
    user_id      = os.environ.get("THREADS_USER_ID", "")

    if not access_token or not user_id:
        return json_resp({"error": "threads_not_configured"}, 400)

    body = request.get_json(force=True, silent=True) or {}
    text = str(body.get("text") or "")

    if not text:
        return json_resp({"error": "missing_text"}, 400)

    # 500文字制限
    if len(text) > 500:
        text = text[:497] + "..."

    base_url = f"https://graph.threads.net/v1.0/{user_id}"

    try:
        # Step1: コンテナ作成
        r1 = http_requests.post(
            f"{base_url}/threads",
            params={
                "media_type":   "TEXT",
                "text":         text,
                "access_token": access_token,
            },
            timeout=15,
        )
        r1.raise_for_status()
        creation_id = r1.json().get("id")
        if not creation_id:
            return json_resp({"error": "no_creation_id"}, 500)

        # Step2: 公開
        r2 = http_requests.post(
            f"{base_url}/threads_publish",
            params={
                "creation_id":  creation_id,
                "access_token": access_token,
            },
            timeout=15,
        )
        r2.raise_for_status()
        post_id = r2.json().get("id", "")
        return json_resp({"success": True, "post_id": post_id})

    except http_requests.HTTPError as e:
        try:
            detail = e.response.json()
        except Exception:
            detail = {}
        return json_resp({"error": "threads_api_error", "detail": detail}, 500)
    except Exception as e:
        return json_resp({"error": safe_str(e)}, 500)


@app.route("/api/debug-supabase")
def debug_supabase():
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_ANON_KEY", "")
    info = {
        "url_set": bool(url),
        "key_set": bool(key),
        "key_prefix": key[:20] if key else "",
        "sb_create_available": _sb_create is not None,
    }
    sb = get_supabase()
    info["client_created"] = sb is not None
    if sb:
        try:
            res = sb.table("history").select("id").limit(1).execute()
            info["query_ok"] = True
            info["row_count"] = len(res.data or [])
        except Exception as e:
            info["query_ok"] = False
            info["query_error"] = safe_str(e)
        try:
            test_row = {"timestamp": "2000-01-01T00:00:00", "name": "__test__", "birthdate": "2000-01-01",
                        "consultation": "test", "result": "test", "compatibility_result": "",
                        "chat_messages": [], "file_id": "test", "partner_birthdate": "",
                        "relationship": "", "detailed_questions": [], "detailed_answers": []}
            res2 = sb.table("history").insert(test_row).execute()
            if res2.data:
                sb.table("history").delete().eq("name", "__test__").execute()
                info["insert_ok"] = True
            else:
                info["insert_ok"] = False
                info["insert_response"] = str(res2)
        except Exception as e:
            info["insert_ok"] = False
            info["insert_error"] = safe_str(e)
    return json_resp(info)


@app.route("/api/history-list")
def get_history_list():
    sb = get_supabase()
    if sb:
        try:
            res = sb.table("history").select("id,timestamp,name,birthdate,consultation,file_id").order("id", desc=True).limit(20).execute()
            items = []
            for row in (res.data or []):
                concern = str(row.get("consultation") or "")
                items.append({
                    "file_id":    row.get("file_id") or "",
                    "history_id": row.get("id"),
                    "timestamp":  str(row.get("timestamp", ""))[:16].replace("T", " "),
                    "name":       str(row.get("name") or ""),
                    "birthdate":  str(row.get("birthdate") or ""),
                    "concern":    concern[:30] + "..." if len(concern) > 30 else concern,
                })
            return Response(response=_safe_dumps(items), content_type="application/json; charset=utf-8")
        except Exception:
            pass
    # Supabase未設定時はローカルファイルにフォールバック
    items = []
    for p in sorted(RESULTS_DIR.glob("fortune_*.json"), reverse=True)[:20]:
        try:
            data    = json.loads(p.read_bytes())
            concern = str(data.get("concern") or "")
            items.append({
                "file_id":    p.stem,
                "history_id": None,
                "timestamp":  str(data.get("timestamp", ""))[:16].replace("T", " "),
                "name":       str(data.get("name") or ""),
                "birthdate":  str(data.get("birthdate") or ""),
                "concern":    concern[:30] + "..." if len(concern) > 30 else concern,
            })
        except Exception:
            pass
    return Response(
        response=_safe_dumps(items),
        content_type="application/json; charset=utf-8",
    )


@app.route("/api/reading/<file_id>")
def get_reading(file_id):
    path = RESULTS_DIR / f"{file_id}.json"
    if not path.exists():
        return json_resp({"error": "not_found"}, 404)
    data = json.loads(path.read_bytes())
    return Response(
        response=_safe_dumps(data),
        content_type="application/json; charset=utf-8",
    )


@app.route("/api/download/<file_id>")
def download_result(file_id):
    path = RESULTS_DIR / f"{file_id}.json"
    if not path.exists():
        return json_resp({"error": "not_found"}, 404)

    data = json.loads(path.read_bytes())
    sc   = data["fortune_data"]["shichusuimei"]
    num  = data["fortune_data"]["numerology"]
    ani  = data["fortune_data"]["animal"]

    lines = [
        "=" * 50,
        "Fortune Reading",
        "=" * 50,
        "Date: " + str(data.get("timestamp", ""))[:16].replace("T", " "),
        "Birthdate: " + str(data.get("birthdate", "")),
        "Concern: " + str(data.get("concern", "")),
        "",
        "[Pillars] " + sc["year_pillar"]["pillar"]
            + " / " + sc["month_pillar"]["pillar"]
            + " / " + sc["day_pillar"]["pillar"],
        "[Life Path] " + str(num["life_path_number"]),
        "[Animal] " + ani["year_animal"]["animal"]
            + " / " + ani["day_animal"]["animal"],
        "",
        "[Reading]",
        str(data.get("reading", "")),
        "",
        "=" * 50,
    ]

    txt_path = RESULTS_DIR / f"{file_id}.txt"
    txt_path.write_bytes("\n".join(lines).encode("utf-8"))

    return send_file(
        txt_path,
        as_attachment=True,
        download_name=f"fortune_{data.get('birthdate','unknown')}.txt",
        mimetype="text/plain; charset=utf-8",
    )


# ---- cocナラ受注管理 ----

@app.route("/coconala-orders")
def coconala_orders_page():
    return render_template("coconala_orders.html")


@app.route("/api/coconala/orders", methods=["GET"])
def get_coconala_orders():
    orders = load_orders()
    return Response(
        response=_safe_dumps(orders),
        content_type="application/json; charset=utf-8",
    )


@app.route("/api/coconala/orders", methods=["POST"])
def create_coconala_orders():
    body    = request.get_json(force=True, silent=True) or {}
    entries = body.get("entries", [])

    if not entries:
        return json_resp({"error": "missing_entries"}, 400)

    orders  = load_orders()
    created = []

    for entry in entries:
        name        = str(entry.get("name") or "")
        birthdate_s = str(entry.get("birthdate") or "")
        concern     = str(entry.get("concern") or "")

        if not birthdate_s or not concern:
            continue
        try:
            datetime.datetime.strptime(birthdate_s, "%Y-%m-%d")
        except ValueError:
            continue

        ts       = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        order_id = f"order_{ts}_{uuid.uuid4().hex[:6]}"
        order    = {
            "id":             order_id,
            "name":           name,
            "birthdate":      birthdate_s,
            "concern":        concern,
            "status":         "未対応",
            "created_at":     datetime.datetime.now().isoformat(),
            "fortune_file_id": None,
            "reading":        None,
            "fortune_data":   None,
        }
        orders.append(order)
        created.append(order)

    save_orders(orders)
    return json_resp({"created": len(created), "orders": created})


@app.route("/api/coconala/orders/<order_id>", methods=["DELETE"])
def delete_coconala_order(order_id):
    orders = [o for o in load_orders() if o["id"] != order_id]
    save_orders(orders)
    return json_resp({"success": True})


@app.route("/api/coconala/orders/<order_id>/status", methods=["PATCH"])
def update_coconala_order_status(order_id):
    body       = request.get_json(force=True, silent=True) or {}
    new_status = str(body.get("status") or "")

    if new_status not in ("未対応", "鑑定中", "完了"):
        return json_resp({"error": "invalid_status"}, 400)

    orders = load_orders()
    for o in orders:
        if o["id"] == order_id:
            o["status"] = new_status
            save_orders(orders)
            return json_resp({"success": True})
    return json_resp({"error": "not_found"}, 404)


@app.route("/api/coconala/orders/<order_id>/fortune", methods=["POST"])
def run_coconala_fortune(order_id):
    orders = load_orders()
    order  = next((o for o in orders if o["id"] == order_id), None)

    if not order:
        return json_resp({"error": "not_found"}, 404)

    name        = str(order.get("name") or "")
    birthdate_s = str(order.get("birthdate") or "")
    concern     = str(order.get("concern") or "")

    try:
        bd = datetime.datetime.strptime(birthdate_s, "%Y-%m-%d")
    except ValueError:
        return json_resp({"error": "invalid_date"}, 400)

    try:
        fortune_data = calculate_all(bd.year, bd.month, bd.day)
        prompt       = format_for_prompt(fortune_data, concern, name)
    except Exception as e:
        return json_resp({"error": safe_str(e)}, 500)

    # ステータスを「鑑定中」に更新
    for o in orders:
        if o["id"] == order_id:
            o["status"] = "鑑定中"
    save_orders(orders)

    def generate():
        try:
            yield sse_bytes({"status": "connecting"})
            full_text = ""
            with get_client().messages.stream(
                model="claude-opus-4-6",
                max_tokens=16384,
                system=FORTUNE_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                for chunk in stream.text_stream:
                    full_text += chunk
                    yield sse_bytes({"chunk": chunk})

            ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            fid  = f"fortune_{ts}"
            path = RESULTS_DIR / f"{fid}.json"
            path.write_bytes(json.dumps({
                "timestamp":    datetime.datetime.now().isoformat(),
                "name":         name,
                "birthdate":    birthdate_s,
                "concern":      concern,
                "fortune_data": fortune_data,
                "reading":      full_text,
            }, ensure_ascii=False, indent=2).encode("utf-8"))

            # 受注データを「完了」に更新
            updated = load_orders()
            for o in updated:
                if o["id"] == order_id:
                    o["status"]          = "完了"
                    o["fortune_file_id"] = fid
                    o["reading"]         = full_text
                    o["fortune_data"]    = fortune_data
            save_orders(updated)

            yield sse_bytes({"done": True, "file_id": fid, "fortune_data": fortune_data, "reading": full_text})

        except Exception as e:
            err_orders = load_orders()
            for o in err_orders:
                if o["id"] == order_id:
                    o["status"] = "未対応"
            save_orders(err_orders)
            yield sse_bytes({"error": safe_str(e)})

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/coconala/bulk-fortune", methods=["POST"])
def bulk_coconala_fortune():
    orders  = load_orders()
    pending = [o for o in orders if o["status"] == "未対応"]

    if not pending:
        return json_resp({"error": "no_pending_orders"}, 400)

    def generate():
        total     = len(pending)
        completed = 0

        yield sse_bytes({"status": "start", "total": total})

        for order in pending:
            order_id    = order["id"]
            name        = str(order.get("name") or "")
            birthdate_s = str(order.get("birthdate") or "")
            concern     = str(order.get("concern") or "")

            yield sse_bytes({
                "status":    "processing",
                "order_id":  order_id,
                "name":      name,
                "completed": completed,
                "total":     total,
            })

            try:
                bd           = datetime.datetime.strptime(birthdate_s, "%Y-%m-%d")
                fortune_data = calculate_all(bd.year, bd.month, bd.day)
                prompt       = format_for_prompt(fortune_data, concern, name)

                cur = load_orders()
                for o in cur:
                    if o["id"] == order_id:
                        o["status"] = "鑑定中"
                save_orders(cur)

                full_text = ""
                with get_client().messages.stream(
                    model="claude-opus-4-6",
                    max_tokens=16384,
                    system=FORTUNE_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt}],
                ) as stream:
                    for chunk in stream.text_stream:
                        full_text += chunk

                ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                fid  = f"fortune_{ts}"
                path = RESULTS_DIR / f"{fid}.json"
                path.write_bytes(json.dumps({
                    "timestamp":    datetime.datetime.now().isoformat(),
                    "name":         name,
                    "birthdate":    birthdate_s,
                    "concern":      concern,
                    "fortune_data": fortune_data,
                    "reading":      full_text,
                }, ensure_ascii=False, indent=2).encode("utf-8"))

                cur = load_orders()
                for o in cur:
                    if o["id"] == order_id:
                        o["status"]          = "完了"
                        o["fortune_file_id"] = fid
                        o["reading"]         = full_text
                        o["fortune_data"]    = fortune_data
                save_orders(cur)

                completed += 1
                yield sse_bytes({
                    "status":    "done_one",
                    "order_id":  order_id,
                    "completed": completed,
                    "total":     total,
                })

            except Exception as e:
                cur = load_orders()
                for o in cur:
                    if o["id"] == order_id:
                        o["status"] = "未対応"
                save_orders(cur)
                yield sse_bytes({
                    "status":    "error_one",
                    "order_id":  order_id,
                    "error":     safe_str(e),
                    "completed": completed,
                    "total":     total,
                })

        yield sse_bytes({"status": "all_done", "completed": completed, "total": total})

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---- チャット（追加質問） ----

@app.route("/api/chat", methods=["POST"])
def chat():
    body    = request.get_json(force=True, silent=True) or {}
    ctx     = body.get("fortune_context") or {}
    messages= body.get("messages") or []

    concern  = str(ctx.get("concern") or "")
    reading  = str(ctx.get("reading") or "")
    today    = datetime.date.today()
    today_str = f"{today.year}年{today.month}月{today.day}日"

    # システムプロンプトに含める鑑定文は最大3000文字に制限
    # （全文を入れるとリクエストが巨大になりタイムアウトの原因になるため）
    reading_excerpt = reading[:3000] + "…（以下省略）" if len(reading) > 3000 else reading

    system = (
        FORTUNE_SYSTEM_PROMPT
        + f"\n\n今日の日付: {today_str}\n\n"
        + "先ほど以下の鑑定を行いました。この内容をふまえて、お客様の追加質問に丁寧に答えてください。\n"
        + "追加質問への回答は簡潔にまとめ、必要十分な内容で答えてください。\n\n"
        + f"【相談内容】\n{concern}\n\n【鑑定結果（抜粋）】\n{reading_excerpt}"
    )

    # messages の整合性チェック：先頭がuserでない・連続するroleがあれば修正
    valid_messages: list = []
    for msg in messages:
        role    = msg.get("role", "")
        content = str(msg.get("content") or "")
        if role not in ("user", "assistant"):
            continue
        if valid_messages and valid_messages[-1]["role"] == role:
            # 同じroleが連続している場合は内容をマージ
            valid_messages[-1]["content"] += "\n" + content
        else:
            valid_messages.append({"role": role, "content": content})

    # 最後のメッセージがuserでなければ追加質問として処理できないためエラー
    if not valid_messages or valid_messages[-1]["role"] != "user":
        return json_resp({"error": "invalid_message_order"}, 400)

    def generate():
        try:
            yield sse_bytes({"status": "connecting"})
            with get_client().messages.stream(
                model="claude-opus-4-6",
                max_tokens=8192,           # 4096 → 8192 に拡張（回答が途中で切れる問題を防止）
                system=system,
                messages=valid_messages,
            ) as stream:
                for chunk in stream.text_stream:
                    yield sse_bytes({"chunk": chunk})
            yield sse_bytes({"done": True})
        except Exception as e:
            try:
                yield sse_bytes({"error": safe_str(e)})
            except Exception:
                pass

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---- 全履歴管理 ----

@app.route("/history")
def history_page():
    return render_template("history.html")


@app.route("/api/history")
def get_history_api():
    history = load_history_data()
    name_q = (request.args.get("name") or "").strip().lower()
    date_q = (request.args.get("date") or "").strip()

    filtered = history
    if name_q:
        filtered = [h for h in filtered if name_q in (h.get("name") or "").lower()]
    if date_q:
        filtered = [h for h in filtered if (h.get("timestamp") or "").startswith(date_q)]

    filtered = list(reversed(filtered))

    # 一覧では result（長文）を除外して軽量化
    result = []
    for h in filtered:
        row = {k: v for k, v in h.items() if k not in ("result", "compatibility_result")}
        row["has_detail"] = bool(h.get("detailed_questions"))
        row["has_result"] = bool(h.get("result"))
        result.append(row)

    return Response(response=_safe_dumps(result), content_type="application/json; charset=utf-8")


@app.route("/api/history/<int:history_id>")
def get_history_entry(history_id):
    history = load_history_data()
    entry = next((h for h in history if h.get("id") == history_id), None)
    if not entry:
        return json_resp({"error": "not_found"}, 404)
    return Response(response=_safe_dumps(entry), content_type="application/json; charset=utf-8")


@app.route("/api/history/export/csv")
def export_history_csv():
    import csv
    import io

    history = load_history_data()
    max_q = max((len(h.get("detailed_questions") or []) for h in history), default=0)

    output = io.StringIO()
    writer = csv.writer(output)

    headers = ["ID", "日時", "名前", "生年月日", "相談内容", "相手の生年月日", "関係性"]
    for i in range(max_q):
        headers += [f"質問{i + 1}", f"回答{i + 1}"]
    headers += ["鑑定結果", "相性診断結果"]
    writer.writerow(headers)

    for h in history:
        qs  = h.get("detailed_questions") or []
        ans = h.get("detailed_answers") or []
        row = [
            h.get("id", ""),
            (h.get("timestamp") or "")[:16].replace("T", " "),
            h.get("name", ""),
            h.get("birthdate", ""),
            h.get("consultation", ""),
            h.get("partner_birthdate", ""),
            h.get("relationship", ""),
        ]
        for i in range(max_q):
            row.append(qs[i] if i < len(qs) else "")
            row.append(ans[i] if i < len(ans) else "")
        row += [h.get("result", ""), h.get("compatibility_result", "")]
        writer.writerow(row)

    csv_bytes = output.getvalue().encode("utf-8-sig")
    return Response(
        response=csv_bytes,
        content_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": "attachment; filename=fortune_history.csv"},
    )


@app.route("/api/history/<int:history_id>/chat", methods=["PATCH"])
def update_history_chat(history_id):
    body          = request.get_json(force=True, silent=True) or {}
    chat_messages = body.get("chat_messages") or []

    sb = get_supabase()
    if sb:
        try:
            sb.table("history").update({"chat_messages": chat_messages}).eq("id", history_id).execute()
            return json_resp({"success": True})
        except Exception as e:
            return json_resp({"error": safe_str(e)}, 500)

    history = load_history_data()
    for h in history:
        if h.get("id") == history_id:
            h["chat_messages"] = chat_messages
            HISTORY_FILE.write_bytes(
                json.dumps(history, ensure_ascii=False, indent=2).encode("utf-8")
            )
            return json_resp({"success": True})
    return json_resp({"error": "not_found"}, 404)


@app.route("/api/history/<int:history_id>/download")
def download_history_entry(history_id):
    import io as _io
    history = load_history_data()
    entry = next((h for h in history if h.get("id") == history_id), None)
    if not entry:
        return json_resp({"error": "not_found"}, 404)

    qs  = entry.get("detailed_questions") or []
    ans = entry.get("detailed_answers") or []

    lines = [
        "=" * 50,
        "Fortune Reading",
        "=" * 50,
        "Date: " + (entry.get("timestamp") or "")[:16].replace("T", " "),
        "Name: " + entry.get("name", ""),
        "Birthdate: " + entry.get("birthdate", ""),
        "Consultation: " + entry.get("consultation", ""),
    ]
    if qs:
        lines += ["", "[Detailed Q&A]"]
        for i, q in enumerate(qs):
            lines.append(f"Q{i + 1}: {q}")
            lines.append(f"A{i + 1}: {ans[i] if i < len(ans) else ''}")
    lines += ["", "[Reading]", entry.get("result", ""), "", "=" * 50]

    content = "\n".join(lines).encode("utf-8")
    return send_file(
        _io.BytesIO(content),
        as_attachment=True,
        download_name=f"fortune_{entry.get('birthdate', 'unknown')}.txt",
        mimetype="text/plain; charset=utf-8",
    )


# ======================================================
# ---- note 自動投稿機能 ----
# ======================================================

AUTO_POST_DIR         = Path("auto_post")
AUTO_POST_DIR.mkdir(exist_ok=True)
(AUTO_POST_DIR / "drafts").mkdir(exist_ok=True)
AUTO_POST_CONFIG_FILE = AUTO_POST_DIR / "config.json"
AUTO_POST_HISTORY_FILE = AUTO_POST_DIR / "history.json"

_AP_DEFAULTS = {
    "enabled":       False,
    "post_time":     "09:00",
    "coconala_url":  "",
    "note_url":      "",
    "note_status":   "draft",
    "content_today": True,
    "content_voice": True,
    "last_post_date": None,
}


def load_ap_config():
    if not AUTO_POST_CONFIG_FILE.exists():
        return dict(_AP_DEFAULTS)
    try:
        return {**_AP_DEFAULTS, **json.loads(AUTO_POST_CONFIG_FILE.read_bytes())}
    except Exception:
        return dict(_AP_DEFAULTS)


def save_ap_config(cfg):
    AUTO_POST_CONFIG_FILE.write_bytes(
        json.dumps(cfg, ensure_ascii=False, indent=2).encode("utf-8")
    )


def load_ap_history():
    if not AUTO_POST_HISTORY_FILE.exists():
        return []
    try:
        return json.loads(AUTO_POST_HISTORY_FILE.read_bytes())
    except Exception:
        return []


def save_ap_history(h):
    AUTO_POST_HISTORY_FILE.write_bytes(
        json.dumps(h, ensure_ascii=False, indent=2).encode("utf-8")
    )


# ---- note.com API ----

def note_login(email: str, password: str) -> str:
    """note.com にログインしてセッショントークンを返す"""
    r = http_requests.post(
        "https://note.com/api/v1/auth/sign_in",
        json={"login": email, "password": password},
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    token = (
        data.get("token")
        or data.get("data", {}).get("token")
        or data.get("user", {}).get("token")
    )
    if not token:
        raise ValueError(f"トークン取得失敗: {json.dumps(data, ensure_ascii=False)[:200]}")
    return token


def note_create_article(token: str, title: str, body: str, status: str = "draft") -> dict:
    """note.com に記事を作成する"""
    r = http_requests.post(
        "https://note.com/api/v3/notes",
        headers={
            "Token": token,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
        json={"kind": "text_note", "status": status, "name": title, "body": body},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


# ---- コンテンツ生成 ----

def _day_numerology(dt: datetime.datetime) -> int:
    n = sum(int(d) for d in dt.strftime("%Y%m%d"))
    while n > 9 and n not in (11, 22, 33):
        n = sum(int(d) for d in str(n))
    return n


def build_daily_fortune_prompt(coconala_url: str) -> str:
    from fortune.calculator import calculate_all
    now = datetime.datetime.now()
    wd  = ["月", "火", "水", "木", "金", "土", "日"][now.weekday()]
    fd  = calculate_all(now.year, now.month, now.day)
    day_pillar  = fd["shichusuimei"]["day_pillar"]["pillar"]
    day_element = fd["shichusuimei"]["day_pillar"].get("element", "")
    day_num     = _day_numerology(now)
    date_str    = f"{now.year}年{now.month}月{now.day}日（{wd}）"

    return f"""今日は{date_str}です。
今日の日柱は「{day_pillar}」（{day_element}）、数秘は{day_num}です。

以下の形式でnote.com向け「12星座別おみくじ運勢」記事を書いてください。

タイトル（1行目）:
【{now.year}年{now.month}月{now.day}日】今日の12星座おみくじ運勢🔮〜四柱推命×数秘術で読み解く天命〜

本文:
- 冒頭3〜4行：今日のエネルギー（日柱・数秘をもとに）
- 各星座の運勢（各2〜3行、ラッキーアドバイス付き）：
  ⭐ おひつじ座（3/21〜4/19）
  ♉ おうし座（4/20〜5/20）
  ♊ ふたご座（5/21〜6/21）
  ♋ かに座（6/22〜7/22）
  ♌ しし座（7/23〜8/22）
  ♍ おとめ座（8/23〜9/22）
  ♎ てんびん座（9/23〜10/23）
  ♏ さそり座（10/24〜11/22）
  ♐ いて座（11/23〜12/21）
  ♑ やぎ座（12/22〜1/19）
  ♒ みずがめ座（1/20〜2/18）
  ♓ うお座（2/19〜3/20）
- 締め：個人鑑定への誘導
  「より詳しいあなただけの天命鑑定はこちら → {coconala_url or '（URLを設定してください）'}」
- 温かく親しみやすい日本語・絵文字適度に使用
- Markdownの##や**は使わない
"""


def build_customer_voice_prompt(coconala_url: str) -> str:
    theme = random.choice(["仕事・転職", "恋愛・結婚", "人間関係", "将来・人生の方向性"])
    return f"""占い師のnote.com向け「お客様の声」記事を日本語で書いてください。

テーマ：{theme}
・架空のお客様（匿名）の体験談として、リアリティのある内容で
・800〜1200文字程度

タイトル（1行目）:
【お客様の声】{theme}でお悩みだった方の鑑定体験談✨

本文の構成：
1. 冒頭の挨拶（占い師として）
2. お客様のプロフィール（例：30代女性、具体的だが匿名）
3. 鑑定前のお悩み（具体的・リアルに）
4. 鑑定を通じた気づき（四柱推命/数秘術/動物占いの視点）
5. 鑑定後の変化・感想（前向きな変化を具体的に）
6. 締め：読者への呼びかけ＋ococoナラURL
   「あなたも天命鑑定を受けてみませんか → {coconala_url or '（URLを設定してください）'}」

- 温かく共感的な日本語
- 過度な宣伝感は避けて自然な口コミ風に
- Markdownの##や**は使わない
"""


def _save_draft_and_history(ctype, title, body, post_status, note_url=""):
    ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    fid  = f"draft_{ctype}_{ts}"
    (AUTO_POST_DIR / "drafts" / f"{fid}.json").write_bytes(
        json.dumps({"id": fid, "type": ctype, "title": title, "body": body,
                    "created_at": datetime.datetime.now().isoformat()},
                   ensure_ascii=False, indent=2).encode("utf-8")
    )
    hist = load_ap_history()
    hist.insert(0, {"id": fid, "type": ctype, "title": title, "status": post_status,
                    "note_url": note_url, "created_at": datetime.datetime.now().isoformat()})
    save_ap_history(hist[:50])
    return fid


def run_auto_post_now(cfg: dict) -> list:
    """自動投稿を実行して結果リストを返す"""
    email        = os.environ.get("NOTE_EMAIL", "")
    password     = os.environ.get("NOTE_PASSWORD", "")
    coconala_url = cfg.get("coconala_url", "")
    note_status  = cfg.get("note_status", "draft")

    # note ログイン
    token = None
    login_error = ""
    if email and password:
        try:
            token = note_login(email, password)
        except Exception as e:
            login_error = safe_str(e)

    content_types = []
    if cfg.get("content_today"): content_types.append("daily_fortune")
    if cfg.get("content_voice"):  content_types.append("customer_voice")

    results = []
    for ctype in content_types:
        try:
            prompt = (build_daily_fortune_prompt(coconala_url)
                      if ctype == "daily_fortune"
                      else build_customer_voice_prompt(coconala_url))

            full_text = ""
            with get_client().messages.stream(
                model="claude-opus-4-6", max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                for chunk in stream.text_stream:
                    full_text += chunk

            lines   = full_text.strip().split("\n")
            title   = lines[0].strip() if lines else "無題"
            body_t  = "\n".join(lines[1:]).strip() if len(lines) > 1 else full_text

            note_url    = ""
            post_status = "draft_saved"

            if token:
                try:
                    res      = note_create_article(token, title, body_t, note_status)
                    note_url = (res.get("data", {}).get("noteUrl")
                                or res.get("noteUrl", ""))
                    post_status = "posted"
                except Exception as e:
                    post_status = f"post_failed:{safe_str(e)}"
            else:
                post_status = f"no_token:{login_error or 'credentials not set'}"

            fid = _save_draft_and_history(ctype, title, body_t, post_status, note_url)
            results.append({"type": ctype, "title": title, "status": post_status,
                             "note_url": note_url, "draft_id": fid})

        except Exception as e:
            results.append({"type": ctype, "status": f"error:{safe_str(e)}"})

    return results


# ---- バックグラウンドスケジューラー ----

_ap_scheduler_started = False


def _start_ap_scheduler():
    global _ap_scheduler_started
    if _ap_scheduler_started:
        return
    _ap_scheduler_started = True

    def loop():
        while True:
            try:
                cfg = load_ap_config()
                if cfg.get("enabled"):
                    now  = datetime.datetime.now()
                    pt   = cfg.get("post_time", "09:00")
                    ph, pm = map(int, pt.split(":"))
                    today  = now.strftime("%Y-%m-%d")
                    if now.hour == ph and now.minute == pm and cfg.get("last_post_date") != today:
                        run_auto_post_now(cfg)
                        cfg["last_post_date"] = today
                        save_ap_config(cfg)
            except Exception:
                pass
            time.sleep(60)

    threading.Thread(target=loop, daemon=True).start()


_start_ap_scheduler()


# ---- ルーティング ----

@app.route("/auto-post")
def auto_post_page():
    return render_template("auto_post.html")


@app.route("/api/auto-post/config", methods=["GET"])
def ap_get_config():
    cfg = load_ap_config()
    cfg["note_email_set"]    = bool(os.environ.get("NOTE_EMAIL"))
    cfg["note_password_set"] = bool(os.environ.get("NOTE_PASSWORD"))
    return Response(response=_safe_dumps(cfg), content_type="application/json; charset=utf-8")


@app.route("/api/auto-post/config", methods=["POST"])
def ap_save_config():
    body = request.get_json(force=True, silent=True) or {}
    cfg  = load_ap_config()
    for k in ("enabled", "post_time", "coconala_url", "note_url",
              "note_status", "content_today", "content_voice"):
        if k in body:
            cfg[k] = body[k]
    save_ap_config(cfg)
    return json_resp({"success": True})


@app.route("/api/auto-post/generate", methods=["POST"])
def ap_generate():
    body         = request.get_json(force=True, silent=True) or {}
    ctype        = str(body.get("type") or "daily_fortune")
    coconala_url = load_ap_config().get("coconala_url", "")

    prompt = (build_daily_fortune_prompt(coconala_url)
              if ctype == "daily_fortune"
              else build_customer_voice_prompt(coconala_url))

    def generate():
        try:
            yield sse_bytes({"status": "connecting"})
            full_text = ""
            with get_client().messages.stream(
                model="claude-opus-4-6", max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                for chunk in stream.text_stream:
                    full_text += chunk
                    yield sse_bytes({"chunk": chunk})

            lines  = full_text.strip().split("\n")
            title  = lines[0].strip() if lines else "無題"
            body_t = "\n".join(lines[1:]).strip() if len(lines) > 1 else full_text
            fid    = _save_draft_and_history(ctype, title, body_t, "draft_generated")

            yield sse_bytes({"done": True, "draft_id": fid,
                             "title": title, "body": body_t})
        except Exception as e:
            yield sse_bytes({"error": safe_str(e)})

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/auto-post/post-note", methods=["POST"])
def ap_post_note():
    body    = request.get_json(force=True, silent=True) or {}
    title   = str(body.get("title") or "")
    body_t  = str(body.get("body") or "")
    ctype   = str(body.get("type") or "daily_fortune")

    if not title or not body_t:
        return json_resp({"error": "missing_content"}, 400)

    cfg      = load_ap_config()
    email    = os.environ.get("NOTE_EMAIL", "")
    password = os.environ.get("NOTE_PASSWORD", "")
    status   = cfg.get("note_status", "draft")

    if not email or not password:
        fid = _save_draft_and_history(ctype, title, body_t, "draft_saved_no_credentials")
        return json_resp({"success": False,
                          "message": "NOTE_EMAIL / NOTE_PASSWORD が未設定のためローカル保存しました",
                          "draft_id": fid})

    try:
        token    = note_login(email, password)
        res      = note_create_article(token, title, body_t, status)
        note_url = res.get("data", {}).get("noteUrl") or res.get("noteUrl", "")
        fid      = _save_draft_and_history(ctype, title, body_t, "posted", note_url)
        return json_resp({"success": True, "note_url": note_url,
                          "status": status, "draft_id": fid})
    except Exception as e:
        return json_resp({"error": safe_str(e)}, 500)


@app.route("/api/auto-post/run-now", methods=["POST"])
def ap_run_now():
    cfg = load_ap_config()
    try:
        results = run_auto_post_now(cfg)
        cfg["last_post_date"] = datetime.datetime.now().strftime("%Y-%m-%d")
        save_ap_config(cfg)
        return json_resp({"success": True, "results": results})
    except Exception as e:
        return json_resp({"error": safe_str(e)}, 500)


@app.route("/api/auto-post/history")
def ap_history():
    return Response(
        response=_safe_dumps(load_ap_history()),
        content_type="application/json; charset=utf-8",
    )


@app.route("/api/auto-post/history/<draft_id>", methods=["DELETE"])
def ap_delete_history(draft_id):
    hist = [h for h in load_ap_history() if h.get("id") != draft_id]
    save_ap_history(hist)
    draft_path = AUTO_POST_DIR / "drafts" / f"{draft_id}.json"
    if draft_path.exists():
        draft_path.unlink()
    return json_resp({"success": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
