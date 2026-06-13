import unittest

from jsonl_cli.render import _json_atom, _render_json_styled, _wrap_styled_lines


def joined(lines):
    return ["".join(text for text, _ in line) for line in lines]


class RenderTests(unittest.TestCase):
    def key_attr(self, key):
        return 100 + len(key)

    def test_json_atom_preserves_unicode(self):
        self.assertEqual(_json_atom("cafe"), '"cafe"')
        self.assertEqual(_json_atom("\ud55c\uae00"), '"\ud55c\uae00"')
        self.assertEqual(_json_atom(True), "true")
        self.assertEqual(_json_atom(None), "null")

    def test_render_flat_object_styles_keys(self):
        lines = _render_json_styled({"name": "Alice", "count": 2}, 0, self.key_attr, 0, 2)

        self.assertEqual(joined(lines), ['{', '  "name": "Alice",', '  "count": 2', '}'])
        self.assertEqual(lines[1][1], ('"name"', self.key_attr("name")))

    def test_render_nested_object_and_list(self):
        lines = _render_json_styled({"items": [{"name": "Widget"}]}, 0, self.key_attr, 0, 2)

        self.assertEqual(
            joined(lines),
            [
                "{",
                '  "items": [',
                "    {",
                '      "name": "Widget"',
                "    }",
                "  ]",
                "}",
            ],
        )

    def test_render_root_list(self):
        lines = _render_json_styled([1, "two", False], 0, self.key_attr, 0, 2)

        self.assertEqual(joined(lines), ["[", "  1,", '  "two",', "  false", "]"])

    def test_wrap_styled_lines_preserves_text_and_attrs(self):
        lines = [[("  ", 0), ('"name"', 1), (': "Alice Wonderland"', 0)]]
        wrapped = _wrap_styled_lines(lines, 12)

        self.assertTrue(all(len(line) <= 12 for line in joined(wrapped)))
        self.assertEqual(joined(wrapped)[0], '  "name": "A')
        self.assertNotEqual(joined(wrapped)[-1].strip(), "")
        self.assertIn(('"name"', 1), wrapped[0])

    def test_wrap_width_one_returns_original_lines(self):
        lines = [[("abcdef", 3)]]

        self.assertIs(_wrap_styled_lines(lines, 1), lines)


if __name__ == "__main__":
    unittest.main()
