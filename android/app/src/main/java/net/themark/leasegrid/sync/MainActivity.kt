package net.themark.leasegrid.sync

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import net.themark.leasegrid.sync.ui.AppModel
import net.themark.leasegrid.sync.ui.SyncApp

class MainActivity : ComponentActivity() {
    private val model: AppModel by viewModels()

    private val pickRecovery = registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri == null) return@registerForActivityResult
        val name = uri.lastPathSegment ?: "recovery.leasegrid-recovery"
        val bytes = contentResolver.openInputStream(uri)?.use { it.readBytes() } ?: return@registerForActivityResult
        model.onPicked(name, bytes)
        model.goImport()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            SyncApp(model) {
                pickRecovery.launch(arrayOf("*/*"))
            }
        }
    }
}
