"""数据模型：片源 / 直播源 / 健康分。"""
from __future__ import annotations
import time
import hashlib
import json
from dataclasses import dataclass, field, asdict


def _now() -> float:
    return time.time()


@dataclass
class Source:
    """一个影视点播源（spider / 直链 / 解析）。"""
    key: str                 # 唯一键，如 "dytt"
    name: str                # 展示名
    api: str = ""            # spider 接口或资源站地址
    type: str = "normal"     # normal / spider / parse
    searchable: int = 1      # 是否可搜索 0/1
    playable: int = 1
    ext: str = ""            # 扩展参数
    group: str = "默认"
    posterProxy: str = ""
    health: float = 0.0
    lastChecked: float = 0.0
    detail: str = ""         # 校验细节（给人看）
    origin: str = "unknown"  # upstream url / samples / live

    def fingerprint(self) -> str:
        """用于判断是否需要人工确认（新增/变更）。"""
        raw = json.dumps({
            "key": self.key, "name": self.name, "api": self.api,
            "type": self.type, "searchable": self.searchable,
            "playable": self.playable, "ext": self.ext, "group": self.group,
        }, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def to_site(self) -> dict:
        """导出为 combined.json 的 sites 条目（TVBox 兼容）。"""
        d = {
            "key": self.key,
            "name": self.name,
            "type": self.type,
            "api": self.api,
            "searchable": self.searchable,
            "playable": self.playable,
            "group": self.group,
        }
        if self.ext:
            d["ext"] = self.ext
        if self.posterProxy:
            d["proxy"] = self.posterProxy
        return d


@dataclass
class LiveSource:
    key: str
    name: str
    url: str                # m3u 或 json 直播源
    type: str = "m3u"       # m3u / json
    group: str = "直播"
    channelCount: int = 0
    health: float = 0.0
    lastChecked: float = 0.0
    detail: str = ""
    origin: str = "unknown"

    def fingerprint(self) -> str:
        raw = json.dumps({"key": self.key, "name": self.name, "url": self.url,
                          "type": self.type, "group": self.group},
                         sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def to_live(self) -> dict:
        return {
            "name": self.name,
            "type": self.type,
            "url": self.url,
            "group": self.group,
            "channels": self.channelCount,
            "health": round(self.health, 1),
        }


@dataclass
class HealthReport:
    generatedAt: float = field(default_factory=_now)
    sources: dict = field(default_factory=dict)   # key -> health
    lives: dict = field(default_factory=dict)
    summary: str = ""

    def to_dict(self) -> dict:
        return asdict(self)
