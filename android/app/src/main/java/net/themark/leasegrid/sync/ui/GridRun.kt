package net.themark.leasegrid.sync.ui

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch

/**
 * Unexpected grid failure. The exception class is for the log, not the card.
 * Retry is the caller's job: it must run the same block again.
 */
@Suppress("UNUSED_PARAMETER")
internal fun unexpectedGridCard(exc: Exception): FailBanner {
    return FailBanner(
        "could not complete that.",
        "Retry. If it repeats, check the network and the invite.",
    )
}

/**
 * One grid coroutine at a time.
 *
 * A newer [launch] or [cancel] bumps the ticket first. The older coroutine's
 * `finally` then sees a stale ticket and must not clear busy under the newer job.
 */
internal class GridRun(
    private val scope: CoroutineScope,
    private val setBusy: (Boolean) -> Unit,
    private val setFail: (FailBanner?) -> Unit,
) {
    private var job: Job? = null
    private var ticket = 0

    fun launch(onError: ((Exception) -> Unit)? = null, block: suspend () -> Unit) {
        val mine = ++ticket
        job?.cancel()
        job = scope.launch {
            setBusy(true)
            setFail(null)
            try {
                block()
            } catch (exc: CancellationException) {
                throw exc
            } catch (exc: Exception) {
                if (onError == null) throw exc
                onError(exc)
            } finally {
                // F4: only the job that is still current may clear busy.
                if (mine == ticket) setBusy(false)
            }
        }
    }

    /** Stop the current job. Its finish is stale, and busy is cleared now. */
    fun cancel() {
        ticket += 1
        job?.cancel()
        job = null
        setBusy(false)
    }
}
