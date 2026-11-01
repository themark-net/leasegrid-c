package net.themark.leasegrid.sync.ui

/**
 * The Retry button's action.
 * [pull] returns it once. A second pull is empty until [arm] again,
 * so a double tap cannot run the same action twice.
 */
internal class RetryOnce {
    private var action: (() -> Unit)? = null

    fun arm(again: (() -> Unit)?) {
        action = again
    }

    fun pull(): (() -> Unit)? {
        val current = action
        action = null
        return current
    }
}
