package net.themark.leasegrid.sync

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import net.themark.leasegrid.sync.ui.AppModel
import net.themark.leasegrid.sync.ui.SyncApp
import java.io.File

class MainActivity : ComponentActivity() {
    private val model: AppModel by viewModels()

    private val pickRecovery = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri == null) {
            model.goImport()
            model.reportFail(
                "could not import this recovery key. No file was chosen.",
                "choose a *.leasegrid-recovery file; Retry.",
                ::openRecoveryPicker,
            )
            return@registerForActivityResult
        }
        readRecovery(uri, uri.lastPathSegment ?: "recovery.leasegrid-recovery")
    }

    private fun openRecoveryPicker() {
        pickRecovery.launch(arrayOf("*/*"))
    }

    /** Each incoming Intent is applied once, after the first frame, so Import is composed. */
    private var delivered: Intent? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            SyncApp(model, ::openRecoveryPicker)
        }
    }

    override fun onStart() {
        super.onStart()
        window.decorView.post { deliverLatest(intent) }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        window.decorView.post { deliverLatest(intent) }
    }

    private fun deliverLatest(incoming: Intent?) {
        if (incoming == null || incoming === delivered) return
        delivered = incoming
        deliver(incoming)
    }

    private fun deliver(intent: Intent?) {
        if (intent == null) return
        if (BuildConfig.DEBUG) {
            val invite = DogfoodIntents.inviteText(
                intent.getStringExtra(DogfoodIntents.EXTRA_INVITE),
                inviteQuery(intent.data),
            )
            if (invite != null) {
                model.inviteText = invite
                if (model.session == null) model.goWelcome()
            }
            val recoveryPath = intent.getStringExtra(DogfoodIntents.EXTRA_RECOVERY_FILE)?.trim().orEmpty()
            if (recoveryPath.isNotEmpty()) {
                val file = if (recoveryPath.startsWith("/")) File(recoveryPath) else File(filesDir, recoveryPath)
                readRecovery(Uri.fromFile(file), file.name)
            }
        }
        if (intent.action == Intent.ACTION_VIEW) {
            val uri = intent.data
            if (uri != null && uri.scheme != "leasegrid") {
                readRecovery(uri, uri.lastPathSegment ?: "recovery.leasegrid-recovery")
            }
        }
    }

    private fun inviteQuery(data: Uri?): String? {
        if (data == null || data.scheme != "leasegrid") return null
        return data.getQueryParameter(DogfoodIntents.QUERY_INVITE)
    }

    private fun readRecovery(uri: Uri, name: String) {
        try {
            val bytes = when (uri.scheme) {
                "file", null -> {
                    val path = uri.path ?: error("no path")
                    File(path).readBytes()
                }
                else -> contentResolver.openInputStream(uri)?.use { it.readBytes() }
                    ?: error("empty stream")
            }
            if (bytes.isEmpty()) error("empty file")
            model.onPicked(name, bytes)
            model.goImport()
        } catch (exc: Exception) {
            model.goImport()
            model.reportFail(
                "could not import this recovery key. The file could not be read.",
                "check the path and storage permission; Retry. (${exc.javaClass.simpleName})",
                ::openRecoveryPicker,
            )
        }
    }
}
