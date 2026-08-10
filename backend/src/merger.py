"""合并为 combined.json / live.json，并产出健康检查报告。"""
from __future__ import annotations
import json
import os
import time
from datetime import datetime, timezone
from .models import Source, LiveSource, HealthReport

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))


def _iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def merge(sources: list[Source], lives: list[LiveSource], cfg: dict,
          min_v: float | None = None, min_l: float | None = None) -> dict:
    out = cfg.get("output", {})
    app = cfg.get("app", {})
    proxy = out.get("posterProxy", "")
    vcfg = cfg.get("validation", {})
    lcfg = cfg.get("liveDiscovery", {})

    min_v = min_v if min_v is not None else vcfg.get("minHealth", 60)
    min_l = min_l if min_l is not None else lcfg.get("minHealth", 50)

    active_sites = [s for s in sources if s.health >= min_v]
    active_lives = [l for l in lives if l.health >= min_l]

    combined = {
        "spider": "",
        "sites": [s.to_site() for s in active_sites],
        "lives": [l.to_live() for l in active_lives],
        "posterConfig": {
            "proxyUrl": proxy,
            "timeoutMs": 30000,
            "cache": True,
            "concurrency": 8,
        },
        "liveConfig": {
            "autoDiscover": True,
            "autoMaintain": True,
            "minHealth": min_l,
        },
        "version": {
            "versionCode": app.get("versionCode", 1),
            "versionName": app.get("versionName", "0.1.0"),
        },
        "generatedAt": _iso(),
    }

    health = HealthReport()
    health.sources = {s.key: s.health for s in sources}
    health.lives = {l.key: l.health for l in lives}
    dropped = [s.key for s in sources if s.health < min_v] + [l.key for l in lives if l.health < min_l]
    health.summary = (
        f"片源 {len(active_sites)}/{len(sources)} 通过，"
        f"直播 {len(active_lives)}/{len(lives)} 通过"
        + (f"，剔除低健康: {dropped}" if dropped else "")
    )

    dist = out.get("distDir", "dist")
    dist_path = dist if os.path.isabs(dist) else os.path.join(_ROOT, dist)
    os.makedirs(dist_path, exist_ok=True)
    with open(os.path.join(dist_path, out.get("combinedFile", "combined.json")), "w", encoding="utf-8") as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)
    with open(os.path.join(dist_path, out.get("liveFile", "live.json")), "w", encoding="utf-8") as f:
        json.dump({"lives": combined["lives"]}, f, ensure_ascii=False, indent=2)
    with open(os.path.join(_ROOT, out.get("healthFile", "state/health.json")), "w", encoding="utf-8") as f:
        json.dump(health.to_dict(), f, ensure_ascii=False, indent=2)

    return combined
