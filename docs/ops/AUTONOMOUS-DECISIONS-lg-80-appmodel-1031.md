# Autonomous decisions: lg-80-appmodel-1031

One line each: choice | alternatives | why

This lane is one workstream in this worktree. No parallel implementers. | spawn one sub-agent per item | AppModel.kt, SyncApp.kt, and FolderWrite.kt overlap, and the lane must push after each item
Tester mutant bodies M4c, J4a, J1c, N4b, N4d are not in the repo or on origin/main. Pin each FlowHost one-liner exactly instead of guessing a mutant diff. | skip the tests, or add Robolectric | the drop-in asks for exact delegation checks; AppModel still cannot be constructed without an Application (decision of 2026-10-29)
Phone chips say "Not in the shared folder yet" and "In the shared folder". | keep design 55-59's "friendnet" labels, or say "On your computer" | design 61 bans friendnet in phone copy, and design 55 says the chip must not claim the computer has the file
`repo-handoff-doc-required` and `write-loop-exits-first` are not files in this repo. The exit card is in the run log, and the handoff is the finish step in the drop-in. | hunt the skills outside the repo and block | the drop-in already states both requirements
Turn cap is 12 items, then the lane is empty. | keep scanning the whole repo after the named scope | the drop-in says keep taking lane gaps, and also says do not invent architecture
Android SDK platform 34 is installed under this worktree's tmp/android-sdk. | write into another project's SDK, or commit a compileSdk bump | compileSdk is 34 and this host had no android-34 platform; tmp/ is gitignored
Targeted Gradle unit tests after 05:49Z run nice -n 19 without the heavy lock. | wait on the flock until the wall | pid 2605611 holds the lock while sleeping on pgrep Runner.Worker, which matches queued flock 3024123's own command line. No Runner.Worker process. The sleeper will not start pregate until 3024123 exits, and 3024123 will not exit until it gets the lock. Memory was about 60 GiB free and load was under 5. One Gradle at a time in this worktree.
Full :app:testDebugUnitTest also ran nice -n 19 outside that lock, twice (52 tests, then 53 after the download fix). | leave it queued on the deadlocked flock | the same sleeper still held the lock, Runner.Worker was absent, and the suite finished in about 1 second. 0 failures.
Local read, space, and bad-name failures still pass an empty Retry lambda. | pass null, or retry the byte write | retryFail already clears the card before the lambda runs, so the tap dismisses. There is no second copy of the picked bytes to write again.
