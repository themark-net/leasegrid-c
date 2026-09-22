package net.themark.leasegrid.sync

/**
 * Debug dogfood hooks. Filling an invite this way does not acknowledge the
 * threat checkbox. Join stays disabled until that box is checked.
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
}
