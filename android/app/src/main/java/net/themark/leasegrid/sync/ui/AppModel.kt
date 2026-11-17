package net.themark.leasegrid.sync.ui

import android.app.Application
import android.content.ActivityNotFoundException
import android.content.Intent
import android.os.Environment
import android.os.StatFs
import android.util.Log
import android.util.Base64
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.FileProvider
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlin.coroutines.coroutineContext
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.security.SecureRandom
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.add
import kotlinx.serialization.json.addJsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray
import net.themark.leasegrid.sync.grid.AndroidGrid
import net.themark.leasegrid.sync.invite.Invite
import net.themark.leasegrid.sync.invite.InviteFail
import net.themark.leasegrid.sync.invite.RedeemOutcome
import net.themark.leasegrid.sync.recovery.IMPORT_FAIL_MSG
import net.themark.leasegrid.sync.recovery.IMPORT_FAIL_NEXT
import net.themark.leasegrid.sync.recovery.ImportFail
import net.themark.leasegrid.sync.recovery.RecoveryCodec
import net.themark.leasegrid.sync.session.FolderRef
import net.themark.leasegrid.sync.session.ServerRef
import net.themark.leasegrid.sync.session.Session
import net.themark.leasegrid.sync.session.SessionStore
import java.io.File
import java.io.IOException
import kotlin.coroutines.CoroutineContext

data class ChildRow(val name: String, val kind: String, val cap: String, val size: Int)

sealed class Place {
    data object Welcome : Place()
    data object Import : Place()
    data object Folders : Place()
    data class Folder(val folder: FolderRef, val children: List<ChildRow>) : Place()
    data class Downloading(val name: String, val cap: String) : Place()
    data class Ready(val name: String, val file: File) : Place()
    data object About : Place()
    data object Settings : Place()
}

private const val TAG = "LeasegridSync"

/**
 * Test seam for JVM unit tests. Production uses [AppSeams] with no arguments:
 * the app's files dir, viewModelScope, Dispatchers.IO and the embedded Python grid.
 */
internal class AppSeams(
    val filesDir: File? = null,
    val scope: CoroutineScope? = null,
    val io: CoroutineContext = Dispatchers.IO,
    val dispatch: ((String, String) -> JsonObject)? = null,
    val freeBytes: ((File) -> Long)? = null,
)

class AppModel internal constructor(app: Application, seams: AppSeams) : AndroidViewModel(app) {
    constructor(app: Application) : this(app, AppSeams())

    private val io = seams.io
    private val scope: CoroutineScope = seams.scope ?: viewModelScope
    private val testFilesDir = seams.filesDir
    private val store = SessionStore(File(testFilesDir ?: app.filesDir, "leasegrid"))
    private val gridDispatch: (String, String) -> JsonObject = seams.dispatch ?: AndroidGrid(app)::dispatch
    private val freeBytes: (File) -> Long = seams.freeBytes ?: { dir -> StatFs(dir.absolutePath).availableBytes }
    private val json = Json { ignoreUnknownKeys = true }
    private val board = FolderWriteBoard()
    private val uploads = mutableMapOf<String, Job>()

    /** Bumps when a pending row or sheet changes so the folder screen redraws. */
    var writeTick by mutableStateOf(0)
        private set

    var place by mutableStateOf<Place>(Place.Welcome)
        private set
    var fail by mutableStateOf<FailBanner?>(null)
        private set
    var busy by mutableStateOf(false)
        private set
    var session by mutableStateOf<Session?>(null)
        private set
    var acknowledged by mutableStateOf(false)
    var inviteText by mutableStateOf("")
    var passphrase by mutableStateOf("")
    var pickedName by mutableStateOf("")
    var pickedBytes by mutableStateOf<ByteArray?>(null)

    private val retries = RetryOnce()
    private var recoveryEpoch = 0

    /** True while a short-code handshake is inside the grid call. */
    @Volatile private var redeeming = false

    private val gridRun = GridRun(
        scope = scope,
        setBusy = { busy = it },
        setFail = { fail = it },
    )

    // Join, refresh and import-finish live in SessionFlow (pure JVM, tested there).
    // The pasted text stays in inviteText on every fail (#50).
    private val flow = SessionFlow(object : FlowHost {
        override var inviteText: String
            get() = this@AppModel.inviteText
            set(value) { this@AppModel.inviteText = value }
        override val session: Session? get() = this@AppModel.session
        override fun launch(label: String, block: suspend () -> Unit) = runGrid(label, block)
        override suspend fun learn(furl: String): List<ServerRef>? = this@AppModel.learn(furl)
        override suspend fun redeem(code: String): RedeemOutcome = this@AppModel.redeem(code)
        override fun save(next: Session) {
            store.save(next)
            this@AppModel.session = next
            place = Place.Folders
        }
        override fun show(banner: FailBanner, again: () -> Unit) = this@AppModel.show(banner, again)
    })

