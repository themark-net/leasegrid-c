package net.themark.leasegrid.sync.ui

import android.app.Application
import android.content.ActivityNotFoundException
import android.content.Intent
import android.os.Environment
import android.os.StatFs
import android.util.Base64
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.FileProvider
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.security.SecureRandom
import kotlinx.serialization.json.Json
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
import net.themark.leasegrid.sync.recovery.IMPORT_FAIL_MSG
import net.themark.leasegrid.sync.recovery.IMPORT_FAIL_NEXT
import net.themark.leasegrid.sync.recovery.ImportFail
import net.themark.leasegrid.sync.recovery.RecoveryCodec
import net.themark.leasegrid.sync.session.FolderRef
import net.themark.leasegrid.sync.session.ServerRef
import net.themark.leasegrid.sync.session.Session
import net.themark.leasegrid.sync.session.SessionStore
import java.io.File

data class FailBanner(val message: String, val next: String)

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

class AppModel(app: Application) : AndroidViewModel(app) {
    private val store = SessionStore(File(app.filesDir, "leasegrid"))
    private val grid = AndroidGrid(app)
    private val json = Json { ignoreUnknownKeys = true }
    private var job: Job? = null
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

    private var retry: (() -> Unit)? = null

    init {
        val existing = store.load()
        if (existing != null) {
            session = existing
            place = Place.Folders
        }
    }

    fun joinEnabled(): Boolean = Invite.joinEnabled(acknowledged, inviteText)

    fun goWelcome() {
        fail = null
        place = Place.Welcome
    }

    fun goImport() {
        fail = null
        place = Place.Import
    }

