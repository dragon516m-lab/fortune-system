import os
import re
import sys
import json
import logging
import datetime
import uuid
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

from fortune.calculator import calculate_all, format_for_prompt

load_dotenv()

app = Flask(__name__)
app.logger.disabled = True

RESULTS_DIR = Path("results")
RESULTS_DIR.mkdir(exist_ok=True)

ORDERS_DIR = Path("orders")
ORDERS_DIR.mkdir(exist_ok=True)
ORDERS_FILE = ORDERS_DIR / "coconala_orders.json"


def load_orders():
    if not ORDERS_FILE.exists():
        return []
    return json.loads(ORDERS_FILE.read_bytes())


def save_orders(orders):
    ORDERS_FILE.write_bytes(
        json.dumps(orders, ensure_ascii=False, indent=2).encode("utf-8")
    )


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
        _client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
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
        "箇条書きで出力してください。"
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
            if cleaned and len(cleaned) > 5:
                questions.append(cleaned)

        return json_resp({"questions": questions})
    except Exception as e:
        return json_resp({"error": safe_str(e)}, 500)


@app.route("/api/fortune", methods=["POST"])
def get_fortune():
    body = request.get_json(force=True, silent=True) or {}

    name           = str(body.get("name") or "")
    birthdate_s    = str(body.get("birthdate") or "")
    concern        = str(body.get("concern") or "")
    detail_context = str(body.get("detail_context") or "")

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

            ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            fid  = f"fortune_{ts}"
            path = RESULTS_DIR / f"{fid}.json"
            save = {
                "timestamp":    datetime.datetime.now().isoformat(),
                "name":         name,
                "birthdate":    birthdate_s,
                "concern":      concern,
                "fortune_data": fortune_data,
                "reading":      full_text,
            }
            path.write_bytes(
                json.dumps(save, ensure_ascii=False, indent=2).encode("utf-8")
            )

            yield sse_bytes({"done": True, "file_id": fid, "fortune_data": fortune_data})

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


@app.route("/api/history-list")
def get_history_list():
    items = []
    for p in sorted(RESULTS_DIR.glob("fortune_*.json"), reverse=True)[:20]:
        try:
            data    = json.loads(p.read_bytes())
            concern = str(data.get("concern") or "")
            items.append({
                "file_id":   p.stem,
                "timestamp": str(data.get("timestamp", ""))[:16].replace("T", " "),
                "name":      str(data.get("name") or ""),
                "birthdate": str(data.get("birthdate") or ""),
                "concern":   concern[:30] + "..." if len(concern) > 30 else concern,
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