    init {
        val existing = store.load()
        if (existing != null) {
            session = existing
            place = Place.Folders
        }
        restorePendingAdds()
    }

    fun joinEnabled(): Boolean = Invite.joinEnabled(acknowledged, inviteText)

    fun goWelcome() {
        fail = null
        place = Place.Welcome
    }

    /**
     * Cancel and the back arrow on the Import screen. A running import stops:
     * nothing is saved and the phone stays on Welcome (T1).
     */
    fun cancelImport() {
        // Retire this attempt so a read that is still waiting cannot land
        // if Import is opened again.
        recoveryEpoch += 1
        gridRun.cancel()
        retries.arm(null)
        goWelcome()
    }

    /** True only for the import attempt that is still on screen. */
    fun recoveryReadCurrent(epoch: Int): Boolean = epoch == recoveryEpoch && place == Place.Import

    fun goImport() {
        // Leaving Invite cancels a short-code attempt. Folders uses this too,
        // and that path has no handshake to stop.
        if (place == Place.Welcome) {
            if (redeeming) abandonRedeem()
            gridRun.cancel()
            retries.arm(null)
        }
        fail = null
        place = Place.Import
    }

    /**
     * Drop any joined home and show Import before the recovery file is read.
     * Returns the attempt id a later read must still match.
     */
    fun beginRecoveryImport(): Int {
        recoveryEpoch += 1
        store.clear()
        session = null
        pickedName = ""
        pickedBytes = null
        passphrase = ""
        fail = null
        // Bump the ticket so this import's finish cannot clear a later join's busy.
        if (redeeming) abandonRedeem()
        gridRun.cancel()
        place = Place.Import
        return recoveryEpoch
    }

    fun goFolders() {
        fail = null
        place = Place.Folders
    }

    fun goAbout() {
        fail = null
        place = Place.About
    }

    fun goSettings() {
        fail = null
        place = Place.Settings
    }

    /** The card offers Retry only when a real action is armed. Otherwise only Dismiss (#88). */
    val canRetry: Boolean
        get() = retries.armed

    fun dismissFail() {
        fail = null
        retries.arm(null)
    }

    /** In-app FAIL. Does not write a session. [again] is the Retry action. */
    fun reportFail(message: String, next: String, again: (() -> Unit)? = null) {
        show(FailBanner(message, next), again)
    }

    fun retryFail() {
        val action = retries.pull()
        fail = null
        action?.invoke()
    }

    fun join() {
        if (!acknowledged) {
            show(FailBanner(Invite.ACK_MSG, Invite.ACK_NEXT)) { join() }
            return
        }
        flow.join()
    }

    /**
     * A camera scan. Null means cancelled: the field and the banner stay.
     * A join link or short code replaces the field and does not join.
     * Anything else keeps the field and shows the same banner a paste of that text would.
     */
    fun onScanned(text: String?) {
        if (text == null) return
        val cleaned = try {
            Invite.acceptScan(text)
        } catch (exc: InviteFail) {
            // No Retry: retrying would join the old field text. Scan again instead.
            show(FailBanner(exc.banner, exc.next), null)
            return
        }
        inviteText = cleaned
        dismissFail()
    }

    /**
     * Scan QR tapped. Ask for the camera before the scanner opens, so a refusal
     * reaches our card and never the scanner's own error dialog (#88).
     */
    fun onScanTapped(cameraGranted: Boolean, launchScanner: () -> Unit, askCamera: () -> Unit) {
        if (cameraGranted) launchScanner() else askCamera()
    }

    /** The answer to the camera prompt. Allowed opens the scanner. Refused shows the paste guidance. */
    fun onCameraAnswer(granted: Boolean, launchScanner: () -> Unit) {
        if (granted) launchScanner() else onScanDenied()
    }

    /**
     * What the scanner screen returned. No text with the missing-permission flag
     * is a refused camera. Anything else is a scan or a cancel.
     */
    fun onScanResult(contents: String?, missingCameraPermission: Boolean) {
        if (contents == null && missingCameraPermission) onScanDenied() else onScanned(contents)
    }

    /** The camera was not allowed. The field stays. Join does not start. */
    fun onScanDenied() {
        show(FailBanner(Invite.SCAN_DENIED_MSG, Invite.SCAN_DENIED_NEXT), null)
    }

    fun onPicked(name: String, bytes: ByteArray) {
        pickedName = name
        pickedBytes = bytes
    }

