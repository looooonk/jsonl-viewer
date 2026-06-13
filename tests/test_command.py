import unittest

from jsonl_cli.command import _apply_command


class CommandTests(unittest.TestCase):
    def test_empty_command_keeps_current_row(self):
        self.assertEqual(_apply_command("", 10, 4), (4, None))

    def test_goto_moves_to_one_indexed_row(self):
        self.assertEqual(_apply_command("goto 3", 10, 0), (2, None))
        self.assertEqual(_apply_command("g 1", 10, 5), (0, None))

    def test_goto_clamps_to_file_bounds(self):
        self.assertEqual(_apply_command("goto -5", 10, 4), (0, None))
        self.assertEqual(_apply_command("goto 99", 10, 4), (9, None))

    def test_goto_reports_invalid_number(self):
        self.assertEqual(_apply_command("goto nope", 10, 4), (4, "goto expects an integer row number"))

    def test_goto_reports_empty_file(self):
        self.assertEqual(_apply_command("goto 1", 0, 0), (0, "file has no rows"))

    def test_quit_commands_return_sentinel(self):
        for cmd in ("q", "quit", "exit"):
            self.assertEqual(_apply_command(cmd, 10, 4), (-1, None))

    def test_unknown_command_reports_input(self):
        self.assertEqual(_apply_command("sort user.name", 10, 4), (4, "unknown command: sort user.name"))


if __name__ == "__main__":
    unittest.main()
