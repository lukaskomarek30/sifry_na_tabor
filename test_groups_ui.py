import copy
import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QPushButton

import groups
import sports_day
from groups import AccommodationCard, GroupCard, GroupsDialog, _sync_person_field_schema
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
            self.assertIn("Oddíly/Ubytování", [card.title for card in home.cards])
            self.assertEqual("ZÁLOHA DAT", home.data_backup_button.text())
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
                self.assertTrue(dialog.groups_host.findChildren(AccommodationCard))
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

    def test_clear_all_groups_requires_confirmation_and_saves_empty_data(self):
        original_loader = groups.load_groups_data
        original_save = groups.save_groups_data
        original_question = groups.QMessageBox.question
        saved = []
        groups.load_groups_data = lambda: copy.deepcopy(sample_data())
        groups.save_groups_data = lambda data: saved.append(copy.deepcopy(data))
        groups.QMessageBox.question = lambda *_args, **_kwargs: QMessageBox.Yes
        try:
            dialog = GroupsDialog(self.owner, ICONS_DIR)
            try:
                dialog._clear_all_groups()

                self.assertEqual([], dialog.data["groups"])
                self.assertEqual([], saved[-1]["groups"])
                self.assertIn("ODDÍLY 0", dialog.stats_label.text())
            finally:
                dialog.close()
        finally:
            groups.QMessageBox.question = original_question
            groups.save_groups_data = original_save
            groups.load_groups_data = original_loader

    def test_accommodation_overview_and_detail_follow_person_field(self):
        original_loader = groups.load_groups_data
        groups.load_groups_data = lambda: copy.deepcopy(sample_data())
        try:
            dialog = GroupsDialog(self.owner, ICONS_DIR)
            try:
                dialog.show_accommodations()
                card = next(
                    widget
                    for widget in dialog.accommodation_host.findChildren(AccommodationCard)
                    if widget.title == "Liščí nora"
                )
                self.assertTrue(card.hitButton(QPoint(5, 5)))
                dialog.show_accommodation("Liščí nora")
                self.assertEqual(1, dialog.accommodation_people_table.rowCount())
                self.assertEqual("Anna Nováková", dialog.accommodation_people_table.item(0, 0).text())
                accommodation_anchors = tuple(dialog.section_visuals["accommodation"]["fire_anchors"])
                self.assertEqual(accommodation_anchors, dialog.fire_flicker.anchors)
                dialog.show_group("group-1")
                group_anchors = tuple(dialog.section_visuals["groups"]["fire_anchors"])
                self.assertEqual(group_anchors, dialog.fire_flicker.anchors)
            finally:
                dialog.close()
        finally:
            groups.load_groups_data = original_loader

    def test_person_card_new_field_is_added_empty_to_everyone(self):
        data = sample_data()
        data["groups"][0]["children"][0]["fields"]["Pohlaví"] = "Holka"
        data["groups"][1]["children"].append(
            {
                "id": "child-2",
                "role": "child",
                "fields": {
                    "Jméno": "Borek",
                    "Příjmení": "Adámek",
                },
            }
        )
        data["groups"][1]["leaders"].append(
            {
                "id": "leader-2",
                "role": "leader",
                "fields": {
                    "Jméno": "Klára",
                    "Příjmení": "Kormidelní",
                },
            }
        )

        changed = _sync_person_field_schema(data["groups"])

        self.assertTrue(changed)
        self.assertEqual("Holka", data["groups"][0]["children"][0]["fields"]["Pohlaví"])
        self.assertIn("Pohlaví", data["groups"][1]["children"][0]["fields"])
        self.assertEqual("", data["groups"][1]["children"][0]["fields"]["Pohlaví"])
        self.assertIn("Pohlaví", data["groups"][1]["leaders"][0]["fields"])
        self.assertEqual("", data["groups"][1]["leaders"][0]["fields"]["Pohlaví"])

    def test_accommodation_detail_header_sorting_toggles(self):
        original_loader = groups.load_groups_data
        data = sample_data()
        data["groups"][0]["children"].extend(
            [
                {
                    "id": "child-2",
                    "role": "child",
                    "fields": {
                        "Jméno": "Cyril",
                        "Příjmení": "Zedník",
                        "Věk": "9",
                        "Ubytování": "Liščí nora",
                    },
                },
                {
                    "id": "child-3",
                    "role": "child",
                    "fields": {
                        "Jméno": "Borek",
                        "Příjmení": "Adámek",
                        "Věk": "11",
                        "Ubytování": "Liščí nora",
                    },
                },
            ]
        )
        groups.load_groups_data = lambda: copy.deepcopy(data)
        try:
            dialog = GroupsDialog(self.owner, ICONS_DIR)
            try:
                dialog.show_accommodation("Liščí nora")
                dialog._accommodation_header_clicked(2)
                self.assertEqual("Cyril Zedník", dialog.accommodation_people_table.item(0, 0).text())
                dialog._accommodation_header_clicked(2)
                self.assertEqual("Borek Adámek", dialog.accommodation_people_table.item(0, 0).text())
                dialog._accommodation_header_clicked(0)
                self.assertEqual("Anna Nováková", dialog.accommodation_people_table.item(0, 0).text())
                dialog._accommodation_header_clicked(0)
                self.assertEqual("Cyril Zedník", dialog.accommodation_people_table.item(0, 0).text())
            finally:
                dialog.close()
        finally:
            groups.load_groups_data = original_loader

    def test_group_detail_header_sorting_toggles(self):
        original_loader = groups.load_groups_data
        data = sample_data()
        data["groups"][0]["children"].extend(
            [
                {
                    "id": "child-2",
                    "role": "child",
                    "fields": {
                        "Počet": "2",
                        "Jméno": "Cyril",
                        "Příjmení": "Zedník",
                        "Věk": "9",
                        "Ubytování": "Kajuta",
                    },
                },
                {
                    "id": "child-3",
                    "role": "child",
                    "fields": {
                        "Počet": "1",
                        "Jméno": "Borek",
                        "Příjmení": "Adámek",
                        "Věk": "11",
                        "Ubytování": "Kajuta",
                    },
                },
            ]
        )
        groups.load_groups_data = lambda: copy.deepcopy(data)
        try:
            dialog = GroupsDialog(self.owner, ICONS_DIR)
            try:
                dialog.show_group("group-1")
                dialog._children_header_clicked(0)
                self.assertEqual("Anna Nováková", dialog.children_table.item(0, 0).text())
                dialog._children_header_clicked(0)
                self.assertEqual("Cyril Zedník", dialog.children_table.item(0, 0).text())
                pocet_column = next(
                    index for index, label in enumerate(dialog._children_headers)
                    if groups.normalized_label(label) == "pocet"
                )
                dialog._children_header_clicked(pocet_column)
                self.assertEqual("Borek Adámek", dialog.children_table.item(0, 0).text())
            finally:
                dialog.close()
        finally:
            groups.load_groups_data = original_loader

    def test_sports_day_uses_roster_name_completer(self):
        original_entries = sports_day.roster_entries
        original_data_dir = sports_day.get_user_data_dir
        original_save = SportsDayDialog._save_data
        sports_day.get_user_data_dir = lambda *_args, **_kwargs: PROJECT_DIR
        sports_day.roster_entries = lambda: [
            {
                "name": "Anna Nováková",
                "group_name": "1. oddíl",
                "role": "Dítě",
                "group_id": "group-1",
                "person_id": "child-1",
                "fields": {
                    "Věk": "10",
                    "Pohlaví": "Holka",
                },
            }
        ]
        SportsDayDialog._save_data = lambda self: None
        try:
            dialog = SportsDayDialog(self.owner, ICONS_DIR)
            try:
                dialog.categories.append({"id": "cat-9-11", "name": "9-11"})
                dialog._refresh_category_combos()
                dialog.competitors.append(
                    {"id": "pirate-1", "name": "Borek Adámek", "category_id": "cat-9-11", "gender": "M", "age": 9}
                )
                dialog._refresh_competitor_search_completer()

                self.assertEqual(1, dialog._roster_completer.model().rowCount())
                label = next(iter(dialog._roster_completion_names))
                dialog._use_roster_completion(label)
                self.assertEqual("Anna Nováková", dialog.competitor_name_edit.text())
                self.assertEqual("10", dialog.competitor_age_edit.text())
                self.assertEqual("cat-9-11", dialog.competitor_category_combo.currentData())
                self.assertEqual("F", dialog.competitor_gender_combo.currentData())

                search_label = next(iter(dialog._competitor_search_names))
                dialog._use_competitor_search_completion(search_label)
                self.assertEqual("Borek Adámek", dialog.competitor_search_edit.text())
            finally:
                dialog.close()
        finally:
            sports_day.roster_entries = original_entries
            sports_day.get_user_data_dir = original_data_dir
            SportsDayDialog._save_data = original_save

    def test_sports_day_age_category_assignment_and_clear_crew(self):
        original_data_dir = sports_day.get_user_data_dir
        original_save = SportsDayDialog._save_data
        original_question = sports_day.QMessageBox.question
        sports_day.get_user_data_dir = lambda *_args, **_kwargs: os.path.join(PROJECT_DIR, "__missing_sports_data__")
        SportsDayDialog._save_data = lambda self: None
        sports_day.QMessageBox.question = lambda *_args, **_kwargs: QMessageBox.Yes
        try:
            dialog = SportsDayDialog(self.owner, ICONS_DIR)
            try:
                dialog.categories = [{"id": "none", "name": "Bez kategorie"}]
                dialog.competitors = [
                    {"id": "anna", "name": "Anna", "category_id": "none", "gender": "F", "age": "10"},
                    {"id": "petr", "name": "Petr", "category_id": "none", "gender": "M", "age": "12"},
                ]
                dialog.results = {"run": {"anna": "12.5", "petr": "13.1", "ghost": "10.0"}}
                dialog.category_name_edit.setText("9-11")

                dialog._add_category()

                category_id = next(category["id"] for category in dialog.categories if category["name"] == "9-11")
                self.assertEqual(category_id, dialog.competitors[0]["category_id"])
                self.assertEqual("none", dialog.competitors[1]["category_id"])

                dialog._clear_all_competitors()

                self.assertEqual([], dialog.competitors)
                self.assertEqual({}, dialog.results)
            finally:
                dialog.close()
        finally:
            sports_day.QMessageBox.question = original_question
            sports_day.get_user_data_dir = original_data_dir
            SportsDayDialog._save_data = original_save


if __name__ == "__main__":
    unittest.main()
