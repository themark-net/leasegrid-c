package net.themark.leasegrid.sync.invite

data class ParsedInvite(
    val kind: String,
    val furl: String,
    val shares: List<Int>? = null,
    val code: String = "",
)

/** What a short-code attempt returned. [status] is ok, expired, rejected, relay, or timeout. */
data class RedeemOutcome(
    val status: String,
    val furl: String = "",
    val shares: List<Int>? = null,
)

data class RedeemCopy(val banner: String, val next: String)

class InviteFail(val banner: String, val next: String) : Exception(banner)

object Invite {
    // A real short code is a few words. Pastes longer than this are not one.
    // The old regex overflowed the stack on a few KB of "-a" groups (#78).
    private const val SHORT_CODE_MAX = 256

    /**
     * A camera result longer than this is not a join link. 4096 is the desktop
     * handoff bound, and more than a QR holds. A typed paste is not capped here,
     * so a long join link still parses.
     */
    const val SCAN_MAX = 4096

    // Foolscap swissnums are longer than this. The fixture swissnumswiss is 13
    // and must still parse. Empty and cut-short values are an incomplete link (#80 F1).
    private const val MIN_SWISSNUM = 8

    // A raw quote in a character check is read as copy by the string scan.
    private const val QUOTE = '\u0022'
    private const val APOSTROPHE = '\''

    const val ACK_MSG = "Read the four points above first."
    const val ACK_NEXT = "check “I understand the four points above.”, then Join."

    // Desktop labels, exact (src/leasegrid_sync/app.py). Pinned once here;
    // tests/test_android_invite_copy.py checks both against the desktop widgets.
    const val SHARE_INVITE = "Share invite"
    const val SHOW_FULL_JOIN_LINK = "Show full join link (advanced)"

    // Parse fails (empty, garbage, web URL, no address, malformed) show no
    // Next line (#50). A short code is not one of those (#77). A failed
    // learn() shows JOIN_FAILED_NEXT. A redeem that did not yield an address
    // shows one of the four redeem next lines.
    const val NO_NEXT = ""

    // Also the Join button label (Design, #50).
    const val TITLE = "Join a shared folder"
    const val BODY =
        "On your computer, click $SHARE_INVITE in Leasegrid Sync. Type the short code below, or tick $SHOW_FULL_JOIN_LINK and paste that link."
    const val INPUT_HINT = "Short code or join link"
    const val EMPTY_MSG = "Enter a short code or paste the join link first."
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
    // Paste advice stays on the parse/format messages. A learn() failure is
    // not a paste problem, so this line does not say to paste again (#82).
    const val JOIN_FAILED = "Couldn't reach your computer."
    const val JOIN_FAILED_NEXT =
        "Check that Leasegrid Sync is open on your computer and this phone is online, then tap Retry."

    // Refresh and recovery import fail on the Folders screen, which has no link field:
    // no paste sentence there (#50 N1). Retry runs refresh().
    const val REFRESH_FAILED_NEXT =
        "Check that Leasegrid Sync is open on your computer and this phone is online, then tap Retry."
    // Shown only after the imported session was saved.
    const val IMPORT_SAVED_MSG = "Saved on this phone. Couldn't reach your computer to finish."

    // Redeem did not yield an address, so learn() is not called (#77).
    // Retry reruns join() on the text in the field now.
    const val CODE_EXPIRED = "This code expired."
    const val CODE_EXPIRED_NEXT =
        "On your computer, click $SHARE_INVITE again. Keep Leasegrid Sync open, type the new short code here, then tap Retry."
    const val CODE_RELAY = "Couldn't reach the invite relay."
    const val CODE_RELAY_NEXT =
        "Check that this phone is online and Leasegrid Sync is still open on your computer, then tap Retry. If it still fails, tick $SHOW_FULL_JOIN_LINK and paste that link here."
    const val CODE_REJECTED = "This code was not accepted."
    const val CODE_REJECTED_NEXT =
        "On your computer, click $SHARE_INVITE again and use the new short code. Keep Leasegrid Sync open, then tap Retry."
    const val CODE_TIMEOUT = "Nobody answered this code yet."
    const val CODE_TIMEOUT_NEXT =
        "Keep Leasegrid Sync open on your computer until this phone joins, then tap Retry. If the code is old, click $SHARE_INVITE again and type the new short code."

