package net.themark.leasegrid.sync.ui

import kotlin.coroutines.cancellation.CancellationException
import net.themark.leasegrid.sync.invite.Invite
import net.themark.leasegrid.sync.invite.InviteFail
import net.themark.leasegrid.sync.session.ServerRef
import net.themark.leasegrid.sync.session.Session

/** What [SessionFlow] needs from AppModel. Each member is a one-line delegation there. */
interface FlowHost {
    var inviteText: String
    val session: Session?
    fun launch(label: String, block: suspend () -> Unit)

    /** The grid's server list, or null on any failure. Never shows anything. */
    suspend fun learn(furl: String): List<ServerRef>?

    /** Write [next] to the store and make it the current session (Folders screen). */
    fun save(next: Session)
    fun show(banner: FailBanner, again: () -> Unit)
}

/**
 * Join, refresh, and the end of a recovery import (#50). Pure JVM.
 *
 * Every learn() failure shows Invite copy, never learn()'s raw text:
 * join shows JOIN_FAILED + JOIN_FAILED_NEXT (Retry reruns join, the field is kept);
 * refresh shows JOIN_FAILED + REFRESH_FAILED_NEXT (Retry reruns refresh);
 * an import that saved shows IMPORT_SAVED_MSG + REFRESH_FAILED_NEXT (Retry runs refresh).
 * The Folders screen has no link field, so refresh and import never say paste.
 */
class SessionFlow(private val host: FlowHost) {
    fun join() {
        val raw = host.inviteText
        host.launch("Joining…") {
            Invite.attempt(
                raw,
                fail = { exc: InviteFail -> host.show(FailBanner(exc.banner, exc.next)) { join() } },
            ) { parsed ->
                val learned = learnOrNull(parsed.furl)
                if (learned == null) {
                    host.show(FailBanner(Invite.JOIN_FAILED, Invite.JOIN_FAILED_NEXT)) { join() }
                } else {
                    host.save(
                        Session(
                            introducerFurl = parsed.furl,
                            shares = parsed.shares ?: listOf(2, 3, 3),
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

    private suspend fun learnOrNull(furl: String): List<ServerRef>? = try {
        host.learn(furl)
    } catch (exc: CancellationException) {
        throw exc
    } catch (_: Exception) {
        null
    }
}