    fun importRecovery() {
        val bytes = pickedBytes
        if (bytes == null) {
            show(
                FailBanner(
                    IMPORT_FAIL_MSG,
                    "choose a *.leasegrid-recovery file exported from desktop Sync; Retry.",
                ),
            ) { importRecovery() }
            return
        }
        val phrase = passphrase
        runGrid("Importing…") {
            val bundle = try {
                withContext(io) { RecoveryCodec.decode(bytes, phrase) }
            } catch (exc: ImportFail) {
                show(FailBanner(exc.banner, exc.next)) { importRecovery() }
                return@runGrid
            }
            flow.finishImport(bundle.introducerFurl) { learned ->
                Session(
                    introducerFurl = bundle.introducerFurl,
                    nickname = bundle.nickname,
                    shares = bundle.shares,
                    folders = bundle.folders.map { FolderRef(it.name, it.collective) },
                    servers = learned ?: session?.servers ?: emptyList(),
                )
            }
        }
    }

    fun refresh() {
        flow.refresh()
    }

    fun openFolder(folder: FolderRef) {
        val current = session
        if (current == null || current.servers.isEmpty()) {
            show(
                FailBanner(
                    "could not load folders. Network error talking to storage.",
                    "check network; Retry.",
                ),
            ) { openFolder(folder) }
            return
        }
        runGrid("Loading…") {
            val result = withContext(io) {
                dispatch(
                "list",
                buildJsonObject {
                    put("cap", folder.cap)
                    putJsonArray("servers") {
                        for (server in current.servers) {
                            addJsonObject {
                                put("furl", server.furl)
                                put("nickname", server.nickname)
                            }
                        }
                    }
                }.toString(),
            )
            }
            if (!result.ok) {
                show(FailBanner(result.message, result.next)) { openFolder(folder) }
                return@runGrid
            }
            val children = result.raw["children"]?.jsonArray?.map { el ->
                val obj = el.jsonObject
                ChildRow(
                    name = obj["name"]?.jsonPrimitive?.contentOrNull ?: "",
                    kind = obj["kind"]?.jsonPrimitive?.contentOrNull ?: "file",
                    cap = obj["cap"]?.jsonPrimitive?.contentOrNull ?: "",
                    size = obj["size"]?.jsonPrimitive?.content?.toIntOrNull() ?: 0,
                )
            } ?: emptyList()
            place = Place.Folder(folder, children)
        }
    }

    fun folderWritable(folder: FolderRef): Boolean = directoryWritable(folder.cap)

    fun visibleFiles(place: Place.Folder): List<VisibleFile> {
        writeTick
        return board.visibleFiles(place.folder.cap, place.children)
    }

    fun writeSheet(): WriteSheet? {
        writeTick
        return board.sheet
    }

    fun addTarget(): FolderRef? = (place as? Place.Folder)?.folder

    fun onFilePicked(folder: FolderRef, displayName: String, bytes: ByteArray) {
        if (!directoryWritable(folder.cap)) {
            show(FailBanner(WriteCopy.ADD_FAIL, WriteCopy.READ_ONLY), null)
            return
        }
        val name = try {
            baseName(displayName)
        } catch (_: IllegalArgumentException) {
            show(FailBanner(WriteCopy.READ_FAIL, WriteCopy.READ_NEXT), null)
            return
        }
        val dest = pendingFile(folder.cap, name)
        try {
            val free = freeBytes(dest.parentFile!!)
            if (free < bytes.size.toLong() + 4096L) {
                show(FailBanner(WriteCopy.SPACE_FAIL, WriteCopy.SPACE_NEXT)) {
                    onFilePicked(folder, displayName, bytes)
                }
                return
            }
            val parent = dest.parentFile
            if (parent != null && !parent.isDirectory) parent.mkdirs()
            dest.writeBytes(bytes)
        } catch (exc: Exception) {
            val parent = dest.parentFile
            val denied = storageDenied(exc) || parent?.canWrite() == false
            if (denied) {
                show(FailBanner(WriteCopy.PERM_FAIL, WriteCopy.PERM_NEXT)) {
                    onFilePicked(folder, displayName, bytes)
                }
            } else {
                show(FailBanner(WriteCopy.READ_FAIL, WriteCopy.READ_NEXT), null)
            }
            return
        }
        val existing = namesInFolder(folder.cap)
        when (val stage = board.stageAdd(folder.name, folder.cap, name, dest.absolutePath, bytes.size, existing)) {
            is StageAdd.Ready -> startUpload(folder, stage.name, stage.localPath, stage.size, replace = false)
            is StageAdd.NeedsChoice -> {
                rememberPendingAdds()
                touch()
            }
        }
    }

    fun replaceClash() {
        val clash = board.clashOrNull() ?: return
        board.cancelSheet()
        touch()
        val folder = folderByCap(clash.folderCap) ?: return
        startUpload(folder, clash.name, clash.localPath, clash.size, replace = true)
    }

