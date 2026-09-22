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

    /** Fingerprint of the last applied dogfood payload. Not Intent identity. */
    private var appliedKey: String? = null
    private var readGeneration = 0

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Before setContent, so a cold-start EXTRA_RECOVERY_FILE composes Import first.
        noteIntent(intent)
        setContent {
            SyncApp(model, ::openRecoveryPicker)
        }
    }

    override fun onStart() {
        super.onStart()
        noteIntent(intent)
    }

    override fun onResume() {
        super.onResume()
        noteIntent(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        noteIntent(intent)
    }

    private fun noteIntent(incoming: Intent?) {
        if (incoming == null) return
        val recoveryExtra = if (BuildConfig.DEBUG) {
            incoming.getStringExtra(DogfoodIntents.EXTRA_RECOVERY_FILE)
        } else {
            null
        }
        val inviteExtra = if (BuildConfig.DEBUG) {
            incoming.getStringExtra(DogfoodIntents.EXTRA_INVITE)
        } else {
            null
        }
        val key = DogfoodIntents.deliveryKey(incoming.action, inviteExtra, recoveryExtra, incoming.dataString)
        if (!DogfoodIntents.shouldDeliver(appliedKey, key)) return
        appliedKey = key
        deliver(incoming, recoveryExtra, inviteExtra)
    }

    private fun deliver(intent: Intent, recoveryExtra: String?, inviteExtra: String?) {
        val recoveryPath = recoveryExtra?.trim().orEmpty()
        if (BuildConfig.DEBUG) {
            val invite = DogfoodIntents.inviteText(inviteExtra, inviteQuery(intent.data))
            if (invite != null) model.inviteText = invite
            if (invite != null && recoveryPath.isEmpty() && model.session == null) model.goWelcome()
        }
        if (DogfoodIntents.opensImport(recoveryPath)) {
            model.beginRecoveryImport()
            val generation = ++readGeneration
            readRecoveryFile(recoveryPath, attempt = 0, generation = generation)
            return
        }
        if (intent.action == Intent.ACTION_VIEW) {
            val uri = intent.data
            if (uri != null && uri.scheme != "leasegrid") {
                model.beginRecoveryImport()
                readRecovery(uri, uri.lastPathSegment ?: "recovery.leasegrid-recovery")
            }
        }
    }

    private fun readRecoveryFile(rawPath: String, attempt: Int, generation: Int) {
        if (generation != readGeneration) return
        val file = DogfoodIntents.recoveryFile(filesDir, rawPath)
        val seed = DogfoodIntents.readRecoverySeed(file)
        if (seed.readable && seed.bytes != null) {
            model.onPicked(seed.name, seed.bytes)
            model.goImport()
            return
        }
        if (attempt < 5) {
            window.decorView.postDelayed(
                { readRecoveryFile(rawPath, attempt + 1, generation) },
                200L * (attempt + 1),
            )
            return
        }
        model.goImport()
        model.reportFail(
            "could not import this recovery key. The file could not be read.",
            "check the path and storage permission; Retry.",
        ) {
            model.beginRecoveryImport()
            val again = ++readGeneration
            readRecoveryFile(rawPath, 0, again)
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
