# LDW-Cinema-Next

一个干净、去混淆、可维护的 Android 影视应用（TVBox / CatVod 架构底座 + 自研增强模块）。
满足五项规范：在线更新、功能一致性、搜索联想、自动化资源管理、片源自维护 API。

## 目录结构
```
ldw_next/
├── backend/                # 自维护片源 API（规格 4/5）· 纯标准库 Python，随处可跑
│   ├── config.json         # 上游源、校验阈值、调度、海报代理
│   ├── src/                # aggregator / validator / live_discoverer / merger / approval / api_server / main
│   ├── samples/            # 冷启动样本源
│   └── dist/               # 产出 combined.json + live.json（App 直接拉取）
├── app/                    # Android 增强模块（规格 1/2/3）· 交给 CI 编译
│   └── src/main/java/com/ldw/cinema/next/
│       ├── update/         # 多镜像断点续传更新器（UpdateManager）
│       ├── search/         # 人名/剧名/海报联想（SearchSuggestionManager + PersonIndex）
│       └── core/           # 动作路由 + 全局崩溃兜底（ActionRouter / CrashGuard）
├── update-mobile.json      # App 在线更新清单（多镜像 APK + sha256）
└── .github/workflows/      # CI：后端发片源清单 + Android 编译 APK
```

## 五项规范如何落地
| 规范 | 实现 |
|---|---|
| 1 在线更新 | `update/UpdateManager`：清单多镜像(ghproxy/jsDelivr/raw)、后台断点续传(Range)、SHA-256 校验、FileProvider 静默安装，杜绝几 KB 慢下载与中断 |
| 2 功能一致性 | `core/ActionRouter` 集中路由按键↔标识↔分类；`core/CrashGuard` 全局异常兜底，模块协同不串味 |
| 3 搜索联想 | `search/SearchSuggestionManager`：输入"L"返回 李丽珍/李小龙/刘德华/柳岩 及对应海报；支持中文名/拼音/首字母匹配 |
| 4 自动化资源管理 | `backend/src/live_discoverer` 自动发现/维护直播源；`validator` 给片源打健康分；`posterConfig.proxyUrl`(wsrv.nl)稳定加载海报 |
| 5 片源自维护 API | `backend/src/*`：聚合上游 spider 配置 → 校验 → 合并生成 `combined.json`；`approval` 提供人工确认闸，默认全自动、关键节点才确认 |

## 运行后端（本机即可）
```bash
cd backend
python -m src.main --once        # 跑一次，生成 dist/combined.json
python -m src.main --serve       # 启动 HTTP API（默认 :8787），并定时重跑
# 端点：/combined.json /live.json /health /pending
#       POST /approve?fp=指纹  POST /quarantine?fp=指纹  POST /trigger
```
把真实上游 spider 配置地址填进 `config.json → aggregator.upstreams` 即可接入生产源。

## 构建 Android APK
自定义模块叠加在 TVBox / CatVod 底座上（底座提供播放器与 spider 运行时）。
在 GitHub 上以 `workflow_dispatch` 提供 `base_repo`（如 `owner/TVBoxOSC@main`）即可由 CI 编译并签名发布。
本机无完整 Android SDK 时，可用上一轮得到的**修补版 APK（基于光幕底座，已含更新/搜索/海报行为）**作为立即可装的过渡产物。

## 说明
- 海报代理默认用公共 `wsrv.nl`，如需更稳可换 Cloudflare Worker（见旧仓库 `docs/POSTER_CACHE_GUIDE.md`）。
- 片源聚合遵循社区 spider 配置机制（聚合公开共享的配置清单并校验），由 `approval` 闸控制质量。
