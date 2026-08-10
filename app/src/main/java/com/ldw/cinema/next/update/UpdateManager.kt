package com.ldw.cinema.next.update

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import androidx.core.content.FileProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.io.File
import java.io.RandomAccessFile
import java.math.BigInteger
import java.security.MessageDigest
import java.util.concurrent.TimeUnit

/**
 * 在线更新管理器（规格 1）。
 *
 * 设计要点：
 *  - 多镜像清单：ghproxy → jsDelivr → raw → mirror.ghproxy，国内更快更稳。
 *  - 后台断点续传：用 Range 头续传；单镜像失败自动切换下一个镜像，避免“几 KB 级慢下载 / 卡死”。
 *  - 完整性：下载完成后做 SHA-256 校验，防止坏包。
 *  - 静默安装：通过 FileProvider 拉起系统安装器，无需 WRITE_EXTERNAL_STORAGE。
 *
 * 注意：本模块不依赖具体 TVBox 基类，可独立编译；在 Application.onCreate 中调用
 * [checkAndUpdate] 即可。
 */
object UpdateManager {

    /** 清单多镜像（与后端 update-mobile.json 位置对应，按需替换仓库名）。 */
    private val MANIFEST_URLS = listOf(
        "https://ghproxy.net/https://raw.githubusercontent.com/lidawei1985/LDW-Cinema-Next/main/update-mobile.json",
        "https://cdn.jsdelivr.net/gh/lidawei1985/LDW-Cinema-Next@main/update-mobile.json",
        "https://raw.githubusercontent.com/lidawei1985/LDW-Cinema-Next/main/update-mobile.json",
        "https://mirror.ghproxy.com/https://raw.githubusercontent.com/lidawei1985/LDW-Cinema-Next/main/update-mobile.json"
    )

    private const val FILE_PROVIDER_AUTH = "com.ldw.cinema.next.fileprovider"
    private const val ATTEMPTS_PER_MIRROR = 3

    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .callTimeout(0, TimeUnit.SECONDS) // 由上层续传控制整体时长
        .build()

    interface ProgressListener {
        fun onProgress(downloaded: Long, total: Long)
        fun onMirrorSwitch(index: Int, url: String)
        fun onDone(file: File)
        fun onError(e: Throwable)
    }

    /** 当前已安装版本号。 */
    fun currentVersionCode(context: Context): Int =
        runCatching {
            context.packageManager.getPackageInfo(context.packageName, 0).versionCode
        }.getOrDefault(0)

    /** 拉取并解析更新清单（多镜像容灾）。 */
    suspend fun fetchManifest(): UpdateInfo? = withContext(Dispatchers.IO) {
        for (url in MANIFEST_URLS) {
            try {
                val req = Request.Builder().url(url).build()
                client.newCall(req).execute().use { resp ->
                    if (!resp.isSuccessful) return@use null
                    val txt = resp.body?.string() ?: return@use null
                    return@withContext parseManifest(txt)
                }
            } catch (_: Exception) {
                // 尝试下一个镜像
            }
        }
        null
    }

    private fun parseManifest(txt: String): UpdateInfo {
        val j = JSONObject(txt)
        val urls = mutableListOf<String>()
        j.optString("apkUrl").takeIf { it.isNotBlank() }?.let { urls.add(it) }
        j.optJSONArray("apkUrls")?.let { arr ->
            for (i in 0 until arr.length()) urls.add(arr.getString(i))
        }
        return UpdateInfo(
            versionCode = j.optInt("versionCode", 0),
            versionName = j.optString("versionName", ""),
            apkUrls = urls.distinct().filter { it.isNotBlank() },
            sha256 = j.optString("sha256").takeIf { it.isNotBlank() },
            changelog = j.optString("changelog", ""),
            force = j.optBoolean("force", false)
        )
    }

