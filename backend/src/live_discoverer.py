"""直播源自动发现与维护（规格 4）。

支持 m3u 与 json 两类直播源；解析频道数、抽样探测可达性，输出健康分。
"""
from __future__ import annotations
import json
import time
import urllib.request
import urllib.error
from .models import LiveSource


def _http_get(url: str, timeout: int):
    req = urllib.request.Request(url, headers={"User-Agent": "LDW-Cinema-Next/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, (e.read() if hasattr(e, "read") else b"")
    except Exception as e:  # noqa: BLE001
        return -1, str(e).encode("utf-8")


def _parse_m3u(text: str):
    channels = []
    for line in text.splitlines():
        if line.startswith("#EXTINF"):
            # #EXTINF:-1 tvg-logo="..." ,名称
            name = line.split(",", 1)[-1].strip() if "," in line else line
            channels.append(name)
    return channels


def discover(live: LiveSource, cfg: dict) -> LiveSource:
    lc = cfg.get("liveDiscovery", {})
    timeout = lc.get("timeoutSeconds", 12)
    max_probe = lc.get("maxChannelsProbe", 3)
    t0 = time.time()
    score = 0.0
    parts = []

    status, body = _http_get(live.url, timeout)
    if status != 200:
        live.detail = f"HTTP {status}" if status > 0 else "不可达"
        live.health, live.lastChecked = 0.0, t0
        return live

    text = body.decode("utf-8", "ignore")
    if live.type == "m3u" or (live.type == "auto" and "#EXTM3U" in text):
        live.type = "m3u"
        chs = _parse_m3u(text)
        live.channelCount = len(chs)
        if live.channelCount > 0:
            score += 50
            parts.append(f"频道{live.channelCount}")
            # 抽样探测（从文本里取前几个 http 链接做 HEAD）
            urls = [u for u in text.split() if u.startswith("http")][:max_probe]
            ok = 0
            for u in urls:
                s, _ = _http_get(u, timeout)
                if s == 200 or s == 302 or s == 206:
                    ok += 1
            if urls:
                score += 30 * (ok / len(urls))
                parts.append(f"探测{ok}/{len(urls)}")
        else:
            parts.append("空m3u")
    else:
        # JSON 直播源
        try:
            j = json.loads(text)
            chs = j.get("channels") or j.get("list") or []
            live.channelCount = len(chs) if isinstance(chs, list) else 0
            score += 50 if live.channelCount > 0 else 10
            parts.append(f"JSON频道{live.channelCount}")
        except Exception:  # noqa: BLE001
            parts.append("JSON解析失败")

    score += 20  # 基础可用
    live.health = round(min(100.0, score), 1)
    live.lastChecked = t0
    live.detail = " | ".join(parts)
    return live
