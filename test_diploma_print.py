import copy
import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication, QMainWindow

from diploma import DOCUMENT_DEFAULTS, DOCUMENT_LAYOUTS, DiplomaDialog, default_document_text_boxes
from diploma_print import paint_to_printer


PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
ICONS_DIR = os.path.join(PROJECT_DIR, "icons")


class DiplomaPrintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.owner = QMainWindow()
        self.owner.central = SimpleNamespace(icons_path=ICONS_DIR)

    def tearDown(self):
        self.owner.close()
        self.app.processEvents()

    def test_every_print_kind_has_editable_text_boxes(self):
        for kind, defaults in DOCUMENT_DEFAULTS.items():
            boxes = default_document_text_boxes(kind, copy.deepcopy(defaults))
            self.assertGreater(len(boxes), 0, kind)
            self.assertTrue(all("x" in box and "font_size" in box for box in boxes), kind)

    def test_dialog_exposes_all_six_print_kinds(self):
        dialog = DiplomaDialog(self.owner, ICONS_DIR)
        try:
            self.assertEqual(set(DOCUMENT_DEFAULTS), set(dialog.text_boxes))
            self.assertEqual(set(DOCUMENT_DEFAULTS), set(dialog.economical_print))
            self.assertEqual(set(DOCUMENT_DEFAULTS), set(dialog.show_logo))
            for kind in DOCUMENT_DEFAULTS:
                self.assertIn(kind, DOCUMENT_LAYOUTS)
        finally:
            dialog.close()

    def test_new_background_assets_exist(self):
        paths = (
            "diplomas/sports_d.png",
            "documents/daily_a.png",
            "documents/daily_b.png",
            "documents/cleaning_award_a.png",
            "documents/cleaning_award_b.png",
            "documents/meal_a.png",
            "documents/meal_b.png",
        )
        for relative in paths:
            self.assertTrue(os.path.isfile(os.path.join(ICONS_DIR, *relative.split("/"))), relative)


if __name__ == "__main__":
    unittest.main()