    /**
     * 检查更新并在有更新时下载 + 校验 + 安装。
     * @return true 表示已触发安装意图。
     */
    suspend fun checkAndUpdate(
        context: Context,
        listener: ProgressListener? = null
    ): Boolean = withContext(Dispatchers.IO) {
        val cur = currentVersionCode(context)
        val info = fetchManifest() ?: run { listener?.onError(IllegalStateException("无法获取更新清单")); return@withContext false }
        if (info.versionCode <= cur || info.apkUrls.isEmpty()) return@withContext false

        val apk = downloadWithFallback(info.apkUrls, info.sha256, listener)
            ?: run { listener?.onError(IllegalStateException("所有镜像下载失败")); return@withContext false }

        withContext(Dispatchers.Main) { install(context, apk) }
        true
    }

    /** 多镜像断点续传下载 + SHA-256 校验。 */
    private fun downloadWithFallback(
        urls: List<String>,
        expectedSha256: String?,
        listener: ProgressListener?
    ): File? {
        val out = File(createCacheDir(), "update-${System.currentTimeMillis()}.apk")
        if (out.exists()) out.delete()
        out.createNewFile()

        urls.forEachIndexed { idx, url ->
            listener?.onMirrorSwitch(idx, url)
            var start: Long = 0L
            repeat(ATTEMPTS_PER_MIRROR) { attempt ->
                try {
                    val downloaded = downloadRange(url, out, start, listener)
                    if (downloaded >= 0) {
                        start = downloaded
                        // 校验
                        if (expectedSha256 == null || sha256(out) == expectedSha256.lowercase()) {
                            listener?.onDone(out)
                            return out
                        }
                    }
                } catch (e: Exception) {
                    // 切换镜像 / 重试
                }
            }
        }
        out.delete()
        return null
    }

    /** 单镜像续传下载；返回已下载总字节数（失败抛异常或返回 -1）。 */
    private fun downloadRange(
        url: String,
        out: File,
        start: Long,
        listener: ProgressListener?
    ): Long {
        val reqBuilder = Request.Builder().url(url)
        if (start > 0) reqBuilder.header("Range", "bytes=$start-")
        val resp = client.newCall(reqBuilder.build()).execute()
        if (!resp.isSuccessful && resp.code != 206) throw IllegalStateException("HTTP ${resp.code}")

        val total = if (resp.code == 206) {
            resp.header("Content-Range")?.substringAfter("/")?.toLongOrNull() ?: -1L
        } else {
            resp.body?.contentLength()?.takeIf { it > 0 } ?: -1L
        }

        RandomAccessFile(out, "rw").use { raf ->
            if (resp.code == 200) {
                raf.setLength(0)
                start = 0L
            } else {
                raf.seek(start)
            }
            resp.body?.byteStream()?.use { input ->
                val buf = ByteArray(64 * 1024)
                var read: Int
                var written = start
                while (input.read(buf).also { read = it } != -1) {
                    raf.write(buf, 0, read)
                    written += read
                    listener?.onProgress(written, total)
                }
            } ?: throw IllegalStateException("空响应体")
            return written
        }
    }

    /** 调起系统安装器（FileProvider，免存储权限）。 */
    fun install(context: Context, apk: File) {
        val uri: Uri = FileProvider.getUriForFile(context, FILE_PROVIDER_AUTH, apk)
        val intent = Intent(Intent.ACTION_INSTALL_PACKAGE).apply {
            setData(uri)
            setFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(intent)
    }

    private fun createCacheDir(): File {
        val dir = File(System.getProperty("java.io.tmpdir") ?: ".", "ldw_updates")
        dir.mkdirs()
        return dir
    }

    private fun sha256(file: File): String {
        val md = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { fis ->
            val buf = ByteArray(8192)
            var n: Int
            while (fis.read(buf).also { n = it } != -1) md.update(buf, 0, n)
        }
        return BigInteger(1, md.digest()).toString(16).padStart(64, '0')
    }
}
