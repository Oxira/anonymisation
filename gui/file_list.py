"""
File list widget showing queued PDF files with per-item remove buttons.
"""
from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QWidget,
)


class FileListItem(QWidget):
    """A single row in the file list: filename label + remove button."""

    remove_requested = Signal(str)  # emits the file path

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self.path = path
        filename = path.split("/")[-1].split("\\")[-1]

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)

        self.status_label = QLabel("○")
        self.status_label.setFixedWidth(20)
        self.status_label.setStyleSheet("color: #aaaaaa;")

        self.name_label = QLabel(filename)
        self.name_label.setToolTip(path)

        remove_btn = QPushButton("✕")
        remove_btn.setFixedSize(24, 24)
        remove_btn.setStyleSheet(
            "QPushButton { border: none; color: #aaaaaa; font-size: 12px; }"
            "QPushButton:hover { color: #cc3333; }"
        )
        remove_btn.clicked.connect(lambda: self.remove_requested.emit(self.path))

        layout.addWidget(self.status_label)
        layout.addWidget(self.name_label, stretch=1)
        layout.addWidget(remove_btn)

    def set_processing(self) -> None:
        self.status_label.setText("⟳")
        self.status_label.setStyleSheet("color: #f0a500;")

    def set_done(self, n_redactions: int) -> None:
        self.status_label.setText("✓")
        self.status_label.setStyleSheet("color: #27ae60;")
        self.name_label.setToolTip(
            f"{self.path}\n{n_redactions} zone(s) redactée(s)"
        )

    def set_error(self) -> None:
        self.status_label.setText("✗")
        self.status_label.setStyleSheet("color: #cc3333;")


class FileListWidget(QListWidget):
    """A list widget managing PDF files to be anonymised."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._paths: List[str] = []
        self._item_widgets: dict = {}  # path → FileListItem
        self.setStyleSheet(
            "QListWidget { border: 1px solid #dddddd; border-radius: 4px; }"
        )

    def add_files(self, paths: List[str]) -> None:
        """Add files to the list, ignoring duplicates."""
        for path in paths:
            if path in self._paths:
                continue
            self._paths.append(path)

            item = QListWidgetItem(self)
            widget = FileListItem(path)
            widget.remove_requested.connect(self._remove_file)
            item.setSizeHint(widget.sizeHint())
            self.addItem(item)
            self.setItemWidget(item, widget)
            self._item_widgets[path] = (item, widget)

    def _remove_file(self, path: str) -> None:
        if path not in self._item_widgets:
            return
        item, _ = self._item_widgets.pop(path)
        self._paths.remove(path)
        self.takeItem(self.row(item))

    def get_paths(self) -> List[str]:
        return list(self._paths)

    def clear_all(self) -> None:
        self._paths.clear()
        self._item_widgets.clear()
        self.clear()

    def mark_processing(self, path: str) -> None:
        if path in self._item_widgets:
            _, widget = self._item_widgets[path]
            widget.set_processing()

    def mark_done(self, path: str, n_redactions: int) -> None:
        if path in self._item_widgets:
            _, widget = self._item_widgets[path]
            widget.set_done(n_redactions)

    def mark_error(self, path: str) -> None:
        if path in self._item_widgets:
            _, widget = self._item_widgets[path]
            widget.set_error()
