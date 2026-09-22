package net.themark.leasegrid.sync.ui

import android.app.Application
import android.content.ActivityNotFoundException
import android.content.Intent
import android.os.Environment
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.FileProvider
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
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
