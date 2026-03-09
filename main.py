"""
Entry point for the PDF anonymisation GUI.

Usage:
    python main.py
"""
import sys

from PySide6.QtWidgets import QApplication

from gui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Anonymiseur PDF")
    app.setOrganizationName("AnonymiseurPDF")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
