from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import tempfile
import unittest

from jsonl_cli.containers import RowData
from jsonl_cli.helpers import (
    _build_offsets,
    _human_bytes,
    _parse_row,
    _read_line_at,
    _scan_brief,
    _validate_path,
)


FIXTURES = Path(__file__).parent / "fixtures"


class HelperTests(unittest.TestCase):
    def test_human_bytes_formats_byte_ranges(self):
        self.assertEqual(_human_bytes(0), "0 B")
        self.assertEqual(_human_bytes(1023), "1023 B")
        self.assertEqual(_human_bytes(1024), "1.00 KiB")
        self.assertEqual(_human_bytes(1024 * 1024), "1.00 MiB")

    def test_validate_path_accepts_jsonl_file(self):
        path = str(FIXTURES / "search_sample.jsonl")

        self.assertEqual(_validate_path(path), path)

    def test_validate_path_rejects_non_jsonl_extension(self):
        with tempfile.NamedTemporaryFile(suffix=".txt") as f:
            stderr = StringIO()
            with redirect_stderr(stderr), self.assertRaises(SystemExit) as cm:
                _validate_path(f.name)

        self.assertEqual(cm.exception.code, 2)
        self.assertIn("FILE must end with .jsonl", stderr.getvalue())

    def test_validate_path_rejects_missing_file(self):
        path = str(FIXTURES / "missing.jsonl")
        stderr = StringIO()

        with redirect_stderr(stderr), self.assertRaises(SystemExit) as cm:
            _validate_path(path)

        self.assertEqual(cm.exception.code, 2)
        self.assertIn("FILE not found", stderr.getvalue())

    def test_build_offsets_and_read_line_at(self):
        path = str(FIXTURES / "mixed_sample.jsonl")
        offsets = _build_offsets(path)

        self.assertEqual(offsets[0], 0)
        self.assertEqual(len(offsets), 5)
        self.assertEqual(_read_line_at(path, offsets[0], offsets[1]), b'{"id":1,"status":"ok","payload":{"value":"alpha"}}\n')
        self.assertEqual(_read_line_at(path, offsets[2], offsets[3]), b"\n")

    def test_scan_brief_counts_lines_columns_and_invalid_rows(self):
        path = str(FIXTURES / "summary_sample.jsonl")
        line_count, size, cols, invalid = _scan_brief(path)

        self.assertEqual(line_count, 5)
        self.assertEqual(size, Path(path).stat().st_size)
        self.assertEqual(cols, ["alpha", "beta", "gamma"])
        self.assertEqual(invalid, 1)

    def test_parse_row_valid_object(self):
        row = _parse_row(b'{"name":"Alice","count":2}\n', 0)

        self.assertEqual(row, RowData(ok=True, title="Row 1: OK", obj={"name": "Alice", "count": 2}))

    def test_parse_row_empty_line(self):
        row = _parse_row(b"\n", 3)

        self.assertEqual(row, RowData(ok=True, title="Row 4: (empty line)", obj=""))

    def test_parse_row_invalid_json_keeps_raw_fallback(self):
        row = _parse_row(b"{bad json\n", 1)

        self.assertFalse(row.ok)
        self.assertIn("Row 2: INVALID JSON", row.title)
        self.assertEqual(row.raw_fallback, "{bad json")


if __name__ == "__main__":
    unittest.main()