    fun keepBothClash() {
        val clash = board.clashOrNull() ?: return
        val folder = folderByCap(clash.folderCap) ?: return
        val taken = namesInFolder(folder.cap) + clash.name
        val distinct = keepBothName(clash.name, taken)
        val dest = pendingFile(folder.cap, distinct)
        val source = File(clash.localPath)
        val bytes = source.takeIf { it.isFile }?.readBytes()
        if (bytes == null) {
            board.cancelSheet()
            rememberPendingAdds()
            show(FailBanner(WriteCopy.READ_FAIL, WriteCopy.READ_NEXT), null)
            touch()
            return
        }
        val parent = dest.parentFile
        try {
            if (parent != null && freeBytes(parent) < bytes.size.toLong() + 4096L) {
                show(FailBanner(WriteCopy.SPACE_FAIL, WriteCopy.SPACE_NEXT)) { keepBothClash() }
                touch()
                return
            }
            if (parent != null && !parent.isDirectory) parent.mkdirs()
            if (dest.absolutePath != source.absolutePath) dest.writeBytes(bytes)
        } catch (exc: Exception) {
            if (dest.absolutePath != source.absolutePath && dest.exists()) dest.delete()
            val denied = storageDenied(exc) || parent?.canWrite() == false
            val text = exc.message?.lowercase().orEmpty()
            val full = text.contains("no space left") || text.contains("enospc")
            val banner = when {
                denied -> FailBanner(WriteCopy.PERM_FAIL, WriteCopy.PERM_NEXT)
                full -> FailBanner(WriteCopy.SPACE_FAIL, WriteCopy.SPACE_NEXT)
                else -> FailBanner(WriteCopy.READ_FAIL, WriteCopy.READ_NEXT)
            }
            show(banner) { keepBothClash() }
            touch()
            return
        }
        board.cancelSheet()
        if (dest.absolutePath != source.absolutePath) source.delete()
        touch()
        startUpload(folder, distinct, dest.absolutePath, bytes.size, replace = false)
    }

    fun cancelClash() {
        val clash = board.clashOrNull() ?: return
        File(clash.localPath).delete()
        board.cancelSheet()
        rememberPendingAdds()
        touch()
    }

    fun askDiscard(name: String) {
        val folder = addTarget() ?: return
        board.askDiscard(folder.cap, name)
        touch()
    }

    fun confirmDiscard() {
        val dropped = board.confirmDiscard() ?: return
        uploads.remove(uploadKey(dropped.folderCap, dropped.name))?.cancel()
        File(dropped.localPath).delete()
        rememberPendingAdds()
        touch()
    }

    fun askRemove(name: String, cap: String) {
        val folder = addTarget() ?: return
        board.askRemove(folder.name, name, cap)
        touch()
    }

    fun cancelSheet() {
        board.cancelSheet()
        touch()
    }

    fun confirmRemove() {
        val request = board.confirmRemove() ?: return
        touch()
        val folder = addTarget() ?: return
        val current = session ?: return
        removeLanded(folder, request.name, current)
    }

    fun retryUpload(name: String) {
        val folder = addTarget() ?: return
        val pending = board.pendingFor(folder.cap).firstOrNull { it.name == name } ?: return
        val replace = serverNames(folder.cap).contains(name)
        startUpload(folder, pending.name, pending.localPath, pending.size, replace = replace)
    }

    fun openChild(row: ChildRow, parent: FolderRef) {
        if (row.kind == "dir") {
            openFolder(FolderRef(row.name, row.cap))
            return
        }
        download(row.name, row.cap, parent)
    }

    fun download(name: String, cap: String, parent: FolderRef? = null) {
        val current = session ?: return
        place = Place.Downloading(name, cap)
        gridRun.launch {
            val dest = File(downloadsDir(), safeName(name))
            val result = withContext(io) {
                try {
                    dispatch(
                        "download",
                        buildJsonObject {
                            put("cap", cap)
                            put("dest", dest.absolutePath)
                            putJsonArray("servers") {
                                for (server in current.servers) {
                                    addJsonObject {
                                        put("furl", server.furl)
                                        put("nickname", server.nickname)
                                    }
                                }
                            }
                        }.toString(),
                    )
                } catch (exc: CancellationException) {
                    throw exc
                } catch (exc: Exception) {
                    Log.w(TAG, "download failed: ${exc.javaClass.simpleName}")
                    GridResult(
                        false,
                        "could not download this file. Network error or not enough free space.",
                        downloadFailNext(exc),
                        buildJsonObject {},
                    )
                }
            }
            if (!result.ok || !dest.isFile) {
                if (dest.exists() && dest.length() == 0L) dest.delete()
                place = if (parent != null) Place.Folder(parent, (place as? Place.Folder)?.children ?: emptyList()) else Place.Folders
                show(FailBanner(result.message, result.next)) { download(name, cap, parent) }
                return@launch
            }
            place = Place.Ready(name, dest)
        }
    }

    fun cancelDownload() {
        gridRun.cancel()
        place = Place.Folders
    }

