import copy
import os
import tempfile
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton

import groups
import sports_day
from groups import GroupCard, GroupsDialog
from home_menu import PirateHomeWidget
from sports_day import SportsDayDialog


PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
ICONS_DIR = os.path.join(PROJECT_DIR, "icons")


def sample_data():
    return {
        "schema_version": 1,
        "source": {"file_name": "vzor.xlsx"},
        "groups": [
            {
                "id": "group-1",
                "name": "1. oddíl",
                "children": [
                    {
                        "id": "child-1",
                        "role": "child",
                        "fields": {
                            "Jméno": "Anna",
                            "Příjmení": "Nováková",
                            "Věk": "10",
                            "Ubytování": "Liščí nora",
                        },
                    }
                ],
                "leaders": [
                    {
                        "id": "leader-1",
                        "role": "leader",
                        "fields": {
                            "Jméno": "Petr",
                            "Příjmení": "Kapitán",
                            "Telefon": "+420 111 222 333",
                        },
                    }
                ],
            },
            {
                "id": "group-2",
                "name": "2. oddíl",
                "children": [],
                "leaders": [],
            },
        ],
    }


class GroupsUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.owner = QMainWindow()
        self.owner.central = SimpleNamespace(icons_path=ICONS_DIR)

    def tearDown(self):
        self.owner.close()
        self.app.processEvents()

    def test_home_menu_contains_eight_cards_and_groups_tile(self):
        home = PirateHomeWidget(ICONS_DIR, "0.0.4")
        try:
            self.assertEqual(8, len(home.cards))
            self.assertIn("Oddíly", [card.title for card in home.cards])
            self.assertEqual(6, len(home.diploma_choice_cards))
            self.assertIn("Jídelníček", [card.title for card in home.diploma_choice_cards])
        finally:
            home.close()

    def test_group_overview_detail_and_whole_card_click_area(self):
        original_loader = groups.load_groups_data
        groups.load_groups_data = lambda: copy.deepcopy(sample_data())
        try:
            dialog = GroupsDialog(self.owner, ICONS_DIR)
            try:
                self.assertIn("ODDÍLY 2", dialog.stats_label.text())
                card = next(
                    widget
                    for widget in dialog.groups_host.findChildren(GroupCard)
                    if widget.group.get("id") == "group-1"
                )
                self.assertTrue(card.hitButton(QPoint(5, 5)))
                dialog.show_group("group-1")
                self.assertEqual(1, dialog.children_table.rowCount())
                self.assertIn("1 dětí", dialog.detail_stats.text())
                leader_buttons = dialog.leaders_host.findChildren(QPushButton)
                self.assertTrue(any("Petr" in button.text() for button in leader_buttons))
            finally:
                dialog.close()
        finally:
            groups.load_groups_data = original_loader

    def test_sports_day_uses_roster_name_completer(self):
        original_entries = sports_day.roster_entries
        original_data_dir = sports_day.get_user_data_dir
        with tempfile.TemporaryDirectory() as folder:
            sports_day.get_user_data_dir = lambda *_args, **_kwargs: folder
            sports_day.roster_entries = lambda: [
                {
                    "name": "Anna Nováková",
                    "group_name": "1. oddíl",
                    "role": "Dítě",
                }
            ]
            try:
                dialog = SportsDayDialog(self.owner, ICONS_DIR)
                try:
                    self.assertEqual(1, dialog._roster_completer.model().rowCount())
                    label = next(iter(dialog._roster_completion_names))
                    dialog._use_roster_completion(label)
                    self.assertEqual("Anna Nováková", dialog.competitor_name_edit.text())
                finally:
                    dialog.close()
            finally:
                sports_day.roster_entries = original_entries
                sports_day.get_user_data_dir = original_data_dir


if __name__ == "__main__":
    unittest.main()
