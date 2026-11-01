package net.themark.leasegrid.sync

import java.io.File
import java.io.IOException

/**
 * Debug dogfood hooks. Filling an invite this way does not acknowledge the
 * threat checkbox. Join stays disabled until that box is checked.
 * A recovery extra always opens Import, even when the file is not readable yet.
 */
object DogfoodIntents {
    const val EXTRA_INVITE = "net.themark.leasegrid.sync.EXTRA_INVITE"
    const val EXTRA_RECOVERY_FILE = "net.themark.leasegrid.sync.EXTRA_RECOVERY_FILE"
    const val QUERY_INVITE = "invite"

    fun inviteText(extra: String?, queryInvite: String?): String? {
        val fromExtra = extra?.trim().orEmpty()
        if (fromExtra.isNotEmpty()) return fromExtra
        val fromQuery = queryInvite?.trim().orEmpty()
        return fromQuery.ifEmpty { null }
    }

    /** Identity of the dogfood payload. Same Intent object with new extras must re-apply. */
    fun deliveryKey(action: String?, inviteExtra: String?, recoveryExtra: String?, data: String?): String {
        return listOf(
            action?.trim().orEmpty(),
            inviteExtra?.trim().orEmpty(),
            recoveryExtra?.trim().orEmpty(),
            data?.trim().orEmpty(),
        ).joinToString("\u0000")
    }

    fun shouldDeliver(previousKey: String?, nextKey: String): Boolean = previousKey != nextKey

    /** A recovery extra always opens Import. A missing file still must not stay on Welcome. */
    fun opensImport(recoveryExtra: String?): Boolean = !recoveryExtra?.trim().isNullOrEmpty()

    const val RECOVERY_MISS_BANNER = "could not import this recovery key. The file could not be read."
    const val RECOVERY_MISS_NEXT = "check the path and storage permission; Retry."
    const val RECOVERY_REJECT_BANNER =
        "could not import this recovery key. That path is not in the app files folder."
    const val RECOVERY_REJECT_NEXT =
        "pass a file name in the app files folder, or a full path; Retry."

    /**
     * Path DogfoodIntents will read for [raw].
     * An absolute path is used as given. A relative path must stay inside [filesDir].
     * A path that leaves that directory returns a file that is not the outside target.
     */
    fun recoveryFile(filesDir: File, raw: String): File {
        return locateRecovery(filesDir, raw.trim()) ?: File(filesDir, "rejected-recovery")
    }

    /**
     * First-load result for EXTRA_RECOVERY_FILE.
     * Non-null [bytes] is what enables import confirm. [rejected] is not retried as a read.
     */
    class RecoveryLoad(
        val opensImport: Boolean,
        val rejected: Boolean,
        val name: String,
        val bytes: ByteArray?,
        val banner: String?,
        val next: String?,
    )

    fun loadRecoveryExtra(filesDir: File, raw: String?): RecoveryLoad {
        val trimmed = raw?.trim().orEmpty()
        if (trimmed.isEmpty()) {
            return RecoveryLoad(false, false, "", null, null, null)
        }
        val located = locateRecovery(filesDir, trimmed)
        if (located == null) {
            return RecoveryLoad(
                true,
                true,
                "recovery.leasegrid-recovery",
                null,
                RECOVERY_REJECT_BANNER,
                RECOVERY_REJECT_NEXT,
            )
        }
        val seed = readRecoverySeed(located)
        if (seed.readable && seed.bytes != null) {
            return RecoveryLoad(true, false, seed.name, seed.bytes, null, null)
        }
        val name = seed.name.ifBlank { "recovery.leasegrid-recovery" }
        return RecoveryLoad(true, false, name, null, RECOVERY_MISS_BANNER, RECOVERY_MISS_NEXT)
    }

    /** Null when [trimmed] is relative and its canonical path leaves [filesDir]. */
    fun locateRecovery(filesDir: File, trimmed: String): File? {
        if (trimmed.isEmpty() || trimmed.indexOf('\u0000') >= 0) return null
        if (trimmed.startsWith("/")) return File(trimmed)
        val base = try {
            filesDir.canonicalFile
        } catch (_: IOException) {
            return null
        }
        val resolved = try {
            File(base, trimmed).canonicalFile
        } catch (_: IOException) {
            return null
        }
        val root = base.path
        val path = resolved.path
        if (path != root && !path.startsWith(root + File.separator)) return null
        return resolved
    }

    data class RecoverySeed(val readable: Boolean, val name: String, val bytes: ByteArray?)

    fun readRecoverySeed(file: File): RecoverySeed {
        return try {
            if (!file.isFile) return RecoverySeed(false, file.name, null)
            val bytes = file.readBytes()
            if (bytes.isEmpty()) RecoverySeed(false, file.name, null)
            else RecoverySeed(true, file.name, bytes)
        } catch (_: Exception) {
            RecoverySeed(false, file.name, null)
        }
    }
}
