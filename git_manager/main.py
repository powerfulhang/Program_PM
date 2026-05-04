"""Entry point for PyInstaller frozen build.

Writes crash logs to ~/git_manager_crash.log and shows an error dialog
so failures are visible even in --windowed mode.
"""
import sys
import traceback
from pathlib import Path

try:
    from git_manager.qt_app import main
    main()
except Exception:
    log_path = Path.home() / "git_manager_crash.log"
    log_path.write_text(traceback.format_exc(), encoding="utf-8")
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        app = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(
            None,
            "Git Manager - Error",
            f"An error occurred:\n\n{traceback.format_exc()}\n\nLog saved to: {log_path}",
        )
    except Exception:
        pass
    sys.exit(1)
