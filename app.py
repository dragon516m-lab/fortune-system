import os
import sys
import json
import logging
import datetime
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
from flask import Flask, render_template, request, Response, send_file
from dotenv import load_dotenv

from fortune.calculator import calculate_all, format_for_prompt

load_dotenv()

app = Flask(__name__)
app.logger.disabled = True

RESULTS_DIR = Path("results")
RESULTS_DIR.mkdir(exist_ok=True)

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


@app.route("/api/fortune", methods=["POST"])
def get_fortune():
    body = request.get_json(force=True, silent=True) or {}

    name        = str(body.get("name") or "")
    birthdate_s = str(body.get("birthdate") or "")
    concern     = str(body.get("concern") or "")

    if not birthdate_s or not concern:
        return json_resp({"error": "missing_params"}, 400)

    try:
        bd = datetime.datetime.strptime(birthdate_s, "%Y-%m-%d")
    except ValueError:
        return json_resp({"error": "invalid_date"}, 400)

    try:
        fortune_data = calculate_all(bd.year, bd.month, bd.day)
        prompt       = format_for_prompt(fortune_data, concern, name)
    except Exception as e:
        return json_resp({"error": safe_str(e)}, 500)

    def generate():
        try:
            yield sse_bytes({"status": "connecting"})

            full_text = ""
            with get_client().messages.stream(
                model="claude-opus-4-6",
                max_tokens=2000,
                system=(
                    "\u3042\u306a\u305f\u306f\u56db\u67f1\u63a8\u547d\u30fb"
                    "\u6570\u79d8\u8853\u30fb\u52d5\u7269\u5360\u3044\u306b"
                    "\u7cbe\u901a\u3057\u305f\u5360\u3044\u5e2b\u3067\u3059\u3002"
                    "\u6e29\u304b\u307f\u306e\u3042\u308b\u65e5\u672c\u8a9e\u3067"
                    "\u3001\u76f8\u8ac7\u8005\u306b\u5bc4\u308a\u6dfb\u3063\u305f"
                    "\u6df1\u307f\u306e\u3042\u308b\u9451\u5b9a\u6587\u3092"
                    "\u66f8\u3044\u3066\u304f\u3060\u3055\u3044\u3002"
                    # Markdown 禁止・見出し形式を指定
                    "##\u3084**\u306a\u3069\u306e\u30de\u30fc\u30af\u30c0\u30a6\u30f3"
                    "\u8a18\u6cd5\u306f\u4e00\u5207\u4f7f\u308f\u306a\u3044\u3067"
                    "\u304f\u3060\u3055\u3044\u3002\u898b\u51fa\u3057\u306f"
                    "\u300a\u3010\u3011\u300b\u3067\u56f2\u3093\u3060\u30d7\u30ec"
                    "\u30fc\u30f3\u30c6\u30ad\u30b9\u30c8\u3060\u3051\u3092\u4f7f"
                    "\u3063\u3066\u304f\u3060\u3055\u3044\u3002"
                ),
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
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
