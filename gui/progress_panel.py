"""
Progress panel: shows a progress bar and a scrollable log of processing events.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QProgressBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class ProgressPanel(QWidget):
    """Shows current file progress and a cumulative log."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.current_file_label = QLabel("")
        self.current_file_label.setStyleSheet("color: #555555; font-size: 12px;")

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet(
            "QProgressBar { border: 1px solid #dddddd; border-radius: 4px; height: 18px; }"
            "QProgressBar::chunk { background-color: #4a90d9; border-radius: 3px; }"
        )

        log_label = QLabel("Journal :")
        log_label.setStyleSheet("font-weight: bold; color: #333333;")

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(160)
        self.log_view.setStyleSheet(
            "QTextEdit { border: 1px solid #dddddd; border-radius: 4px; "
            "font-family: monospace; font-size: 12px; background: #fafafa; }"
        )

        layout.addWidget(self.current_file_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(log_label)
        layout.addWidget(self.log_view)

    def set_file(self, filename: str) -> None:
        self.current_file_label.setText(f"Traitement : {filename}")
        self.progress_bar.setValue(0)

    def update_progress(self, current: int, total: int) -> None:
        if total > 0:
            pct = int(current / total * 100)
            self.progress_bar.setValue(pct)

    def log(self, message: str) -> None:
        self.log_view.append(message)
        # Scroll to bottom
        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def reset(self) -> None:
        self.current_file_label.setText("")
        self.progress_bar.setValue(0)
        self.log_view.clear()

    def set_complete(self) -> None:
        self.progress_bar.setValue(100)
        self.current_file_label.setText("Traitement terminé.")
