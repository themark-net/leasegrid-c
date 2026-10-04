package net.themark.leasegrid.sync.ui

/**
 * Slice B write rules for the folder that is already open.
 * Docs: design/55–59. The chip cannot say On friendnet before acknowledge.
 */
object WriteCopy {
    const val PENDING = "Not on friendnet yet"
    const val LANDED = "On friendnet"
    const val ADD = "Add file"
    const val READ_ONLY =
        "You can download from this folder. Adding files is not available here."
    const val ADD_FAIL = "could not add this file."
    const val ADD_NEXT = "check network; Retry."
    const val READ_FAIL = "could not read this file."
    const val READ_NEXT = "pick it again."
    const val SPACE_FAIL = "not enough free space."
    const val SPACE_NEXT = "free space; Retry."
    const val REMOVE_FAIL = "could not remove this file."
    const val REMOVE_NEXT = "Retry."
    const val CLASH_NEXT = "Choose Replace, Keep both, or Cancel."
    const val DESKTOP_FOLDERS =
        "New folders are still added in Leasegrid Sync on your computer."
}

fun directoryWritable(cap: String): Boolean {
    val text = cap.trim()
    return text.startsWith("URI:DIR2:") && !text.startsWith("URI:DIR2-")
}

fun keepBothName(name: String, taken: Set<String>): String {
    val dot = name.lastIndexOf('.')
    val stem: String
    val ext: String
    if (dot > 0) {
        stem = name.substring(0, dot)
        ext = name.substring(dot)
    } else {
        stem = name
        ext = ""
    }
    var candidate = "$stem (phone)$ext"
    var number = 2
    while (candidate in taken) {
        candidate = "$stem (phone $number)$ext"
        number += 1
        if (number > 50) error("could not add this file.")
    }
    return candidate
}

fun formatByteSize(size: Int): String {
    if (size < 1024) return "$size bytes"
    val kb = size / 1024.0
    if (kb < 1024) {
        return if (kb < 10) String.format("%.1f KB", kb) else "${kb.toInt()} KB"
    }
    return String.format("%.1f MB", kb / 1024.0)
}

enum class Chip { Pending, Landed }

data class VisibleFile(
    val name: String,
    val chip: Chip,
    val size: Int,
    val cap: String = "",
    val kind: String = "file",
    val progress: Float = 0f,
    val failed: Boolean = false,
    val localPath: String = "",
)

fun chipText(row: VisibleFile): String = when (row.chip) {
    Chip.Pending -> WriteCopy.PENDING
    Chip.Landed -> WriteCopy.LANDED
}

sealed class WriteSheet {
    data class Clash(
        val folder: String,
        val folderCap: String,
        val name: String,
        val localPath: String,
        val size: Int,
    ) : WriteSheet()

    data class Remove(val folder: String, val name: String, val cap: String) : WriteSheet()

    data class Discard(val folderCap: String, val name: String) : WriteSheet()
}

data class PendingFile(
    val folderCap: String,
    val name: String,
    val localPath: String,
    val size: Int,
    val progress: Float = 0.05f,
    val failed: Boolean = false,
    val token: Long = 0L,
)

sealed class StageAdd {
    data class Ready(val name: String, val localPath: String, val size: Int) : StageAdd()
    data class NeedsChoice(val sheet: WriteSheet.Clash) : StageAdd()
}

/**
 * Pending rows stay Not on friendnet yet until [acknowledge].
 * Discard drops a pending row. Remove is a separate confirm for a landed file.
 */
class FolderWriteBoard {
    private val pending = linkedMapOf<String, PendingFile>()
    var sheet: WriteSheet? = null
        private set
    private var tokens = 1L

    fun pendingFor(folderCap: String): List<PendingFile> =
        pending.values.filter { it.folderCap == folderCap }

