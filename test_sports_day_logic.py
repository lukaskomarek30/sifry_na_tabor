import math
import unittest
from unittest.mock import patch

from sports_day import (
    _category_age_range,
    _clean_name,
    _competition_ranks,
    _duplicate_named_item,
    _parse_age_value,
    compute_event_points,
    parse_metric_value,
)
from sports_day_print import SportsDayPrintMixin, _sports_print_font_family, _sports_print_font_style


class SportsDayScoringTests(unittest.TestCase):
    def setUp(self):
        self.categories = [{"id": "all", "name": "Všichni"}]
        self.competitors = [
            {"id": "petr", "name": "Petr", "category_id": "all", "gender": "M"},
            {"id": "jan", "name": "Jan", "category_id": "all", "gender": "M"},
            {"id": "tomas", "name": "Tomáš", "category_id": "all", "gender": "M"},
        ]
        self.event = {"id": "run", "metric": "time", "direction": "asc"}
        self.results = {"run": {"petr": "10.5", "jan": "10.5", "tomas": "9.8"}}

    def test_dense_tie_has_equal_rank_and_original_points(self):
        points = compute_event_points(self.event, self.categories, self.competitors, self.results)
        self.assertEqual(points, {"tomas": 3, "petr": 2, "jan": 2})
        self.assertEqual(_competition_ranks([9.8, 10.5, 10.5]), [1, 2, 2])
        self.assertEqual(_competition_ranks([9.8, 10.5, 10.5, 11.0]), [1, 2, 2, 3])
        self.assertEqual(
            _competition_ranks([1, 1, 2, 2, 3, 3, 4, 5, 6, 7, 8]),
            [1, 1, 2, 2, 3, 3, 4, 5, 6, 7, 8],
        )

    def test_tie_uses_two_decimal_places(self):
        results = {"run": {"petr": "10.501", "jan": "10.499", "tomas": "9.8"}}
        points = compute_event_points(self.event, self.categories, self.competitors, results)
        self.assertEqual(points["petr"], points["jan"])

    def test_normalized_points_use_common_ten_to_one_scale(self):
        event = dict(self.event, _normalize_points=True, _normalized_points_max=10)
        points = compute_event_points(event, self.categories, self.competitors, self.results)
        self.assertEqual(points, {"tomas": 10, "petr": 5.5, "jan": 5.5})

    def test_normalized_points_accept_custom_maximum(self):
        event = dict(self.event, _normalize_points=True, _normalized_points_max=20)
        points = compute_event_points(event, self.categories, self.competitors, self.results)
        self.assertEqual(points, {"tomas": 20, "petr": 10.5, "jan": 10.5})

    def test_time_parser_rejects_invalid_minutes_seconds(self):
        self.assertEqual(parse_metric_value("1:05.5", "time"), 65.5)
        self.assertEqual(parse_metric_value("0:59.99", "time"), 59.99)
        for raw in ("3:70", "1:59.999", "-1:20", "1:-2", "-5", "1:2:3"):
            with self.subTest(raw=raw):
                self.assertIsNone(parse_metric_value(raw, "time"))

    def test_duplicate_names_ignore_case_unicode_width_and_extra_spaces(self):
        items = [{"id": "run", "name": "Běh na 60 m"}]
        self.assertEqual(_clean_name("  Petr   Novák  "), "Petr Novák")
        self.assertIsNotNone(_duplicate_named_item(items, " běh  NA  60 m "))
        self.assertIsNone(_duplicate_named_item(items, "Skok do dálky"))
        self.assertIsNone(_duplicate_named_item(items, "BĚH NA 60 M", exclude_id="run"))

    def test_age_category_parser_supports_common_czech_ranges(self):
        self.assertEqual(_parse_age_value("10 let"), 10)
        self.assertEqual(_category_age_range("9-11 let"), (9, 11))
        self.assertEqual(_category_age_range("9–11"), (9, 11))
        self.assertEqual(_category_age_range("do 8 let"), (0.0, 8))
        self.assertEqual(_category_age_range("12+"), (12, math.inf))


class SportsDayEventCardTests(unittest.TestCase):
    def test_print_font_helpers_keep_defaults_and_styles(self):
        self.assertEqual(_sports_print_font_family(None)["qfont"], "Segoe UI")
        self.assertEqual(_sports_print_font_family("serif")["qfont"], "Georgia")

        bold_italic = _sports_print_font_style("bold_italic")
        self.assertTrue(bold_italic["bold"])
        self.assertTrue(bold_italic["italic"])
        self.assertEqual(_sports_print_font_style("missing")["body_weight"], "400")

    def test_event_card_roster_people_reads_age_from_groups(self):
        class Dummy(SportsDayPrintMixin):
            pass

        entries = [
            {
                "name": "Anna Nová",
                "group_name": "Modří",
                "role": "Dítě",
                "fields": {"Věk": "10", "Poznámka": "běhá ráda"},
            },
            {
                "name": "Kapitán",
                "group_name": "Modří",
                "role": "Vedoucí",
                "fields": {},
            },
        ]

        with patch("sports_day_print.roster_entries", return_value=entries):
            people = Dummy()._event_card_roster_people()

        self.assertEqual(
            people,
            [
                {"name": "Anna Nová", "age": "10", "group_name": "Modří", "role": "Dítě"},
                {"name": "Kapitán", "age": "", "group_name": "Modří", "role": "Vedoucí"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
