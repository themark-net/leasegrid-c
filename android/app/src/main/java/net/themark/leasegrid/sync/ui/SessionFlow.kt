package net.themark.leasegrid.sync.ui

import kotlin.coroutines.cancellation.CancellationException
import net.themark.leasegrid.sync.invite.Invite
import net.themark.leasegrid.sync.invite.InviteFail
import net.themark.leasegrid.sync.invite.ParsedInvite
import net.themark.leasegrid.sync.invite.RedeemOutcome
import net.themark.leasegrid.sync.session.ServerRef
import net.themark.leasegrid.sync.session.Session

/** What [SessionFlow] needs from AppModel. Each member is a one-line delegation there. */
interface FlowHost {
    var inviteText: String
    val session: Session?
    fun launch(label: String, block: suspend () -> Unit)

    /** The grid's server list, or null on any failure. Never shows anything. */
    suspend fun learn(furl: String): List<ServerRef>?

    /**
     * Tahoe 1.20 client handshake for a short code.
     * Returns a status only. Does not show a banner.
     */
    suspend fun redeem(code: String): RedeemOutcome

    /** Write [next] to the store and make it the current session (Folders screen). */
    fun save(next: Session)
    fun show(banner: FailBanner, again: () -> Unit)
}

/**
 * Join, refresh, and the end of a recovery import (#50). Pure JVM.
 *
 * Every learn() failure shows Invite copy, never learn()'s raw text:
 * join shows JOIN_FAILED + JOIN_FAILED_NEXT (no paste advice; Retry reruns join, the field is kept);
 * refresh shows JOIN_FAILED + REFRESH_FAILED_NEXT (Retry reruns refresh);
 * an import that saved shows IMPORT_SAVED_MSG + REFRESH_FAILED_NEXT (Retry runs refresh).
 * The Folders screen has no link field, so refresh and import never say paste.
 */
class SessionFlow(private val host: FlowHost) {
    fun join() {
        // The text at this tap. The job may start later, and a change before it
        // starts still joins this text. Unexpected Retry runs this same block
        // again, and that run reads the field as it is then.
        val tapped = host.inviteText
        var opened = false
        host.launch("Joining…") {
            val raw = if (opened) host.inviteText else tapped
            opened = true
            Invite.attempt(
                raw,
                fail = { exc: InviteFail -> host.show(FailBanner(exc.banner, exc.next)) { join() } },
            ) { parsed ->
                val ready = if (parsed.kind == "code") {
                    redeemReady(parsed.code) ?: return@attempt
                } else {
                    parsed
                }
                val learned = learnOrNull(ready.furl)
                if (learned == null) {
                    host.show(FailBanner(Invite.JOIN_FAILED, Invite.JOIN_FAILED_NEXT)) { join() }
                } else {
                    host.save(
                        Session(
                            introducerFurl = ready.furl,
                            shares = ready.shares ?: listOf(2, 3, 3),
                            folders = host.session?.folders ?: emptyList(),
                            servers = learned,
                        ),
                    )
                }
            }
        }
    }

    fun refresh() {
        val current = host.session ?: return
        host.launch("Refreshing…") {
            val learned = learnOrNull(current.introducerFurl)
            if (learned == null) {
                host.show(FailBanner(Invite.JOIN_FAILED, Invite.REFRESH_FAILED_NEXT)) { refresh() }
            } else {
                host.save(current.copy(servers = learned))
            }
        }
    }

    /**
     * After a recovery file decoded: learn, build, save. The reassurance banner shows only
     * once [FlowHost.save] returned; if the save throws, the caller's generic fail shows instead.
     */
    suspend fun finishImport(furl: String, build: (List<ServerRef>?) -> Session) {
        val learned = learnOrNull(furl)
        host.save(build(learned))
        if (learned == null) {
            host.show(FailBanner(Invite.IMPORT_SAVED_MSG, Invite.REFRESH_FAILED_NEXT)) { refresh() }
        }
    }

    /** Null when the banner is already shown. Cancellation still escapes. */
    private suspend fun redeemReady(code: String): ParsedInvite? {
        val outcome = try {
            host.redeem(code)
        } catch (exc: CancellationException) {
            throw exc
        } catch (_: Exception) {
            val copy = Invite.redeemCopy("relay")
            host.show(FailBanner(copy.banner, copy.next)) { join() }
            return null
        }
        if (outcome.status != "ok") {
            val copy = Invite.redeemCopy(outcome.status)
            host.show(FailBanner(copy.banner, copy.next)) { join() }
            return null
        }
        val furl = try {
            Invite.validateFurl(outcome.furl)
        } catch (exc: InviteFail) {
            host.show(FailBanner(exc.banner, exc.next)) { join() }
            return null
        }
        return ParsedInvite("url", furl, Invite.keptShares(outcome.shares))
    }

    private suspend fun learnOrNull(furl: String): List<ServerRef>? = try {
        host.learn(furl)
    } catch (exc: CancellationException) {
        throw exc
    } catch (_: Exception) {
        null
    }
}
