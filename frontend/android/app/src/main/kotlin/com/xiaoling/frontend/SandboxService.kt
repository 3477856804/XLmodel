package com.xiaoling.frontend

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.util.Log
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform

/**
 * 小凌 Android 沙箱前台服务。
 *
 * 生命周期：MainActivity 通过 startForegroundService 拉起本服务；
 * onCreate 内初始化 Chaquopy Python 并调用 sandbox_entry.start(port)。
 * 状态与下载均通过 Python 模块的 JSON 接口读写，方法挂在 companion 上供
 * MainActivity 的 MethodChannel 直接调用。
 */
class SandboxService : Service() {

    companion object {
        private const val TAG = "XiaoLingSandbox"
        private const val CHANNEL_ID = "xiaoling_sandbox"
        private const val NOTIF_ID = 4201
        private const val PORT = 50051

        @Volatile
        private var instance: SandboxService? = null

        @Volatile
        var isRunning: Boolean = false
            private set

        @Volatile
        var lastStatusJson: String = "{}"
            private set

        fun start(ctx: Context) {
            val intent = Intent(ctx, SandboxService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                ctx.startForegroundService(intent)
            } else {
                ctx.startService(intent)
            }
        }

        fun stop(ctx: Context) {
            ctx.stopService(Intent(ctx, SandboxService::class.java))
        }

        fun statusJson(): String {
            val svc = instance ?: return "{\"started\":false,\"error\":\"service not created\"}"
            return try {
                val py = Python.getInstance()
                py.getModule("sandbox_entry").callAttr("status_json").toString()
            } catch (t: Throwable) {
                Log.w(TAG, "status failed: $t")
                lastStatusJson
            }
        }

        fun modelSnapshotJson(): String {
            return try {
                Python.getInstance().getModule("sandbox_entry").callAttr("model_snapshot_json").toString()
            } catch (t: Throwable) {
                "{}"
            }
        }

        fun downloadModel(name: String, quant: String): String {
            return try {
                Python.getInstance()
                    .getModule("sandbox_entry")
                    .callAttr("download_model_json", name, quant)
                    .toString()
            } catch (t: Throwable) {
                Log.w(TAG, "download failed: $t")
                "{\"ok\":false,\"error\":\"${t.message}\"}"
            }
        }
    }

    private var wakeLock: PowerManager.WakeLock? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        instance = this
        createChannel()
        startForeground(NOTIF_ID, buildNotification("小凌沙箱启动中…"))
        bootPython()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        return START_STICKY
    }

    private fun bootPython() {
        try {
            if (!Python.isStarted()) {
                Python.start(AndroidPlatform(applicationContext))
            }
            val py = Python.getInstance()
            val home = filesDir.absolutePath
            py.getModule("sandbox_entry").callAttr("setup", home)
            py.getModule("sandbox_entry").callAttr("start", PORT)
            lastStatusJson = try {
                py.getModule("sandbox_entry").callAttr("status_json").toString()
            } catch (_: Throwable) {
                "{}"
            }
            isRunning = true
            setNotification("小凌沙箱运行中 · gRPC :$PORT")
            Log.i(TAG, "python sandbox booted, home=$home")
        } catch (t: Throwable) {
            isRunning = false
            Log.e(TAG, "python boot failed: $t", t)
            setNotification("小凌沙箱启动失败：${t.javaClass.simpleName}")
        }
    }

    private fun createChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val nm = getSystemService(NotificationManager::class.java)
        val channel = NotificationChannel(
            CHANNEL_ID, "小凌沙箱", NotificationManager.IMPORTANCE_LOW
        ).apply {
            description = "保持本地 Python 后端运行"
            setShowBadge(false)
        }
        nm.createNotificationChannel(channel)
    }

    private fun buildNotification(text: String): Notification {
        val pi = PendingIntent.getActivity(
            this, 0, packageManager.getLaunchIntentForPackage(packageName),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        )
        val builder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Notification.Builder(this, CHANNEL_ID)
        } else {
            @Suppress("DEPRECATION")
            Notification.Builder(this)
        }
        return builder
            .setContentTitle("小凌")
            .setContentText(text)
            .setSmallIcon(applicationInfo.icon)
            .setContentIntent(pi)
            .setOngoing(true)
            .build()
    }

    private fun setNotification(text: String) {
        try {
            val nm = getSystemService(NotificationManager::class.java)
            nm.notify(NOTIF_ID, buildNotification(text))
        } catch (_: Throwable) {
        }
    }

    override fun onDestroy() {
        try {
            Python.getInstance().getModule("sandbox_entry").callAttr("stop")
        } catch (_: Throwable) {
        }
        isRunning = false
        instance = null
        super.onDestroy()
    }
}
