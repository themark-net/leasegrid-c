package net.themark.leasegrid.sync.ui

import kotlin.coroutines.cancellation.CancellationException
import net.themark.leasegrid.sync.invite.Invite
import net.themark.leasegrid.sync.invite.InviteFail
import net.themark.leasegrid.sync.invite.ParsedInvite
import net.themark.leasegrid.sync.session.ServerRef

/**
 * Join from the pasted invite (#50). Pure JVM: AppModel supplies the grid and the UI.
 *
 * A parse fail shows the Invite banner. Any learn() failure (null or a throw) shows
 * Invite.JOIN_FAILED + JOIN_FAILED_NEXT, never learn()'s raw text. Retry on either
 * card reruns [join] with whatever is in the field now. The field is never cleared here.
 */
class JoinFlow(
    private val text: () -> String,
    private val launch: (suspend () -> Unit) -> Unit,
    private val learn: suspend (String) -> List<ServerRef>?,
    private val show: (FailBanner, () -> Unit) -> Unit,
    private val joined: (ParsedInvite, List<ServerRef>) -> Unit,
) {
    fun join() {
        val raw = text()
        launch {
            Invite.attempt(
                raw,
                fail = { exc: InviteFail -> show(FailBanner(exc.banner, exc.next)) { join() } },
            ) { parsed ->
                val learned = try {
                    learn(parsed.furl)
                } catch (exc: CancellationException) {
                    throw exc
                } catch (_: Exception) {
                    null
                }
                if (learned == null) {
                    show(FailBanner(Invite.JOIN_FAILED, Invite.JOIN_FAILED_NEXT)) { join() }
                } else {
                    joined(parsed, learned)
                }
            }
        }
    }
}
