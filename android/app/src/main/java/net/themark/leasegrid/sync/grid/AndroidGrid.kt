package net.themark.leasegrid.sync.grid

import android.content.Context
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject

/** Calls `leasegrid_read.dispatch` in-process. Never the Tahoe web UI. */
class AndroidGrid(context: Context) {
    private val appContext = context.applicationContext
    private val json = Json { ignoreUnknownKeys = true }

    fun dispatch(op: String, payload: String): JsonObject {
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(appContext))
        }
        val raw = Python.getInstance()
            .getModule("leasegrid_read")
            .callAttr("dispatch", op, payload)
            .toString()
        return json.parseToJsonElement(raw).jsonObject
    }
}
