package net.themark.leasegrid.sync

import java.io.File

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

    fun recoveryFile(filesDir: File, raw: String): File {
        val trimmed = raw.trim()
        return if (trimmed.startsWith("/")) File(trimmed) else File(filesDir, trimmed)
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
