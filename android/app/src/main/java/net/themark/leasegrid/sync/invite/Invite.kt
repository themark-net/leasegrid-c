package net.themark.leasegrid.sync.invite

data class ParsedInvite(
    val kind: String,
    val furl: String,
    val shares: List<Int>? = null,
)

class InviteFail(val banner: String, val next: String) : Exception(banner)

object Invite {
    private val wormhole = Regex("^[0-9]{1,3}(-[a-z0-9]+){2,}$")

    const val ACK_MSG = "Read the four points above first."
    const val ACK_NEXT = "check “I understand the four points above.”, then Join."

    // Desktop labels, exact (src/leasegrid_sync/app.py). Pinned once here;
    // tests/test_android_invite_copy.py checks both against the desktop widgets.
    const val SHARE_INVITE = "Share invite"
    const val SHOW_FULL_JOIN_LINK = "Show full join link (advanced)"

    // Parse fails (empty, short code, garbage, web URL, no address, malformed)
    // show no Next line (#50, Design). A failed learn() shows JOIN_FAILED_NEXT.
    const val NO_NEXT = ""

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
        if (wormhole.matches(text.lowercase())) {
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
        val decoded = java.net.URLDecoder.decode(frag, "UTF-8")
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

    private fun validateFurl(raw: String): String {
        val text = raw.trim()
        if (!text.startsWith("pb://")) {
            throw InviteFail(GARBAGE_MSG, NO_NEXT)
        }
        val rest = text.removePrefix("pb://")
        if (!rest.contains("/") || rest.length < 12) {
            throw InviteFail(MALFORMED_MSG, NO_NEXT)
        }
        return text
    }
}
