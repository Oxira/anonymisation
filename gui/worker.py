"""
QThread worker for running PDF anonymisation in the background.

Emits signals for progress updates and log messages so the UI stays responsive.
"""
from __future__ import annotations

from typing import List

from PySide6.QtCore import QThread, Signal


class AnonymisationWorker(QThread):
    """
    Background worker that processes a list of PDF files.

    Signals:
        file_started(filename):       emitted when a file begins processing
        file_progress(current, total): emitted for each page processed
        file_done(filename, n_redactions): emitted when a file is complete
        all_done(total_redactions):   emitted when all files are processed
        error(filename, message):     emitted on error
    """

    file_started = Signal(str)
    file_progress = Signal(int, int)
    file_done = Signal(str, int)
    all_done = Signal(int)
    error = Signal(str, str)

    def __init__(
        self,
        files: List[tuple],  # list of (input_path, output_path)
        nlp,
        dpi: int = 300,
        ocr_engine: str = "auto",
        parent=None,
    ):
        super().__init__(parent)
        self.files = files
        self.nlp = nlp
        self.dpi = dpi
        self.ocr_engine = ocr_engine
        self._abort = False

    def abort(self) -> None:
        """Request cancellation of the current job."""
        self._abort = True

    def run(self) -> None:
        from anonymiser.pipeline import process_pdf

        total_redactions = 0

        for input_path, output_path in self.files:
            if self._abort:
                break

            filename = input_path.split("/")[-1].split("\\")[-1]
            self.file_started.emit(filename)

            try:
                def progress_cb(current: int, total: int) -> None:
                    self.file_progress.emit(current, total)

                n = process_pdf(
                    input_path,
                    output_path,
                    self.nlp,
                    dpi=self.dpi,
                    ocr_engine=self.ocr_engine,
                    progress_cb=progress_cb,
                )
                total_redactions += n
                self.file_done.emit(filename, n)

            except Exception as exc:
                self.error.emit(filename, str(exc))

        self.all_done.emit(total_redactions)