    fun openReady(file: File) {
        val context = getApplication<Application>()
        val uri = FileProvider.getUriForFile(context, context.packageName + ".files", file)
        val ext = file.extension.lowercase()
        val mime = mimeFor(ext)
        val view = Intent(Intent.ACTION_VIEW)
            .setDataAndType(uri, mime)
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        try {
            context.startActivity(Intent.createChooser(view, "Open with").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        } catch (_: ActivityNotFoundException) {
            show(
                FailBanner(
                    "could not open this file. No app on this phone accepted it.",
                    "Retry, or open the file from the Files app.",
                ),
            ) { openReady(file) }
        }
    }

    fun clearDownloads() {
        val dir = downloadsDir()
        dir.listFiles()?.forEach { it.delete() }
        show(
            FailBanner(
                "downloads on this phone were removed. Shared folders are unchanged.",
                "Download again when you need a file.",
            ),
            null,
        )
    }

    fun forgetThisPhone() {
        store.clear()
        session = null
        acknowledged = false
        inviteText = ""
        place = Place.Welcome
        fail = null
        board.clear()
        deletePendingIndex(File(filesRoot(), "leasegrid/pending-adds.json"))
        File(filesRoot(), "pending").deleteRecursively()
    }

    private fun startUpload(
        folder: FolderRef,
        name: String,
        localPath: String,
        size: Int,
        replace: Boolean,
    ) {
        val current = session ?: return
        if (current.servers.isEmpty()) {
            show(FailBanner(WriteCopy.ADD_FAIL, WriteCopy.ADD_NEXT)) {
                retryUpload(name)
            }
            val item = board.begin(folder.cap, name, localPath, size)
            board.fail(folder.cap, name, item.token)
            rememberPendingAdds()
            touch()
            return
        }
        fail = null
        retries.arm(null)
        val armed = ensureAuthor(folder)
        val existing = board.tokenOf(armed.cap, name)
        val item = if (existing == null) {
            board.begin(armed.cap, name, localPath, size)
        } else {
            board.markSending(armed.cap, name)
            board.pendingFor(armed.cap).first { it.name == name }
        }
        touch()
        val token = board.tokenOf(armed.cap, name) ?: item.token
        val key = uploadKey(armed.cap, name)
        rememberPendingAdds()
        uploads.remove(key)?.cancel()
        val upload = scope.launch {
            val ticker = launch {
                var mark = 0.12f
                while (isActive) {
                    delay(350)
                    mark = (mark + 0.08f).coerceAtMost(0.9f)
                    board.noteProgress(armed.cap, name, mark)
                    touch()
                }
            }
            val silence = launch silence@{
                delay(ADD_SILENCE_MS)
                if (board.tokenOf(armed.cap, name) != token) return@silence
                if (!board.noteSilence(armed.cap, name, token, ADD_SILENCE_MS)) return@silence
                ticker.cancel()
                touch()
                show(FailBanner(WriteCopy.ADD_FAIL, WriteCopy.ADD_NEXT)) { retryUpload(name) }
            }
            val result = withContext(io) {
                try {
                    dispatch(
                        "put",
                        buildJsonObject {
                            put("cap", armed.cap)
                            put("name", name)
                            put("path", localPath)
                            put("replace", replace)
                            put("author_seed_b64", armed.authorSeedB64)
                            put("phone_dmd", armed.phoneDmd)
                            putJsonArray("shares") {
                                for (share in armedShares(current)) add(share)
                            }
                            putJsonArray("servers") {
                                for (server in current.servers) {
                                    addJsonObject {
                                        put("furl", server.furl)
                                        put("nickname", server.nickname)
                                    }
                                }
                            }
                        }.toString(),
                    )
                } catch (exc: CancellationException) {
                    throw exc
                } catch (exc: Exception) {
                    GridResult(false, WriteCopy.ADD_FAIL, WriteCopy.ADD_NEXT, buildJsonObject {})
                }
            }
            ticker.cancel()
            silence.cancel()
            if (board.tokenOf(armed.cap, name) != token) return@launch
            if (!result.ok && result.message.contains("already in this folder")) {
                board.abandon(armed.cap, name, token)
                board.stageAdd(armed.name, armed.cap, name, localPath, size, setOf(name))
                rememberPendingAdds()
                touch()
                return@launch
            }
            if (!result.ok) {
                board.fail(armed.cap, name, token)
                rememberPendingAdds()
                touch()
                show(FailBanner(result.message, result.next)) { retryUpload(name) }
                return@launch
            }
            val dmd = result.raw["phone_dmd"]?.jsonPrimitive?.contentOrNull ?: armed.phoneDmd
            val seed = result.raw["author_seed_b64"]?.jsonPrimitive?.contentOrNull ?: armed.authorSeedB64
            rememberFolder(armed.copy(phoneDmd = dmd, authorSeedB64 = seed))
            if (!board.acknowledge(armed.cap, name, token)) return@launch
            fail = null
            retries.arm(null)
            val landedCap = result.raw["cap"]?.jsonPrimitive?.contentOrNull ?: ""
            val landedSize = result.raw["size"]?.jsonPrimitive?.content?.toIntOrNull() ?: size
            val here = place as? Place.Folder
            if (here != null && here.folder.cap == armed.cap) {
                val kept = here.children.filter { it.name != name }
                place = here.copy(
                    folder = folderByCap(armed.cap) ?: here.folder,
                    children = listOf(ChildRow(name, "file", landedCap, landedSize)) + kept,
                )
            }
            File(localPath).delete()
            rememberPendingAdds()
            touch()
            reloadIfOpen(armed)
        }
        uploads[key] = upload
    }

    private fun removeLanded(folder: FolderRef, name: String, current: Session) {
        gridRun.launch {
            val result = withContext(io) {
                try {
                    dispatch(
                        "remove",
                        buildJsonObject {
                            put("cap", folder.cap)
                            put("name", name)
                            put("phone_dmd", folder.phoneDmd)
                            putJsonArray("shares") {
                                for (share in armedShares(current)) add(share)
                            }
                            putJsonArray("servers") {
                                for (server in current.servers) {
                                    addJsonObject {
                                        put("furl", server.furl)
                                        put("nickname", server.nickname)
                                    }
                                }
                            }
                        }.toString(),
                    )
                } catch (exc: CancellationException) {
                    throw exc
                } catch (exc: Exception) {
                    GridResult(false, WriteCopy.REMOVE_FAIL, WriteCopy.REMOVE_NEXT, buildJsonObject {})
                }
            }
            if (!result.ok) {
                show(FailBanner(result.message.ifBlank { WriteCopy.REMOVE_FAIL }, result.next)) {
                    val again = addTarget() ?: folder
                    removeLanded(again, name, session ?: current)
                }
                return@launch
            }
            reloadIfOpen(folder)
        }
    }

    private fun namesInFolder(folderCap: String): Set<String> {
        val pending = board.pendingFor(folderCap).map { it.name }
        return serverNames(folderCap) + pending
    }

    private fun serverNames(folderCap: String): Set<String> {
        val here = place as? Place.Folder ?: return emptySet()
        if (here.folder.cap != folderCap) return emptySet()
        return here.children.map { it.name }.toSet()
    }

    private fun folderByCap(cap: String): FolderRef? =
        session?.folders?.firstOrNull { it.cap == cap }

    private fun ensureAuthor(folder: FolderRef): FolderRef {
        if (folder.authorSeedB64.isNotBlank()) return folder
        val seed = ByteArray(32)
        SecureRandom().nextBytes(seed)
        val next = folder.copy(authorSeedB64 = Base64.encodeToString(seed, Base64.NO_WRAP))
        rememberFolder(next)
        return next
    }

    private fun rememberFolder(folder: FolderRef) {
        val current = session ?: return
        val next = current.copy(
            folders = current.folders.map { existing ->
                if (existing.cap == folder.cap) {
                    existing.copy(phoneDmd = folder.phoneDmd, authorSeedB64 = folder.authorSeedB64)
                } else {
                    existing
                }
            },
        )
        store.save(next)
        session = next
        val here = place
        if (here is Place.Folder && here.folder.cap == folder.cap) {
            val updated = next.folders.firstOrNull { it.cap == folder.cap } ?: return
            place = here.copy(folder = updated)
        }
    }

    private fun reloadIfOpen(folder: FolderRef) {
        val here = place as? Place.Folder ?: return
        if (here.folder.cap != folder.cap) return
        val fresh = folderByCap(folder.cap) ?: folder
        openFolder(fresh)
    }

    private fun armedShares(current: Session): List<Int> {
        val shares = current.shares
        return if (shares.size >= 3) shares.take(3) else listOf(2, 3, 3)
    }

    private fun pendingFile(folderCap: String, name: String): File {
        val dir = File(testFilesDir ?: getApplication<Application>().filesDir, "pending")
        val bucket = File(dir, Integer.toHexString(folderCap.hashCode()))
        bucket.mkdirs()
        return File(bucket, safeName(name))
    }

    private fun baseName(name: String): String {
        val cleaned = name.replace('\\', '/').substringAfterLast('/').replace("\u0000", "").trim()
        if (cleaned.isBlank() || cleaned == "." || cleaned == "..") {
            throw IllegalArgumentException("name")
        }
        return cleaned.take(180)
    }

    private fun uploadKey(folderCap: String, name: String) = "$folderCap\n$name"

    private fun touch() {
        writeTick += 1
    }

    private fun downloadsDir(): File {
        testFilesDir?.let { return File(it, "Download").apply { mkdirs() } }
        val context = getApplication<Application>()
        val ext = context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS)
        val dir = ext ?: File(context.filesDir, "Download")
        dir.mkdirs()
        return dir
    }

