from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import unittest

from jsonl_cli.cli import main


FIXTURES = Path(__file__).parent / "fixtures"


class CliTests(unittest.TestCase):
    def test_brief_mode_prints_summary_and_exits_without_curses(self):
        stdout = StringIO()

        with redirect_stdout(stdout):
            main([str(FIXTURES / "summary_sample.jsonl"), "--brief"])

        output = stdout.getvalue()
        self.assertIn("Lines: 5", output)
        self.assertIn("Invalid JSON lines: 1", output)
        self.assertIn("  - alpha", output)
        self.assertIn("  - gamma", output)


if __name__ == "__main__":
    unittest.main()
