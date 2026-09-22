package net.themark.leasegrid.sync.invite

data class ParsedInvite(
    val kind: String,
    val furl: String,
    val shares: List<Int>? = null,
)

class InviteFail(val banner: String, val next: String) : Exception(banner)

object Invite {
    private val wormhole = Regex("^[0-9]{1,3}(-[a-z0-9]+){2,}$")

    const val ACK_MSG = "could not join this friendnet. The four points above are not acknowledged."
    const val ACK_NEXT = "check “I understand the four points above.”, then Join."
    const val WORMHOLE_MSG =
        "could not join this friendnet. A short code is not redeemed on this phone."
    const val WORMHOLE_NEXT =
        "paste the full join link or the pb:// furl from desktop Sync; Retry."

    fun parse(raw: String): ParsedInvite {
        val text = raw.trim()
        if (text.isEmpty()) {
            throw InviteFail(
                "could not join this friendnet. Invite is empty.",
                "paste a join link or a pb:// furl.",
            )
        }
        if (wormhole.matches(text.lowercase())) {
            throw InviteFail(WORMHOLE_MSG, WORMHOLE_NEXT)
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
                throw InviteFail(
                    "could not join this friendnet. That link has no address.",
                    "paste the full link (it includes a #…); Retry.",
                )
            }
            return fromFragment(text.substring(hash + 1))
        }
        if (low.startsWith("http://") || low.startsWith("https://")) {
            val hash = text.indexOf('#')
            val frag = if (hash >= 0) text.substring(hash + 1) else ""
            if (frag.contains("i=") || frag.lowercase().contains("i%3d")) {
                return fromFragment(frag)
            }
            throw InviteFail(
                "could not join this friendnet. That looks like a web URL.",
                "Leasegrid Sync does not use the Tahoe web UI. Paste a join link or pb:// furl.",
            )
        }
        throw InviteFail(
            "could not join this friendnet. Invite code invalid.",
            "ask your inviter for a fresh invite (pb://… or a full join link); Retry.",
        )
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
        val furl = params["i"] ?: throw InviteFail(
            "could not join this friendnet. That link has no address.",
            "ask for the full link (it includes a #…); Retry.",
        )
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
            throw InviteFail(
                "could not join this friendnet. Invite code invalid.",
                "ask your inviter for a fresh invite (pb://…); Retry.",
            )
        }
        val rest = text.removePrefix("pb://")
        if (!rest.contains("/") || rest.length < 12) {
            throw InviteFail(
                "could not join this friendnet. Invite furl is malformed.",
                "get a fresh code from your inviter; check network; Retry.",
            )
        }
        return text
    }
}
