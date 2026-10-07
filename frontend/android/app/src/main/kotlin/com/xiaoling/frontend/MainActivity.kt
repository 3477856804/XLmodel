package com.xiaoling.frontend

import android.content.Context
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.util.concurrent.Executors

class MainActivity : FlutterActivity() {

    private val channelName = "xiaoling/sandbox"
    private val bg = Executors.newSingleThreadExecutor()

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        val channel = MethodChannel(flutterEngine.dartExecutor, channelName)
        channel.setMethodCallHandler { call, result ->
            when (call.method) {
                "startSandbox" -> bg.execute {
                    try {
                        SandboxService.start(applicationContext)
                        Thread.sleep(600)
                        val status = SandboxService.statusJson()
                        result.success(mapOf("ok" to true, "status" to status))
                    } catch (t: Throwable) {
                        result.error("START_FAILED", t.message, null)
                    }
                }
                "stopSandbox" -> bg.execute {
                    try {
                        SandboxService.stop(applicationContext)
                        result.success(mapOf("ok" to true))
                    } catch (t: Throwable) {
                        result.error("STOP_FAILED", t.message, null)
                    }
                }
                "getSandboxStatus" -> bg.execute {
                    try {
                        val status = SandboxService.statusJson()
                        val snap = SandboxService.modelSnapshotJson()
                        result.success(mapOf("status" to status, "snapshot" to snap))
                    } catch (t: Throwable) {
                        result.error("STATUS_FAILED", t.message, null)
                    }
                }
                "downloadModel" -> bg.execute {
                    try {
                        val name = call.argument<String>("name") ?: ""
                        val quant = call.argument<String>("quant") ?: "q4_k_m"
                        val resp = SandboxService.downloadModel(name, quant)
                        result.success(mapOf("ok" to true, "result" to resp))
                    } catch (t: Throwable) {
                        result.error("DOWNLOAD_FAILED", t.message, null)
                    }
                }
                else -> result.notImplemented()
            }
        }
    }
}
