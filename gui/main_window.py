"""
Main application window for the PDF anonymisation tool.

Layout:
  - DropZone (drag-and-drop or click to add PDFs)
  - FileListWidget (queued files with remove buttons)
  - Output folder selector
  - Anonymise button
  - ProgressPanel (progress bar + log)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .drop_zone import DropZone
from .file_list import FileListWidget
from .progress_panel import ProgressPanel
from .worker import AnonymisationWorker


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Anonymiseur PDF")
        self.setMinimumWidth(600)
        self.setMinimumHeight(650)

        self._worker: Optional[AnonymisationWorker] = None
        self._nlp = None  # loaded lazily on first run

        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # Title
        title = QLabel("Anonymiseur PDF")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        subtitle = QLabel("Suppression automatique des données personnelles")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #777777; font-size: 12px;")
        main_layout.addWidget(subtitle)

        # Drop zone
        self.drop_zone = DropZone()
        main_layout.addWidget(self.drop_zone)

        # File list group
        files_group = QGroupBox("Fichiers à traiter")
        files_layout = QVBoxLayout(files_group)
        self.file_list = FileListWidget()
        self.file_list.setMinimumHeight(120)
        files_layout.addWidget(self.file_list)

        clear_btn = QPushButton("Tout retirer")
        clear_btn.setStyleSheet("color: #888888; font-size: 11px;")
        clear_btn.clicked.connect(self.file_list.clear_all)
        files_layout.addWidget(clear_btn, alignment=Qt.AlignRight)
        main_layout.addWidget(files_group)

        # Output folder row
        output_group = QGroupBox("Dossier de sortie")
        output_layout = QHBoxLayout(output_group)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Même dossier que les fichiers sources")
        self.output_edit.setReadOnly(True)
        browse_btn = QPushButton("Parcourir…")
        browse_btn.clicked.connect(self._browse_output)
        output_layout.addWidget(self.output_edit, stretch=1)
        output_layout.addWidget(browse_btn)
        main_layout.addWidget(output_group)

        # Anonymise button
        self.run_btn = QPushButton("Anonymiser")
        self.run_btn.setFixedHeight(42)
        self.run_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #4a90d9; color: white; border-radius: 6px;"
            "  font-size: 15px; font-weight: bold;"
            "}"
            "QPushButton:hover { background-color: #3a7fc9; }"
            "QPushButton:disabled { background-color: #aaaaaa; }"
        )
        main_layout.addWidget(self.run_btn)

        # Progress panel
        self.progress_panel = ProgressPanel()
        main_layout.addWidget(self.progress_panel)

        # Stretch at the bottom
        main_layout.addStretch()

    def _connect_signals(self) -> None:
        self.drop_zone.files_dropped.connect(self._on_files_dropped)
        self.run_btn.clicked.connect(self._on_run_clicked)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_files_dropped(self, paths: List[str]) -> None:
        self.file_list.add_files(paths)
        self._update_run_button()

    def _browse_output(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Choisir le dossier de sortie", ""
        )
        if folder:
            self.output_edit.setText(folder)

    def _update_run_button(self) -> None:
        count = len(self.file_list.get_paths())
        if count > 0:
            self.run_btn.setText(f"Anonymiser ({count} fichier{'s' if count > 1 else ''})")
            self.run_btn.setEnabled(True)
        else:
            self.run_btn.setText("Anonymiser")
            self.run_btn.setEnabled(False)

    def _on_run_clicked(self) -> None:
        paths = self.file_list.get_paths()
        if not paths:
            return

        # Load spaCy model once
        if self._nlp is None:
            self.run_btn.setEnabled(False)
            self.progress_panel.log("Chargement du modèle NLP…")
            QApplication.processEvents()
            try:
                from anonymiser.detector import load_nlp_model
                self._nlp = load_nlp_model()
                self.progress_panel.log("Modèle NLP chargé.")
            except Exception as exc:
                QMessageBox.critical(
                    self, "Erreur", f"Impossible de charger le modèle spaCy :\n{exc}"
                )
                self.run_btn.setEnabled(True)
                return

        # Build (input_path, output_path) pairs
        output_dir = self.output_edit.text().strip() or None
        file_pairs = []
        for path in paths:
            src = Path(path)
            if output_dir:
                dst = Path(output_dir) / (src.stem + "_anonymise.pdf")
            else:
                dst = src.parent / (src.stem + "_anonymise.pdf")
            file_pairs.append((str(src), str(dst)))

        # Start worker
        self.run_btn.setEnabled(False)
        self.progress_panel.reset()

        self._worker = AnonymisationWorker(file_pairs, self._nlp)
        self._worker.file_started.connect(self._on_file_started)
        self._worker.file_progress.connect(self._on_file_progress)
        self._worker.file_done.connect(self._on_file_done)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_file_started(self, filename: str) -> None:
        self.progress_panel.set_file(filename)
        self.progress_panel.log(f"▶ {filename}")
        # Find full path from filename
        for path in self.file_list.get_paths():
            if path.endswith(filename) or path.endswith("/" + filename) or path.endswith("\\" + filename):
                self.file_list.mark_processing(path)
                break

    def _on_file_progress(self, current: int, total: int) -> None:
        self.progress_panel.update_progress(current, total)

    def _on_file_done(self, filename: str, n_redactions: int) -> None:
        self.progress_panel.log(
            f"  ✓ {filename} — {n_redactions} zone(s) redactée(s)"
        )
        for path in self.file_list.get_paths():
            if path.endswith(filename) or path.endswith("/" + filename) or path.endswith("\\" + filename):
                self.file_list.mark_done(path, n_redactions)
                break

    def _on_all_done(self, total: int) -> None:
        self.progress_panel.set_complete()
        self.progress_panel.log(
            f"\n✔ Terminé — {total} zone(s) redactée(s) au total."
        )
        self.run_btn.setEnabled(True)
        self._update_run_button()

    def _on_error(self, filename: str, message: str) -> None:
        self.progress_panel.log(f"  ✗ {filename} — Erreur : {message}")
        for path in self.file_list.get_paths():
            if path.endswith(filename) or path.endswith("/" + filename) or path.endswith("\\" + filename):
                self.file_list.mark_error(path)
                break
