"""人工确认闸（规格 5：用户仅在关键节点进行少量确认）。

默认 autoPromote=true → 全自动；当 requireApprovalForNew=true 且 autoPromote=false 时，
新增/变更的源进入 pending，需人工 approve 才进正式 combined.json。
"""
from __future__ import annotations
import json
import os
import threading

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
_STATE = os.path.join(_ROOT, "state")
_APPROVED = os.path.join(_STATE, "approved.json")
_PENDING = os.path.join(_ROOT, "pending", "pending.json")

_lock = threading.Lock()


def _load(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:  # noqa: BLE001
            return {}
    return {}


def _save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def load_approved() -> set:
    return set(_load(_APPROVED).get("fingerprints", []))


def load_pending() -> dict:
    return _load(_PENDING)


def approve(fp: str) -> bool:
    with _lock:
        ap = _load(_APPROVED)
        fps = set(ap.get("fingerprints", []))
        if fp in fps:
            return True
        fps.add(fp)
        ap["fingerprints"] = list(fps)
        _save(_APPROVED, ap)
        # 从 pending 移除
        pend = _load(_PENDING)
        pend.pop(fp, None)
        _save(_PENDING, pend)
        return True


def quarantine(fp: str) -> bool:
    with _lock:
        pend = _load(_PENDING)
        if fp in pend:
            pend.pop(fp, None)
            _save(_PENDING, pend)
        return True


def gate(sources, cfg: dict) -> tuple[list, list]:
    """返回 (active, pending_list)。pending_list 为待确认 Source。"""
    out = cfg.get("output", {})
    require = out.get("requireApprovalForNew", True)
    auto = out.get("autoPromote", True)
    if (not require) or auto:
        return sources, []

    approved = load_approved()
    active, pending = [], []
    for s in sources:
        fp = s.fingerprint()
        if fp in approved:
            active.append(s)
        else:
            pending.append(s)
            pend = _load(_PENDING)
            pend[fp] = s.to_site()
            _save(_PENDING, pend)
    return active, pending