    /** Drop any joined home and show Import before the recovery file is read. */
    fun beginRecoveryImport() {
        store.clear()
        session = null
        pickedName = ""
        pickedBytes = null
        passphrase = ""
        fail = null
        busy = false
        place = Place.Import
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

    fun dismissFail() {
        fail = null
        retry = null
    }

    /** In-app FAIL. Does not write a session. [again] is the Retry action. */
    fun reportFail(message: String, next: String, again: (() -> Unit)? = null) {
        show(FailBanner(message, next), again)
    }

    fun retryFail() {
        val action = retry
        fail = null
        action?.invoke()
    }

    fun join() {
        if (!acknowledged) {
            show(FailBanner(Invite.ACK_MSG, Invite.ACK_NEXT)) { join() }
            return
        }
        val text = inviteText
        runGrid("Joining…") {
            val parsed = try {
                Invite.parse(text)
            } catch (exc: InviteFail) {
                show(FailBanner(exc.banner, exc.next)) { join() }
                return@runGrid
            }
            val learned = learn(parsed.furl)
            if (learned == null) return@runGrid
            val next = Session(
                introducerFurl = parsed.furl,
                shares = parsed.shares ?: listOf(2, 3, 3),
                folders = session?.folders ?: emptyList(),
                servers = learned,
            )
            store.save(next)
            session = next
            place = Place.Folders
        }
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
                withContext(Dispatchers.IO) { RecoveryCodec.decode(bytes, phrase) }
            } catch (exc: ImportFail) {
                show(FailBanner(exc.banner, exc.next)) { importRecovery() }
                return@runGrid
            }
            val learned = learn(bundle.introducerFurl, fatal = false)
            val next = Session(
                introducerFurl = bundle.introducerFurl,
                nickname = bundle.nickname,
                shares = bundle.shares,
                folders = bundle.folders.map { FolderRef(it.name, it.collective) },
                servers = learned ?: session?.servers ?: emptyList(),
            )
            store.save(next)
            session = next
            place = Place.Folders
            if (learned == null) {
                show(
                    FailBanner(
                        "could not reach the introducer yet. Folder names are on this phone.",
                        "check the network path to the introducer; Retry.",
                    ),
                ) { refresh() }
            }
        }
    }

    fun refresh() {
        val current = session ?: return
        runGrid("Refreshing…") {
            val learned = learn(current.introducerFurl) ?: return@runGrid
            val next = current.copy(servers = learned)
            store.save(next)
            session = next
            place = Place.Folders
        }
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
            val result = withContext(Dispatchers.IO) {
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
            show(FailBanner(WriteCopy.READ_FAIL, WriteCopy.READ_NEXT)) { }
            return
        }
        val dest = pendingFile(folder.cap, name)
        try {
            val free = StatFs(dest.parentFile!!.absolutePath).availableBytes
            if (free < bytes.size.toLong() + 4096L) {
                show(FailBanner(WriteCopy.SPACE_FAIL, WriteCopy.SPACE_NEXT)) { }
                return
            }
            dest.parentFile?.mkdirs()
            dest.writeBytes(bytes)
        } catch (_: Exception) {
            show(FailBanner(WriteCopy.READ_FAIL, WriteCopy.READ_NEXT)) { }
            return
        }
        val existing = namesInFolder(folder.cap)
        when (val stage = board.stageAdd(folder.name, folder.cap, name, dest.absolutePath, bytes.size, existing)) {
            is StageAdd.Ready -> startUpload(folder, stage.name, stage.localPath, stage.size, replace = false)
            is StageAdd.NeedsChoice -> touch()
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
        board.cancelSheet()
        val folder = folderByCap(clash.folderCap) ?: return
        val taken = namesInFolder(folder.cap)
        val distinct = keepBothName(clash.name, taken)
        val dest = pendingFile(folder.cap, distinct)
        val bytes = File(clash.localPath).takeIf { it.isFile }?.readBytes()
        if (bytes == null) {
            show(FailBanner(WriteCopy.READ_FAIL, WriteCopy.READ_NEXT)) { }
            touch()
            return
        }
        dest.parentFile?.mkdirs()
        dest.writeBytes(bytes)
        if (dest.absolutePath != clash.localPath) File(clash.localPath).delete()
        touch()
        startUpload(folder, distinct, dest.absolutePath, bytes.size, replace = false)
    }

    fun cancelClash() {
        val clash = board.clashOrNull() ?: return
        File(clash.localPath).delete()
        board.cancelSheet()
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
        job?.cancel()
        job = viewModelScope.launch {
            busy = true
            fail = null
            val dest = File(downloadsDir(), safeName(name))
            val result = withContext(Dispatchers.IO) {
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
                    GridResult(
                        false,
                        "could not download this file. Network error or not enough free space.",
                        "check network / free space; Retry. (${exc.javaClass.simpleName})",
                        buildJsonObject {},
                    )
                }
            }
            busy = false
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
        job?.cancel()
        busy = false
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
                "downloads on this phone were removed. Folders on the friendnet are unchanged.",
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
            touch()
            return
        }
        fail = null
        retry = null
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
        uploads.remove(key)?.cancel()
        val upload = viewModelScope.launch {
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
            val result = withContext(Dispatchers.IO) {
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
                touch()
                return@launch
            }
            if (!result.ok) {
                board.fail(armed.cap, name, token)
                touch()
                show(FailBanner(result.message, result.next)) { retryUpload(name) }
                return@launch
            }
            val dmd = result.raw["phone_dmd"]?.jsonPrimitive?.contentOrNull ?: armed.phoneDmd
            val seed = result.raw["author_seed_b64"]?.jsonPrimitive?.contentOrNull ?: armed.authorSeedB64
            rememberFolder(armed.copy(phoneDmd = dmd, authorSeedB64 = seed))
            if (!board.acknowledge(armed.cap, name, token)) return@launch
            fail = null
            retry = null
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
            touch()
            reloadIfOpen(armed)
        }
        uploads[key] = upload
    }

    private fun removeLanded(folder: FolderRef, name: String, current: Session) {
        job?.cancel()
        job = viewModelScope.launch {
            busy = true
            val result = withContext(Dispatchers.IO) {
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
            busy = false
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
        val dir = File(getApplication<Application>().filesDir, "pending")
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
        val context = getApplication<Application>()
        val ext = context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS)
        val dir = ext ?: File(context.filesDir, "Download")
        dir.mkdirs()
        return dir
    }

    private suspend fun learn(furl: String, fatal: Boolean = true): List<ServerRef>? {
        val result = try {
            withContext(Dispatchers.IO) {
                dispatch("learn", buildJsonObject {
                    put("furl", furl)
                    put("timeout", 25)
                }.toString())
            }
        } catch (exc: Exception) {
            if (fatal) {
                show(
                    FailBanner(
                        "could not join this friendnet. Introducer is unreachable.",
                        "check the network path to the introducer (and that it is running); Retry. (${exc.javaClass.simpleName})",
                    ),
                ) { refresh() }
            }
            return null
        }
        if (!result.ok) {
            if (fatal) show(FailBanner(result.message, result.next)) { refresh() }
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
        val raw = grid.dispatch(op, payload)
        val ok = raw["ok"]?.jsonPrimitive?.contentOrNull == "true" ||
            raw["ok"]?.toString() == "true"
        val message = raw["message"]?.jsonPrimitive?.contentOrNull
            ?: "could not complete that."
        val next = raw["next"]?.jsonPrimitive?.contentOrNull ?: "Retry."
        return GridResult(ok, message, next, raw)
    }

    private fun runGrid(label: String, block: suspend () -> Unit) {
        job?.cancel()
        job = viewModelScope.launch {
            busy = true
            fail = null
            try {
                block()
            } catch (exc: CancellationException) {
                throw exc
            } catch (exc: Exception) {
                show(
                    FailBanner(
                        "could not complete that. ${exc.javaClass.simpleName}",
                        "Retry. If it repeats, check the network and the invite.",
                    ),
                ) { }
            } finally {
                busy = false
            }
        }
        if (label.isEmpty()) return
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
        retry = again
    }

    private fun safeName(name: String): String {
        val cleaned = name.replace(Regex("[\\\\/]+"), "_").replace("\u0000", "")
        return if (cleaned.isBlank()) "download.bin" else cleaned.take(120)
    }
}

private data class GridResult(
    val ok: Boolean,
    val message: String,
    val next: String,
    val raw: kotlinx.serialization.json.JsonObject,
)
