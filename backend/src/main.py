"""LDW-Cinema-Next 后端编排器（规格 4/5）。

用法：
  python -m src.main --once        仅跑一次流水线并退出
  python -m src.main --serve       仅启动 HTTP API
  python -m src.main               默认：启动 API + 定时调度（按 config.schedule）
"""
from __future__ import annotations
import json
import os
import sys
import time
import threading

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
sys.path.insert(0, _ROOT)

from src import aggregator, validator, live_discoverer, merger, approval as approval_mod  # noqa: E402


def load_config() -> dict:
    path = os.path.join(_ROOT, "config.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_once(cfg: dict) -> dict:
    print("[pipeline] 聚合上游片源 ...")
    sources, lives, used = aggregator.aggregate(cfg)
    used_samples = any(u.startswith("samples:") for u in used)
    print(f"[pipeline] 聚合到片源 {len(sources)} 个，直播源 {len(lives)} 个（来源: {used}）")

    print("[pipeline] 校验片源健康分 ...")
    for s in sources:
        validator.validate_source(s, cfg)

    print("[pipeline] 自动发现/维护直播源 ...")
    for l in lives:
        live_discoverer.discover(l, cfg)

    # 人工确认闸
    active, pending = approval_mod.gate(sources, cfg)
    if pending:
        print(f"[pipeline] {len(pending)} 个新源待人工确认（已写入 pending/）")

    # 冷启动兜底：上游全失败时，samples 一律纳入（curated），健康分仅作展示
    bootstrap = cfg.get("output", {}).get("bootstrapIncludeSamples", True)
    boot = bool(used_samples and bootstrap)
    if boot:
        active = sources
        print("[pipeline] 冷启动兜底：samples 全部纳入 combined.json（健康分仅展示）")

    combined = merger.merge(
        active, lives, cfg,
        min_v=0 if boot else None,
        min_l=0 if boot else None,
    )
    print(f"[pipeline] 已生成 {cfg['output']['combinedFile']}："
          f"片源 {len(combined['sites'])}，直播 {len(combined['lives'])}")
    return combined


def _schedule_loop(cfg: dict):
    interval = cfg.get("schedule", {}).get("intervalHours", 6) * 3600
    while True:
        try:
            run_once(cfg)
        except Exception as e:  # noqa: BLE001
            print(f"[schedule] 运行异常: {e}")
        time.sleep(interval)


def main():
    args = sys.argv[1:]
    cfg = load_config()
    once = "--once" in args
    serve = "--serve" in args or not once

    if once:
        run_once(cfg)
        return

    # 启动 API（后台线程）
    if serve and cfg.get("api", {}).get("enabled", True):
        from src.api_server import serve as api_serve
        t = threading.Thread(target=api_serve, args=(cfg, lambda: run_once(cfg)), daemon=True)
        t.start()

    if cfg.get("schedule", {}).get("enabled", True) and cfg.get("schedule", {}).get("runOnStart", True):
        run_once(cfg)

    if cfg.get("schedule", {}).get("enabled", True):
        _schedule_loop(cfg)
    else:
        # 仅 API 模式：阻塞
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            print("bye")


if __name__ == "__main__":
    main()
