package com.ldw.cinema.next.update

/**
 * 更新清单模型（与后端 update-mobile.json 对齐）。
 *
 * 后端生成的 JSON 结构（由自维护片源 API 产出，见 backend/）：
 * {
 *   "packageName": "com.ldw.cinema.next",
 *   "versionCode": 249,
 *   "versionName": "0.1.249",
 *   "apkUrl": "https://ghproxy.net/.../app-release.apk",
 *   "apkUrls": ["https://mirror.ghproxy.com/...", "https://github.com/.../releases/download/..."],
 *   "sha256": "xxxx",
 *   "changelog": "修复...",
 *   "force": false
 * }
 */
data class UpdateInfo(
    val versionCode: Int,
    val versionName: String,
    val apkUrls: List<String>,
    val sha256: String?,
    val changelog: String,
    val force: Boolean
) {
    val primaryUrl: String get() = apkUrls.firstOrNull().orEmpty()
}
