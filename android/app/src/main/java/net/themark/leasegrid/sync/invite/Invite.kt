package net.themark.leasegrid.sync.invite

data class ParsedInvite(
    val kind: String,
    val furl: String,
    val shares: List<Int>? = null,
)

class InviteFail(val banner: String, val next: String) : Exception(banner)

object Invite {
    // A real short code is a few words. Pastes longer than this are not one.
    // The old regex overflowed the stack on a few KB of "-a" groups (#78).
    private const val SHORT_CODE_MAX = 256

    // Foolscap swissnums are longer than this. The fixture swissnumswiss is 13
    // and must still parse. Empty and cut-short values are an incomplete link (#80 F1).
    private const val MIN_SWISSNUM = 8

    const val ACK_MSG = "Read the four points above first."
    const val ACK_NEXT = "check “I understand the four points above.”, then Join."

    // Desktop labels, exact (src/leasegrid_sync/app.py). Pinned once here;
    // tests/test_android_invite_copy.py checks both against the desktop widgets.
    const val SHARE_INVITE = "Share invite"
    const val SHOW_FULL_JOIN_LINK = "Show full join link (advanced)"

    // Parse fails (empty, short code, garbage, web URL, no address, malformed)
    // show no Next line (#50, Design). A failed learn() shows JOIN_FAILED_NEXT.
    const val NO_NEXT = ""

    // Also the Join button label (Design, #50).
    const val TITLE = "Join a shared folder"
    const val BODY =
        "On your computer, click $SHARE_INVITE in Leasegrid Sync and tick $SHOW_FULL_JOIN_LINK. Copy that link and paste it below."
    const val INPUT_HINT = "Paste the full join link"
    const val EMPTY_MSG = "Paste the join link first."
    const val WORMHOLE_MSG =
        "That's a short code. This phone can't use short codes yet. On your computer, tick $SHOW_FULL_JOIN_LINK, then paste that link here."
    const val GARBAGE_MSG =
        "That isn't a join link. On your computer, tick $SHOW_FULL_JOIN_LINK, then copy and paste the whole link."
    const val WEB_URL_MSG =
        "That's the Sync web page address, not a join link. On your computer, tick $SHOW_FULL_JOIN_LINK and paste that link here."
    const val NO_ADDRESS_MSG =
        "That link is missing your computer's address. On your computer, tick $SHOW_FULL_JOIN_LINK, then copy and paste the whole link."
    const val MALFORMED_MSG =
        "That join link is incomplete. On your computer, tick $SHOW_FULL_JOIN_LINK, then copy and paste the whole link."

    // Any learn() failure (unreachable, timeout, or a rejected link: the grid
    // reports them all the same way). The raw error never reaches the screen.
    const val JOIN_FAILED = "Couldn't reach your computer."
    const val JOIN_FAILED_NEXT =
        "Check that Leasegrid Sync is open on your computer and this phone is online, then tap Retry. If it still fails, copy the join link again from your computer and paste it here."

    // Refresh and recovery import fail on the Folders screen, which has no link field:
    // no paste sentence there (#50 N1). Retry runs refresh().
    const val REFRESH_FAILED_NEXT =
        "Check that Leasegrid Sync is open on your computer and this phone is online, then tap Retry."
    // Shown only after the imported session was saved.
    const val IMPORT_SAVED_MSG = "Saved on this phone. Couldn't reach your computer to finish."

    /** Parse first. A failed parse never reaches [join]. */
    inline fun <T> attempt(raw: String, fail: (InviteFail) -> T, join: (ParsedInvite) -> T): T {
        val parsed = try {
            parse(raw)
        } catch (exc: InviteFail) {
            return fail(exc)
        }
        return join(parsed)
    }

