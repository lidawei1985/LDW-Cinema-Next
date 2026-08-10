"""最小化 HTTP API：提供片源 JSON、健康检查、人工确认闸。"""
from __future__ import annotations
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from . import approval as approval_mod

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))

PIPELINE = None  # 由 serve() 注入，模块级避免被当作绑定方法


def _read(p: str) -> bytes | None:
    full = p if os.path.isabs(p) else os.path.join(_ROOT, p)
    if os.path.exists(full):
        with open(full, "r", encoding="utf-8") as f:
            return f.read().encode("utf-8")
    return None


def _json_body(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    pipeline = None  # 由 main 注入

    def _send(self, code: int, body: bytes, ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        path = u.path
        if path in ("/combined.json",):
            b = _read("dist/combined.json") or _json_body({"sites": [], "lives": []})
            self._send(200, b)
        elif path in ("/live.json",):
            b = _read("dist/live.json") or _json_body({"lives": []})
            self._send(200, b)
        elif path in ("/health",):
            b = _read("state/health.json") or _json_body({"summary": "尚未运行"})
            self._send(200, b)
        elif path in ("/pending",):
            self._send(200, _json_body(approval_mod.load_pending()))
        elif path in ("/", "/index.html"):
            self._send(200, self._index(), "text/html; charset=utf-8")
        else:
            self._send(404, _json_body({"error": "not found"}))

    def do_POST(self):
        u = urlparse(self.path)
        qs = parse_qs(u.query)
        fp = (qs.get("fp") or [""])[0]
        if u.path == "/approve" and fp:
            approval_mod.approve(fp)
            self._send(200, _json_body({"ok": True, "approved": fp}))
        elif u.path == "/quarantine" and fp:
            approval_mod.quarantine(fp)
            self._send(200, _json_body({"ok": True, "quarantined": fp}))
        elif u.path == "/trigger" and PIPELINE:
            try:
                combined = PIPELINE()
                self._send(200, _json_body({"ok": True, "sites": len(combined.get("sites", [])),
                                            "lives": len(combined.get("lives", []))}))
            except Exception as e:  # noqa: BLE001
                self._send(500, _json_body({"ok": False, "error": str(e)}))
        else:
            self._send(400, _json_body({"error": "bad request"}))

    def _index(self) -> bytes:
        health = _read("state/health.json") or b"{}"
        try:
            h = json.loads(health)
            summary = h.get("summary", "尚未运行")
        except Exception:  # noqa: BLE001
            summary = "尚未运行"
        return f"""<html><head><meta charset=utf-8><title>LDW-Cinema-Next 片源管家</title>
<style>body{{font-family:system-ui;background:#0f1115;color:#e6e6e6;padding:24px}}
h1{{color:#4cc2ff}} code{{background:#1c2130;padding:2px 6px;border-radius:4px}}</style></head>
<body><h1>LDW-Cinema-Next · 自维护片源 API</h1>
<p>状态：<b>{summary}</b></p>
<ul>
<li><a style="color:#4cc2ff" href="/combined.json">/combined.json</a> — 点播+直播合并清单（App 直接拉取）</li>
<li><a style="color:#4cc2ff" href="/live.json">/live.json</a> — 直播源清单</li>
<li><a style="color:#4cc2ff" href="/health">/health</a> — 健康分报告</li>
<li><a style="color:#4cc2ff" href="/pending">/pending</a> — 待人工确认源</li>
</ul>
<p>人工确认：<code>POST /approve?fp=指纹</code> · <code>POST /quarantine?fp=指纹</code> · <code>POST /trigger</code> 立即重跑</p>
</body></html>""".encode("utf-8")

    def log_message(self, *a):  # 静默默认日志
        pass


def serve(cfg: dict, pipeline):
    global PIPELINE
    PIPELINE = pipeline
    host = cfg.get("api", {}).get("host", "0.0.0.0")
    port = int(os.environ.get("LDW_API_PORT", cfg.get("api", {}).get("port", 8787)))
    httpd = HTTPServer((host, port), Handler)
    print(f"[api] 片源管家已启动 http://{host}:{port}")
    httpd.serve_forever()
