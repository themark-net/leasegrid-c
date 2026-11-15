package net.themark.leasegrid.sync

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import net.themark.leasegrid.sync.recovery.IMPORT_FAIL_MSG
import net.themark.leasegrid.sync.recovery.IMPORT_FAIL_NEXT
import net.themark.leasegrid.sync.recovery.MAX_RECOVERY_BYTES
import net.themark.leasegrid.sync.ui.AppModel
import net.themark.leasegrid.sync.ui.SyncApp
import net.themark.leasegrid.sync.ui.TooLarge
import net.themark.leasegrid.sync.ui.WriteCopy
import net.themark.leasegrid.sync.ui.readAtMost
import java.io.File

private const val STATE_DELIVERY = "leasegrid.delivery"

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

    private val pickAdd = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        val folder = model.addTarget() ?: return@registerForActivityResult
        if (uri == null) return@registerForActivityResult
        readAddedFile(folder, uri)
    }

    private fun openRecoveryPicker() {
        pickRecovery.launch(arrayOf("*/*"))
    }

    private fun openAddPicker() {
        if (model.addTarget() == null) return
        pickAdd.launch(arrayOf("*/*"))
    }

    /** Hash of the last applied launch payload. Not the invite text. */
    private var appliedToken: String? = null
    private var readGeneration = 0

    /** Not decorView: noteIntent runs in onCreate before setContent. */
    private val mainHandler = Handler(Looper.getMainLooper())

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        appliedToken = savedInstanceState?.getString(STATE_DELIVERY)
        // Before setContent, so a cold-start EXTRA_RECOVERY_FILE composes Import first.
        // A restored activity already applied this intent. Applying it again wipes the home.
        noteIntent(intent)
        setContent {
            SyncApp(model, ::openRecoveryPicker, ::openAddPicker)
        }
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        appliedToken?.let { outState.putString(STATE_DELIVERY, it) }
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
        if (DogfoodIntents.sameDelivery(appliedToken, key)) return
        appliedToken = DogfoodIntents.deliveryToken(key)
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
            val epoch = model.beginRecoveryImport()
            val generation = ++readGeneration
            readRecoveryFile(recoveryPath, attempt = 0, generation = generation, epoch = epoch)
            return
        }
        if (intent.action == Intent.ACTION_VIEW) {
            val uri = intent.data
            if (uri != null && uri.scheme != "leasegrid") {
                val epoch = model.beginRecoveryImport()
                readRecovery(uri, uri.lastPathSegment ?: "recovery.leasegrid-recovery", epoch)
            }
        }
    }

    private fun readRecoveryFile(rawPath: String, attempt: Int, generation: Int, epoch: Int) {
        if (generation != readGeneration) return
        if (!model.recoveryReadCurrent(epoch)) return
        val loaded = DogfoodIntents.loadRecoveryExtra(filesDir, rawPath)
        if (loaded.bytes != null) {
            if (!model.recoveryReadCurrent(epoch)) return
            model.onPicked(loaded.name, loaded.bytes)
            model.goImport()
            return
        }
        if (!loaded.rejected && attempt < 5) {
            mainHandler.postDelayed(
                { readRecoveryFile(rawPath, attempt + 1, generation, epoch) },
                200L * (attempt + 1),
            )
            return
        }
        if (!model.recoveryReadCurrent(epoch)) return
        val again: () -> Unit = if (loaded.rejected) {
            ::openRecoveryPicker
        } else {
            {
                val nextEpoch = model.beginRecoveryImport()
                val nextGeneration = ++readGeneration
                readRecoveryFile(rawPath, 0, nextGeneration, nextEpoch)
            }
        }
        model.goImport()
        model.reportFail(
            loaded.banner ?: "could not import this recovery key. The file could not be read.",
            loaded.next ?: "check the path and storage permission; Retry.",
            again,
        )
    }

    private fun inviteQuery(data: Uri?): String? {
        if (data == null || data.scheme != "leasegrid") return null
        return data.getQueryParameter(DogfoodIntents.QUERY_INVITE)
    }

    private fun readAddedFile(folder: net.themark.leasegrid.sync.session.FolderRef, uri: Uri) {
        val name = queryDisplayName(uri) ?: uri.lastPathSegment ?: "file"
        try {
            val bytes = contentResolver.openInputStream(uri)?.use { readAtMost(it, WriteCopy.ADD_MAX_BYTES) }
                ?: error("empty stream")
            model.onFilePicked(folder, name, bytes)
        } catch (_: TooLarge) {
            model.reportFail(WriteCopy.READ_FAIL, WriteCopy.TOO_BIG_NEXT)
        } catch (exc: Exception) {
            android.util.Log.w("LeasegridSync", "add read failed: ${exc.javaClass.simpleName}")
            model.reportFail(WriteCopy.READ_FAIL, WriteCopy.READ_NEXT)
        }
    }

    private fun queryDisplayName(uri: Uri): String? {
        val projection = arrayOf(android.provider.OpenableColumns.DISPLAY_NAME)
        return try {
            contentResolver.query(uri, projection, null, null, null)?.use { cursor ->
                if (!cursor.moveToFirst()) return@use null
                val index = cursor.getColumnIndex(android.provider.OpenableColumns.DISPLAY_NAME)
                if (index < 0) null else cursor.getString(index)
            }
        } catch (_: Exception) {
            null
        }
    }

    private fun readRecovery(uri: Uri, name: String, epoch: Int) {
        if (!model.recoveryReadCurrent(epoch)) return
        readRecovery(uri, name)
    }

    private fun readRecovery(uri: Uri, name: String) {
        try {
            val bytes = when (uri.scheme) {
                "file", null -> {
                    val path = uri.path ?: error("no path")
                    File(path).inputStream().use { readAtMost(it, MAX_RECOVERY_BYTES) }
                }
                else -> contentResolver.openInputStream(uri)?.use { readAtMost(it, MAX_RECOVERY_BYTES) }
                    ?: error("empty stream")
            }
            if (bytes.isEmpty()) error("empty file")
            model.onPicked(name, bytes)
            model.goImport()
        } catch (_: TooLarge) {
            // Bigger than any recovery file: the same card as a corrupt one.
            model.goImport()
            model.reportFail(IMPORT_FAIL_MSG, IMPORT_FAIL_NEXT, ::openRecoveryPicker)
        } catch (exc: Exception) {
            android.util.Log.w("LeasegridSync", "recovery read failed: ${exc.javaClass.simpleName}")
            model.goImport()
            model.reportFail(
                "could not import this recovery key. The file could not be read.",
                "check the path and storage permission; Retry.",
                ::openRecoveryPicker,
            )
        }
    }
}