    fun visibleFiles(folderCap: String, server: List<ChildRow>): List<VisibleFile> {
        val mine = pending.values.filter { it.folderCap == folderCap }
        val hidden = mine.map { it.name }.toSet()
        val pendingRows = mine.map { item ->
            VisibleFile(
                name = item.name,
                chip = Chip.Pending,
                size = item.size,
                progress = item.progress,
                failed = item.failed,
                localPath = item.localPath,
            )
        }
        val landed = server.map { row ->
            if (row.kind == "dir") {
                VisibleFile(name = row.name, chip = Chip.Landed, size = row.size, cap = row.cap, kind = "dir")
            } else {
                VisibleFile(
                    name = row.name,
                    chip = Chip.Landed,
                    size = row.size,
                    cap = row.cap,
                    kind = "file",
                )
            }
        }.filter { it.kind == "dir" || it.name !in hidden }
        return pendingRows + landed
    }

    fun stageAdd(
        folderName: String,
        folderCap: String,
        name: String,
        localPath: String,
        size: Int,
        existing: Set<String>,
    ): StageAdd {
        if (name in existing || pending.contains(key(folderCap, name))) {
            val clash = WriteSheet.Clash(folderName, folderCap, name, localPath, size)
            sheet = clash
            return StageAdd.NeedsChoice(clash)
        }
        return StageAdd.Ready(name, localPath, size)
    }

    fun begin(folderCap: String, name: String, localPath: String, size: Int): PendingFile {
        val item = PendingFile(
            folderCap = folderCap,
            name = name,
            localPath = localPath,
            size = size,
            progress = 0.05f,
            failed = false,
            token = tokens++,
        )
        pending[key(folderCap, name)] = item
        return item
    }

    fun markSending(folderCap: String, name: String) {
        val item = pending[key(folderCap, name)] ?: return
        pending[key(folderCap, name)] = item.copy(failed = false, progress = 0.05f)
    }

    fun noteProgress(folderCap: String, name: String, progress: Float) {
        val item = pending[key(folderCap, name)] ?: return
        val capped = progress.coerceIn(0f, 0.9f)
        pending[key(folderCap, name)] = item.copy(progress = capped)
    }

    /** Drops a pending row that never landed. Not a friendnet remove. */
    fun abandon(folderCap: String, name: String, token: Long): Boolean {
        val item = pending[key(folderCap, name)] ?: return false
        if (item.token != token) return false
        pending.remove(key(folderCap, name))
        return true
    }

    /** Drops the pending row. Only the server listing may then say On friendnet. */
    fun acknowledge(folderCap: String, name: String, token: Long): Boolean {
        val item = pending[key(folderCap, name)] ?: return false
        if (item.token != token) return false
        pending.remove(key(folderCap, name))
        return true
    }

    fun fail(folderCap: String, name: String, token: Long) {
        val item = pending[key(folderCap, name)] ?: return
        if (item.token != token) return
        pending[key(folderCap, name)] = item.copy(failed = true, progress = item.progress.coerceAtMost(0.9f))
    }

    fun tokenOf(folderCap: String, name: String): Long? = pending[key(folderCap, name)]?.token

    fun askDiscard(folderCap: String, name: String) {
        if (!pending.containsKey(key(folderCap, name))) return
        sheet = WriteSheet.Discard(folderCap, name)
    }

    /** Local only. Does not describe a friendnet delete. */
    fun confirmDiscard(): PendingFile? {
        val discard = sheet as? WriteSheet.Discard ?: return null
        sheet = null
        return pending.remove(key(discard.folderCap, discard.name))
    }

    fun askRemove(folder: String, name: String, cap: String) {
        sheet = WriteSheet.Remove(folder, name, cap)
    }

    fun confirmRemove(): WriteSheet.Remove? {
        val remove = sheet as? WriteSheet.Remove ?: return null
        sheet = null
        return remove
    }

    fun cancelSheet() {
        sheet = null
    }

    fun clashOrNull(): WriteSheet.Clash? = sheet as? WriteSheet.Clash

    private fun key(folderCap: String, name: String) = "$folderCap\n$name"
}