    fun parse(raw: String): ParsedInvite {
        val text = raw.trim()
        if (text.isEmpty()) {
            throw InviteFail(EMPTY_MSG, NO_NEXT)
        }
        if (isShortCode(text)) {
            throw InviteFail(WORMHOLE_MSG, NO_NEXT)
        }
        if (text.startsWith("pb://")) {
            return ParsedInvite("furl", validateFurl(text))
        }
        val low = text.lowercase()
        if (text.startsWith("#") || low.startsWith("v=1&") || low.startsWith("v=1%")) {
            return fromFragment(text.removePrefix("#"))
        }
        if (low.startsWith("leasegrid:")) {
            val hash = text.indexOf('#')
            if (hash < 0 || hash == text.lastIndex) {
                throw InviteFail(NO_ADDRESS_MSG, NO_NEXT)
            }
            return fromFragment(text.substring(hash + 1))
        }
        if (low.startsWith("http://") || low.startsWith("https://")) {
            val hash = text.indexOf('#')
            val frag = if (hash >= 0) text.substring(hash + 1) else ""
            if (frag.contains("i=") || frag.lowercase().contains("i%3d")) {
                return fromFragment(frag)
            }
            throw InviteFail(WEB_URL_MSG, NO_NEXT)
        }
        throw InviteFail(GARBAGE_MSG, NO_NEXT)
    }

    fun joinEnabled(acknowledged: Boolean, invite: String): Boolean {
        return acknowledged && invite.isNotBlank()
    }

    private fun fromFragment(frag: String): ParsedInvite {
        // A link cut inside a %XX escape makes the decoder throw: that is an incomplete link.
        val decoded = try {
            java.net.URLDecoder.decode(frag, "UTF-8")
        } catch (_: IllegalArgumentException) {
            throw InviteFail(MALFORMED_MSG, NO_NEXT)
        }
        val params = mutableMapOf<String, String>()
        for (part in decoded.split("&")) {
            val eq = part.indexOf('=')
            if (eq <= 0) continue
            params[part.substring(0, eq)] = part.substring(eq + 1)
        }
        val furl = params["i"] ?: throw InviteFail(NO_ADDRESS_MSG, NO_NEXT)
        val shares = try {
            val n = params["n"]?.toInt()
            val h = params["h"]?.toInt()
            val t = params["t"]?.toInt()
            if (n != null && h != null && t != null && n > 0 && n <= h && h <= t) {
                listOf(n, h, t)
            } else {
                null
            }
        } catch (_: NumberFormatException) {
            null
        }
        return ParsedInvite("url", validateFurl(furl), shares)
    }

    /** Linear stand-in for `^[0-9]{1,3}(-[a-z0-9]+){2,}$`. No backtracking. */
    private fun isShortCode(text: String): Boolean {
        if (text.length > SHORT_CODE_MAX) return false
        val low = text.lowercase()
        var i = 0
        var digits = 0
        while (i < low.length && low[i] in '0'..'9') {
            digits++
            if (digits > 3) return false
            i++
        }
        if (digits == 0) return false
        var groups = 0
        while (i < low.length) {
            if (low[i] != '-') return false
            i++
            val start = i
            while (i < low.length && (low[i] in 'a'..'z' || low[i] in '0'..'9')) i++
            if (i == start) return false
            groups++
        }
        return groups >= 2
    }

    private fun validateFurl(raw: String): String {
        val text = raw.trim()
        if (!text.startsWith("pb://")) {
            throw InviteFail(GARBAGE_MSG, NO_NEXT)
        }
        // %00 is a NUL when the paste was not decoded yet. A join URL is decoded
        // first, so the same byte arrives as a control character or U+FFFD.
        if (text.contains("%00", ignoreCase = true) || text.any { rejectedInFurl(it) }) {
            throw InviteFail(MALFORMED_MSG, NO_NEXT)
        }
        val rest = text.removePrefix("pb://")
        val slash = rest.lastIndexOf('/')
        if (slash < 0 || rest.length < 12) {
            throw InviteFail(MALFORMED_MSG, NO_NEXT)
        }
        val swiss = rest.substring(slash + 1).substringBefore('#')
        if (swiss.length < MIN_SWISSNUM) {
            throw InviteFail(MALFORMED_MSG, NO_NEXT)
        }
        return text
    }

    private fun rejectedInFurl(ch: Char): Boolean {
        if (ch == '\uFFFD') return true
        if (ch.isWhitespace()) return true
        val code = ch.code
        return code <= 0x1F || code == 0x7F || code in 0x80..0x9F
    }
}