    /**
     * Short-code handshake. The relay address stays in the Python entry point.
     * A thrown failure becomes relay. Cancellation closes the attempt and escapes.
     */
    private suspend fun redeem(code: String): RedeemOutcome {
        redeeming = true
        try {
            val result = try {
                withContext(io) {
                    dispatch("redeem", buildJsonObject {
                        put("code", code)
                        put("timeout", 120)
                    }.toString())
                }
            } catch (exc: CancellationException) {
                throw exc
            } catch (exc: Exception) {
                Log.w(TAG, "redeem failed: ${exc.javaClass.simpleName}")
                return RedeemOutcome("relay")
            }
            // Leave already cancelled this attempt. Do not learn an address that arrived late.
            coroutineContext.ensureActive()
            val status = result.raw["status"]?.jsonPrimitive?.contentOrNull
            if (result.ok && status == "ok") {
                val furl = result.raw["furl"]?.jsonPrimitive?.contentOrNull ?: ""
                return RedeemOutcome("ok", furl, Invite.keptShares(shareCounts(result.raw)))
            }
            return RedeemOutcome(
                when (status) {
                    "expired", "rejected", "relay", "timeout" -> status
                    else -> "relay"
                },
            )
        } finally {
            redeeming = false
        }
    }

    /** Ask the handshake to stop. Safe when nothing is open. */
    private fun abandonRedeem() {
        try {
            dispatch("redeem-cancel", "{}")
        } catch (exc: Exception) {
            Log.w(TAG, "redeem cancel failed: ${exc.javaClass.simpleName}")
        }
    }

