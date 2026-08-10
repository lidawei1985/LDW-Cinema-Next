"""聚合上游 spider 配置，归一化为 Source / LiveSource。

上游可以是：
  - 一个站点数组 [...]
  - 一个 { "sites":[...], "lives":[...] } 清单
所有上游失败时，按配置回退到 samples（保证系统可冷启动）。
"""
from __future__ import annotations
import json
import os
import urllib.request
import urllib.error
from .models import Source, LiveSource

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))


def _http_get_json(url: str, timeout: int):
    req = urllib.request.Request(url, headers={"User-Agent": "LDW-Cinema-Next/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:  # noqa: BLE001
        return -1, None


def _norm_source(d: dict, origin: str) -> Source:
    return Source(
        key=str(d.get("key") or d.get("id") or ""),
        name=str(d.get("name") or d.get("key") or ""),
        api=str(d.get("api") or d.get("url") or ""),
        type=str(d.get("type") or "normal"),
        searchable=int(d.get("searchable", 1) or 0),
        playable=int(d.get("playable", 1) or 0),
        ext=str(d.get("ext") or ""),
        group=str(d.get("group") or "默认"),
        posterProxy=str(d.get("proxy") or d.get("posterProxy") or ""),
        origin=origin,
    )


def _norm_live(d: dict, origin: str) -> LiveSource:
    return LiveSource(
        key=str(d.get("key") or d.get("id") or d.get("name") or ""),
        name=str(d.get("name") or ""),
        url=str(d.get("url") or d.get("api") or ""),
        type=str(d.get("type") or d.get("kind") or "auto"),
        group=str(d.get("group") or "直播"),
        origin=origin,
    )


def _ingest(obj, origin: str, sources: list, lives: list):
    if isinstance(obj, list):
        for d in obj:
            if isinstance(d, dict):
                if d.get("api") or d.get("url"):
                    sources.append(_norm_source(d, origin))
                elif d.get("url") and (d.get("type") in ("m3u", "live") or d.get("channels") is not None):
                    lives.append(_norm_live(d, origin))
    elif isinstance(obj, dict):
        for d in obj.get("sites", []) or []:
            sources.append(_norm_source(d, origin))
        for d in obj.get("lives", []) or []:
            lives.append(_norm_live(d, origin))


def aggregate(cfg: dict):
    agg = cfg.get("aggregator", {})
    timeout = agg.get("timeoutSeconds", 12)
    sources: list[Source] = []
    lives: list[LiveSource] = []
    used = []

    for up in agg.get("upstreams", []) or []:
        status, obj = _http_get_json(up, timeout)
        if status == 200 and obj:
            _ingest(obj, up, sources, lives)
            used.append(up)
        else:
            print(f"[aggregator] 上游不可用 {up} -> HTTP {status}")

    if not used and agg.get("allowSamplesWhenAllUpstreamsFail"):
        sp = agg.get("samplesFallback") or "samples/sample_sources.json"
        path = sp if os.path.isabs(sp) else os.path.join(_ROOT, sp)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    obj = json.load(f)
                _ingest(obj, "samples", sources, lives)
                used.append("samples:" + path)
                print(f"[aggregator] 回退到 samples: {path}")
            except Exception as e:  # noqa: BLE001
                print(f"[aggregator] samples 读取失败: {e}")

    # 去重（按 key）
    seen = set()
    uniq_s = []
    for s in sources:
        if s.key and s.key not in seen:
            seen.add(s.key)
            uniq_s.append(s)
    seen_l = set()
    uniq_l = []
    for l in lives:
        if l.key and l.key not in seen_l:
            seen_l.add(l.key)
            uniq_l.append(l)

    cap = agg.get("maxSources", 60)
    return uniq_s[:cap], uniq_l, used
