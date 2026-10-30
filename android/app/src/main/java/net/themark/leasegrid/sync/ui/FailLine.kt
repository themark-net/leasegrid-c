package net.themark.leasegrid.sync.ui

data class FailBanner(val message: String, val next: String)

/** The fail card's Next line. A blank next renders no line (#50). */
fun failNextLine(next: String): String? = if (next.isBlank()) null else "Next: $next"