    private fun shareCounts(raw: JsonObject): List<Int>? {
        val arr = raw["shares"]?.jsonArray ?: return null
        val nums = ArrayList<Int>(arr.size)
        for (el in arr) {
            val text = try {
                el.jsonPrimitive.contentOrNull
            } catch (_: Exception) {
                return null
            } ?: return null
            val number = text.toIntOrNull() ?: return null
            nums.add(number)
        }
        return nums
    }

    override fun onCleared() {
        val stop = redeeming
        gridRun.cancel()
        if (stop) abandonRedeem()
        super.onCleared()
    }

    /** Null on any failure. Never shows a banner: SessionFlow owns the copy (#50). */
    private suspend fun learn(furl: String): List<ServerRef>? {
        val result = try {
            withContext(io) {
                dispatch("learn", buildJsonObject {
                    put("furl", furl)
                    put("timeout", 25)
                }.toString())
            }
        } catch (exc: CancellationException) {
            // A cancelled join must not paint JOIN_FAILED over a newer attempt.
            throw exc
        } catch (exc: Exception) {
            // Raw error to the log only, never on screen (#50).
            Log.w(TAG, "learn failed: ${exc.javaClass.simpleName}")
            return null
        }
        if (!result.ok) {
            Log.w(TAG, "learn failed: ${result.message}")
            return null
        }
        val servers = result.raw["servers"]?.jsonArray?.map { el ->
            val obj = el.jsonObject
            ServerRef(
                furl = obj["furl"]?.jsonPrimitive?.contentOrNull ?: "",
                nickname = obj["nickname"]?.jsonPrimitive?.contentOrNull ?: "",
            )
        }?.filter { it.furl.startsWith("pb://") } ?: emptyList()
        return servers
    }

    private fun dispatch(op: String, payload: String): GridResult {
        val raw = gridDispatch(op, payload)
        val ok = raw["ok"]?.jsonPrimitive?.contentOrNull == "true" ||
            raw["ok"]?.toString() == "true"
        val message = raw["message"]?.jsonPrimitive?.contentOrNull
            ?: "could not complete that."
        val next = raw["next"]?.jsonPrimitive?.contentOrNull ?: "Retry."
        return GridResult(ok, message, next, raw)
    }

    private fun runGrid(label: String, block: suspend () -> Unit) {
        gridRun.launch(onError = { exc ->
            Log.w(TAG, "grid failed: ${exc.javaClass.simpleName}")
            show(unexpectedGridCard(exc)) { runGrid(label, block) }
        }, block)
    }

    private fun mimeFor(ext: String): String = when (ext) {
        "txt", "md", "csv" -> "text/plain"
        "jpg", "jpeg" -> "image/jpeg"
        "png" -> "image/png"
        "gif" -> "image/gif"
        "pdf" -> "application/pdf"
        "json" -> "application/json"
        "mp4" -> "video/mp4"
        "mp3" -> "audio/mpeg"
        else -> "application/octet-stream"
    }

    private fun show(banner: FailBanner, again: (() -> Unit)?) {
        fail = banner
        retries.arm(again)
    }

    private fun safeName(name: String): String {
        val cleaned = name.replace(Regex("[\\\\/]+"), "_").replace("\u0000", "")
        return if (cleaned.isBlank()) "download.bin" else cleaned.take(120)
    }

    private fun filesRoot(): File = testFilesDir ?: getApplication<Application>().filesDir

