from pathlib import Path
import unittest

from jsonl_cli.helpers import _build_offsets
from jsonl_cli.search import SearchSpec, _find_next, _matches, _parse_search_spec


FIXTURES = Path(__file__).parent / "fixtures"


class SearchSpecTests(unittest.TestCase):
    def test_plain_search_defaults_to_all_fields(self):
        spec, err = _parse_search_spec("alice")

        self.assertIsNone(err)
        self.assertEqual(spec, SearchSpec("alice"))

    def test_field_limited_search(self):
        spec, err = _parse_search_spec("user.name,items[].name: widget")

        self.assertIsNone(err)
        self.assertEqual(spec.paths, ("user.name", "items[].name"))
        self.assertEqual(spec.query, "widget")

    def test_quoted_query(self):
        spec, err = _parse_search_spec('user.name: "Alice Kim"')

        self.assertIsNone(err)
        self.assertEqual(spec.query, "Alice Kim")

    def test_regex_and_case_options(self):
        spec, err = _parse_search_spec("-r -c user.email: ^alice@")

        self.assertIsNone(err)
        self.assertTrue(spec.regex)
        self.assertTrue(spec.case_sensitive)

    def test_empty_query_reports_error(self):
        spec, err = _parse_search_spec("user.name:")

        self.assertIsNone(spec)
        self.assertEqual(err, "find expects a search string")

    def test_invalid_regex_reports_error(self):
        spec, err = _parse_search_spec("-r user.name: [")

        self.assertIsNone(spec)
        self.assertTrue(err.startswith("invalid regex:"))


class SearchMatchTests(unittest.TestCase):
    def test_all_field_search_includes_nested_values(self):
        obj = {
            "user": {"name": "Alice Kim"},
            "items": [{"name": "Widget"}],
        }

        self.assertTrue(_matches(obj, self.spec("widget")))

    def test_field_limited_search_does_not_match_other_fields(self):
        obj = {"user": {"name": "Alice Kim"}, "notes": "Alice referred order"}

        self.assertTrue(_matches(obj, self.spec("user.name: alice")))
        self.assertFalse(_matches(obj, self.spec("notes: kim")))

    def test_nested_object_path(self):
        obj = {"metadata": {"owner": {"name": "Dana"}}}

        self.assertTrue(_matches(obj, self.spec("metadata.owner.name: dana")))
        self.assertFalse(_matches(obj, self.spec("metadata.owner.email: dana")))

    def test_dict_wildcard_path(self):
        obj = {
            "metadata": {
                "owner": {"name": "Dana"},
                "reviewer": {"name": "Eli"},
            }
        }

        self.assertTrue(_matches(obj, self.spec("metadata.*.name: eli")))

    def test_array_wildcard_path(self):
        obj = {"items": [{"name": "Cable"}, {"name": "Widget Pro"}]}

        self.assertTrue(_matches(obj, self.spec("items[].name: widget")))

    def test_numeric_array_index_path(self):
        obj = {"items": [{"name": "Cable"}, {"name": "Widget Pro"}]}

        self.assertTrue(_matches(obj, self.spec("items.1.name: widget")))
        self.assertFalse(_matches(obj, self.spec("items.0.name: widget")))

    def test_array_value_search(self):
        obj = {"user": {"roles": ["admin", "editor"]}}

        self.assertTrue(_matches(obj, self.spec("user.roles: editor")))

    def test_case_sensitive_search(self):
        obj = {"notes": "ALICE referred this order"}

        self.assertTrue(_matches(obj, self.spec("notes: alice")))
        self.assertFalse(_matches(obj, self.spec("-c notes: alice")))

    def test_regex_search(self):
        obj = {"user": {"email": "alice@example.com"}}

        self.assertTrue(_matches(obj, self.spec("-r user.email: ^alice@.+\\.com$")))
        self.assertFalse(_matches(obj, self.spec("-r user.email: ^bob@")))

    def spec(self, raw):
        spec, err = _parse_search_spec(raw)
        self.assertIsNone(err)
        return spec


class SearchFileTests(unittest.TestCase):
    def setUp(self):
        self.path = str(FIXTURES / "search_sample.jsonl")
        self.offsets = _build_offsets(self.path)
        self.total = len(self.offsets) - 1

    def test_find_next_includes_current_for_new_search(self):
        hit = _find_next(self.path, self.offsets, self.total, 0, self.spec("user.name: alice"), 1, True)

        self.assertIsNotNone(hit)
        self.assertEqual(hit.idx, 0)
        self.assertFalse(hit.wrapped)

    def test_find_next_skips_current_for_repeat_search(self):
        hit = _find_next(self.path, self.offsets, self.total, 0, self.spec("items[].name: widget"), 1, False)

        self.assertIsNotNone(hit)
        self.assertEqual(hit.idx, 2)
        self.assertFalse(hit.wrapped)

    def test_find_next_wraps_forward(self):
        hit = _find_next(self.path, self.offsets, self.total, 3, self.spec("user.name: alice"), 1, False)

        self.assertIsNotNone(hit)
        self.assertEqual(hit.idx, 0)
        self.assertTrue(hit.wrapped)

    def test_find_next_wraps_backward(self):
        hit = _find_next(self.path, self.offsets, self.total, 0, self.spec("metadata.*.name: eli"), -1, False)

        self.assertIsNotNone(hit)
        self.assertEqual(hit.idx, 3)
        self.assertTrue(hit.wrapped)

    def test_find_next_returns_none_without_match(self):
        hit = _find_next(self.path, self.offsets, self.total, 0, self.spec("user.name: nobody"), 1, True)

        self.assertIsNone(hit)

    def test_find_next_skips_invalid_rows(self):
        path = str(FIXTURES / "mixed_sample.jsonl")
        offsets = _build_offsets(path)
        hit = _find_next(path, offsets, len(offsets) - 1, 0, self.spec("payload.value: omega"), 1, False)

        self.assertIsNotNone(hit)
        self.assertEqual(hit.idx, 3)

    def spec(self, raw):
        spec, err = _parse_search_spec(raw)
        self.assertIsNone(err)
        return spec


if __name__ == "__main__":
    unittest.main()
