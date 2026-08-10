package com.ldw.cinema.next.core

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.widget.Toast
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.Executors

/**
 * 全局崩溃兜底（规格 2：模块协同、避免静默闪退）。
 *
 * 未捕获异常不再直接杀死进程，而是：记录日志 + Toast 提示 + 降级继续。
 * 这与 smali 层之前的 LiveGuard 思路一致，但放到干净的源码层。
 */
object CrashGuard {

    @Volatile
    private var installed = false

    fun install(context: Context, logDir: File? = null) {
        if (installed) return
        installed = true
        val default = Thread.getDefaultUncaughtExceptionHandler()
        val executor = Executors.newSingleThreadExecutor()

        Thread.setDefaultUncaughtExceptionHandler { thread, throwable ->
            val msg = buildString {
                append("[").append(thread.name).append("] ")
                append(throwable.javaClass.name).append(": ")
                append(throwable.message ?: "null")
                append("\n").append(throwable.stackTraceToString().take(2000))
            }
            // 1) 落盘
            executor.execute {
                runCatching {
                    val dir = logDir ?: File(context.filesDir, "crash")
                    dir.mkdirs()
                    val ts = SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US).format(Date())
                    File(dir, "crash-$ts.log").writeText(msg)
                }
            }
            // 2) 主线程 Toast 提示（避免静默死）
            try {
                Handler(Looper.getMainLooper()).post {
                    Toast.makeText(context, "发生异常已记录：${throwable.message?.take(60)}", Toast.LENGTH_LONG).show()
                }
            } catch (_: Exception) { /* ignore */ }

            // 3) 交给默认处理器（避免吞掉系统关键崩溃）
            default?.uncaughtException(thread, throwable)
        }
    }
}