    private fun storageDenied(exc: Exception): Boolean {
        if (exc is SecurityException) return true
        if (exc is java.nio.file.AccessDeniedException) return true
        val text = exc.message?.lowercase().orEmpty()
        return text.contains("permission denied") || text.contains("eacces")
    }

    private fun pendingIndex(): File = File(filesRoot(), "leasegrid/pending-adds.json")

    private fun rememberPendingAdds() {
        val root = filesRoot()
        val rows = board.allPending().mapNotNull { item ->
            val rel = relativeInside(root, File(item.localPath)) ?: return@mapNotNull null
            buildJsonObject {
                put("folderCap", item.folderCap)
                put("name", item.name)
                put("size", item.size)
                put("path", rel)
            }
        }
        val clash = board.clashOrNull()
        val clashRel = clash?.let { relativeInside(root, File(it.localPath)) }
        val dest = pendingIndex()
        if (rows.isEmpty() && clashRel == null) {
            deletePendingIndex(dest)
            return
        }
        dest.parentFile?.mkdirs()
        writePendingIndex(
            dest,
            buildJsonObject {
                putJsonArray("rows") {
                    for (row in rows) add(row)
                }
                if (clash != null && clashRel != null) {
                    put("clash", buildJsonObject {
                        put("folder", clash.folder)
                        put("folderCap", clash.folderCap)
                        put("name", clash.name)
                        put("size", clash.size)
                        put("path", clashRel)
                    })
                }
            }.toString(),
        )
    }

    private fun restorePendingAdds() {
        val dest = pendingIndex()
        val temp = File(dest.parentFile, dest.name + ".tmp")
        // A temp is an unfinished replace. The index already on disk is the last complete copy.
        if (dest.isFile) temp.delete()
        if (!dest.isFile) return
        val rootObj = try {
            json.parseToJsonElement(dest.readText()).jsonObject
        } catch (_: Exception) {
            return
        }
        val rows = rootObj["rows"]?.jsonArray
        val root = filesRoot()
        val base = try {
            root.canonicalFile
        } catch (_: IOException) {
            return
        }
        val kept = mutableListOf<kotlinx.serialization.json.JsonObject>()
        if (rows != null) {
            for (el in rows) {
                val obj = el as? kotlinx.serialization.json.JsonObject ?: continue
                val cap = obj["folderCap"]?.jsonPrimitive?.contentOrNull ?: continue
                val name = obj["name"]?.jsonPrimitive?.contentOrNull ?: continue
                val size = obj["size"]?.jsonPrimitive?.content?.toIntOrNull() ?: continue
                val rel = obj["path"]?.jsonPrimitive?.contentOrNull ?: continue
                val file = fileInside(base, rel) ?: continue
                board.restoreFailed(cap, name, file.absolutePath, size)
                kept.add(obj)
            }
        }
        val clashEl = rootObj["clash"] as? kotlinx.serialization.json.JsonObject
        val clashOk = clashEl == null || restoreClashElement(clashEl, base)
        val rowsSame = rows == null || kept.size == rows.size
        if (rowsSame && clashOk) return
        rememberPendingAdds()
    }

    /** A clash path outside the phone files dir is dropped. It is not opened and not uploaded. */
    private fun restoreClashElement(obj: kotlinx.serialization.json.JsonObject, base: File): Boolean {
        val folder = obj["folder"]?.jsonPrimitive?.contentOrNull ?: return false
        val cap = obj["folderCap"]?.jsonPrimitive?.contentOrNull ?: return false
        val name = obj["name"]?.jsonPrimitive?.contentOrNull ?: return false
        val size = obj["size"]?.jsonPrimitive?.content?.toIntOrNull() ?: return false
        val rel = obj["path"]?.jsonPrimitive?.contentOrNull ?: return false
        val file = fileInside(base, rel) ?: return false
        board.restoreClash(folder, cap, name, file.absolutePath, size)
        return board.clashOrNull() != null
    }

    private fun fileInside(base: File, rel: String): File? {
        if (rel.startsWith("/") || rel.split("/", "\\").contains("..")) return null
        val file = try {
            File(base, rel).canonicalFile
        } catch (_: IOException) {
            return null
        }
        val path = file.path
        val rootPath = base.path
        if (path != rootPath && !path.startsWith(rootPath + File.separator)) return null
        if (!file.isFile) return null
        return file
    }

    private fun relativeInside(root: File, file: File): String? {
        val base = try {
            root.canonicalFile
        } catch (_: IOException) {
            return null
        }
        val target = try {
            file.canonicalFile
        } catch (_: IOException) {
            return null
        }
        val rel = try {
            target.relativeTo(base).path
        } catch (_: IllegalArgumentException) {
            return null
        }
        if (rel == ".." || rel.startsWith(".." + File.separator)) return null
        return rel
    }
}

private data class GridResult(
    val ok: Boolean,
    val message: String,
    val next: String,
    val raw: kotlinx.serialization.json.JsonObject,
)
