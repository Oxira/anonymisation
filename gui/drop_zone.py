"""
Drag-and-drop zone widget for accepting PDF files.
"""
from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QLabel


class DropZone(QLabel):
    """
    A label-based widget that accepts PDF files via drag-and-drop or click.

    Emits files_dropped(list_of_paths) when valid PDF files are dropped.
    """

    files_dropped = Signal(list)

    _STYLE_NORMAL = """
        QLabel {
            border: 2px dashed #aaaaaa;
            border-radius: 8px;
            color: #666666;
            font-size: 14px;
            padding: 20px;
            background-color: #f8f8f8;
        }
        QLabel:hover {
            border-color: #4a90d9;
            background-color: #eef5fd;
        }
    """

    _STYLE_HOVER = """
        QLabel {
            border: 2px dashed #4a90d9;
            border-radius: 8px;
            color: #4a90d9;
            font-size: 14px;
            padding: 20px;
            background-color: #eef5fd;
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText("Glisser-déposer vos PDFs ici\nou cliquer pour choisir des fichiers")
        self.setAlignment(Qt.AlignCenter)
        self.setAcceptDrops(True)
        self.setStyleSheet(self._STYLE_NORMAL)
        self.setMinimumHeight(120)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(u.toLocalFile().lower().endswith(".pdf") for u in urls):
                event.acceptProposedAction()
                self.setStyleSheet(self._STYLE_HOVER)
                return
        event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self.setStyleSheet(self._STYLE_NORMAL)

    def dropEvent(self, event: QDropEvent) -> None:
        self.setStyleSheet(self._STYLE_NORMAL)
        paths: List[str] = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".pdf"):
                paths.append(path)
        if paths:
            self.files_dropped.emit(paths)
        event.acceptProposedAction()

    def mousePressEvent(self, event) -> None:
        """Open a file dialog on click."""
        from PySide6.QtWidgets import QFileDialog
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Sélectionner des fichiers PDF",
            "",
            "Fichiers PDF (*.pdf)",
        )
        if paths:
            self.files_dropped.emit(paths)
