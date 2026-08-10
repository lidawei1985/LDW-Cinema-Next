"""片源校验：可达性 + 结构 + 抽样探测，输出 0-100 健康分。"""
from __future__ import annotations
import json
import time
import urllib.request
import urllib.error
from .models import Source


def _http_get(url: str, timeout: int, headers=None) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "LDW-Cinema-Next/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, (e.read() if hasattr(e, "read") else b"")
    except Exception as e:  # noqa: BLE001
        return -1, str(e).encode("utf-8")


def _looks_json(body: bytes) -> bool:
    try:
        json.loads(body.decode("utf-8", "ignore"))
        return True
    except Exception:  # noqa: BLE001
        return False


def validate_source(src: Source, cfg: dict) -> Source:
    """就地更新 src.health / detail。"""
    v = cfg.get("validation", {})
    timeout = cfg.get("aggregator", {}).get("timeoutSeconds", 12)
    t0 = time.time()
    score = 0.0
    parts = []

    # 1) 可达性 + 结构 (40)
    if not src.api:
        src.detail = "缺少 api 地址"
        src.health, src.lastChecked = 0.0, t0
        return src
    status, body = _http_get(src.api, timeout)
    if status == 200 and _looks_json(body):
        score += 40
        parts.append("可达+JSON")
    elif status == 200:
        score += 20
        parts.append("可达(非JSON)")
    elif status > 0:
        parts.append(f"HTTP {status}")
    else:
        parts.append("不可达")

    # 2) 搜索探测 (25)
    if v.get("probeSearch") and src.searchable and score > 0:
        q = v.get("probeSearchQuery", "test")
        probe = f"{src.api}?wd={urllib.parse.quote(q)}" if "?" not in src.api else f"{src.api}&wd={urllib.parse.quote(q)}"
        s2, b2 = _http_get(probe, timeout)
        if s2 == 200 and _looks_json(b2):
            try:
                j = json.loads(b2.decode("utf-8", "ignore"))
                if isinstance(j, dict) and (j.get("list") or j.get("data") or j.get("items")):
                    score += 25
                    parts.append("搜索OK")
                else:
                    score += 10
                    parts.append("搜索空")
            except Exception:  # noqa: BLE001
                score += 10
                parts.append("搜索异形")
        else:
            parts.append("搜索失败")

    # 3) 结构完整性 (20)
    if src.name and src.key and src.type:
        score += 20
        parts.append("结构完整")

    # 4) 可播放标记 (15)
    if src.playable:
        score += 15
        parts.append("可播放")

    score = min(100.0, score)
    src.health = round(score, 1)
    src.lastChecked = t0
    src.detail = " | ".join(parts)
    return src