    const val SCAN_QR = "Scan QR"
    const val SCAN_PROMPT = "Point at the code on your computer."
    const val SCAN_DENIED_MSG = "The camera was not allowed."
    const val SCAN_DENIED_NEXT = "Paste the join link or type the short code."

    /** Parse first. A failed parse never reaches [join]. */
    inline fun <T> attempt(raw: String, fail: (InviteFail) -> T, join: (ParsedInvite) -> T): T {
        val parsed = try {
            parse(raw)
        } catch (exc: InviteFail) {
            return fail(exc)
        }
        return join(parsed)
    }

    /** Banner for a redeem that did not return an address. Unknown statuses fail closed. */
    fun redeemCopy(status: String): RedeemCopy = when (status) {
        "expired" -> RedeemCopy(CODE_EXPIRED, CODE_EXPIRED_NEXT)
        "relay" -> RedeemCopy(CODE_RELAY, CODE_RELAY_NEXT)
        "timeout" -> RedeemCopy(CODE_TIMEOUT, CODE_TIMEOUT_NEXT)
        else -> RedeemCopy(CODE_REJECTED, CODE_REJECTED_NEXT)
    }

    fun parse(raw: String): ParsedInvite {
        val text = peelWrappers(stripPaste(raw))
        if (text.isEmpty()) {
            throw InviteFail(EMPTY_MSG, NO_NEXT)
        }
        if (isShortCode(text)) {
            // Lower case: the desktop code is printed in lower case, and a
            // mixed-case paste is the same code.
            return ParsedInvite("code", "", code = text.lowercase())
        }
        if (text.startsWith("pb://")) {
            return ParsedInvite("furl", validateFurl(text))
        }
        val low = text.lowercase()
        if (text.startsWith("#") || low.startsWith("v=1&") || low.startsWith("v=1%")) {
            return fromFragment(text.removePrefix("#"))
        }
        if (low.startsWith("leasegrid:")) {
            // Desktop urllib: a non-empty fragment wins, otherwise the query.
            // A trailing # is an empty fragment, so the query is the link.
            val tail = leasegridTail(text)
            if (tail.isEmpty()) {
                throw InviteFail(NO_ADDRESS_MSG, NO_NEXT)
            }
            return fromFragment(tail)
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

    /**
     * Text a scan may put in the field. Same cleanup as a paste: invisible marks,
     * trim, wrapped quotes or brackets, then a trailing sentence mark.
     * Throws [InviteFail] when that text is not a short code or a join link.
     */
    fun acceptScan(raw: String): String {
        if (raw.length > SCAN_MAX) throw InviteFail(GARBAGE_MSG, NO_NEXT)
        val text = peelWrappers(stripPaste(raw)).trimEnd(::trailingPasteJunk).trim()
        parse(text)
        return text
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
            if (n == null || h == null || t == null) null else keptShares(listOf(n, h, t))
        } catch (_: NumberFormatException) {
            null
        }
        return ParsedInvite("url", validateFurl(furl), shares)
    }

    /** Share counts from a join link or a redeemed invite. Null means the save path's 2, 3, 3. */
    internal fun keptShares(shares: List<Int>?): List<Int>? {
        if (shares == null || shares.size < 3) return null
        val needed = shares[0]
        val happy = shares[1]
        val total = shares[2]
        if (needed > 0 && needed <= happy && happy <= total) return listOf(needed, happy, total)
        return null
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

    /**
     * Drop the invisible marks chat apps add on paste (U+00AD, U+200B, U+200C,
     * U+200D, U+2060, U+FEFF) anywhere in the text, then trim(). None of them
     * is ever part of a join link, so a mark inside the link is noise, not damage.
     * U+202E is not dropped: it can hide a different host, so the link is rejected.
     */
    private fun stripPaste(raw: String): String {
        val unmarked = if (raw.any(::isPasteMark)) raw.filterNot(::isPasteMark) else raw
        return unmarked.trim()
    }

    private fun isPasteMark(ch: Char): Boolean =
        ch == '\u00AD' || ch == '\u200B' || ch == '\u200C' || ch == '\u200D' || ch == '\u2060' || ch == '\uFEFF'

    /**
     * The part of a leasegrid link that holds i=.
     * A #fragment is used when it has any characters. Otherwise the ?query is used.
     * A ? that sits inside the fragment stays in the fragment.
     */
    private fun leasegridTail(text: String): String {
        val hash = text.indexOf('#')
        val question = text.indexOf('?')
        val fragment = if (hash >= 0) text.substring(hash + 1) else ""
        if (fragment.isNotEmpty()) return fragment
        if (question < 0 || (hash >= 0 && question > hash)) return ""
        val end = if (hash >= 0) hash else text.length
        return text.substring(question + 1, end)
    }

    /** Quotes or brackets that chat and mail wrap around a pasted link. */
    private fun peelWrappers(text: String): String {
        var current = text.trim()
        while (current.length >= 2) {
            val open = current.first()
            val close = current.last()
            val pair = (open == QUOTE && close == QUOTE) ||
                (open == APOSTROPHE && close == APOSTROPHE) ||
                (open == '<' && close == '>') ||
                (open == '(' && close == ')') ||
                (open == '[' && close == ']')
            if (!pair) break
            current = current.substring(1, current.lastIndex).trim()
        }
        return current
    }

    private fun trailingPasteJunk(ch: Char): Boolean =
        ch == '.' || ch == ',' || ch == ';' || ch == ':' || ch == '!' || ch == '?' ||
            ch == ')' || ch == ']' || ch == '>' || ch == QUOTE || ch == APOSTROPHE

    /**
     * The one furl check, for a pasted link and a recovery file alike.
     * Throws [InviteFail] with the advice for what is wrong.
     */
    internal fun validateFurl(raw: String): String {
        val text = stripPaste(raw)
        if (!text.startsWith("pb://")) {
            throw InviteFail(GARBAGE_MSG, NO_NEXT)
        }
        // %00 is a NUL when the paste was not decoded yet. A join URL is decoded
        // first, so the same byte arrives as a control character or U+FFFD.
        if (text.contains("%00", ignoreCase = true) || text.any { rejectedInFurl(it) }) {
            throw InviteFail(MALFORMED_MSG, NO_NEXT)
        }
        // One @ separates the tub id from the location. A second @ is not a furl.
        if (text.count { it == '@' } > 1) {
            throw InviteFail(MALFORMED_MSG, NO_NEXT)
        }
        val rest = text.removePrefix("pb://")
        val slash = rest.lastIndexOf('/')
        if (slash < 0 || rest.length < 12) {
            throw InviteFail(MALFORMED_MSG, NO_NEXT)
        }
        // pb://TUBID@LOCATION/SWISS. No tub id is a cut link; no location is no address.
        val authority = rest.substring(0, slash)
        val at = authority.indexOf('@')
        if (at == 0) {
            throw InviteFail(MALFORMED_MSG, NO_NEXT)
        }
        if (at < 0 || at == authority.lastIndex) {
            throw InviteFail(NO_ADDRESS_MSG, NO_NEXT)
        }
        val after = rest.substring(slash + 1)
        val hash = after.indexOf('#')
        val swissRaw = if (hash >= 0) after.substring(0, hash) else after
        val suffix = if (hash >= 0) after.substring(hash) else ""
        // A sentence period or a closing bracket is not part of the link.
        val swiss = swissRaw.trimEnd(::trailingPasteJunk)
        if (swiss.length < MIN_SWISSNUM) {
            throw InviteFail(MALFORMED_MSG, NO_NEXT)
        }
        if (swiss == swissRaw) return text
        return "pb://" + rest.substring(0, slash + 1) + swiss + suffix
    }

    private fun rejectedInFurl(ch: Char): Boolean {
        if (ch == '\uFFFD' || ch == '+' || ch == '\u202E') return true
        if (ch.isWhitespace()) return true
        val code = ch.code
        return code <= 0x1F || code == 0x7F || code in 0x80..0x9F
    }
}
