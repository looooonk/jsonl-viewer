import unittest

from jsonl_cli.colors import _hex_to_rgb, _key_to_pair_id, _load_theme, _rgb_to_xterm256


class ColorTests(unittest.TestCase):
    def test_hex_to_rgb_accepts_hash_prefix(self):
        self.assertEqual(_hex_to_rgb("#ff00aa"), (255, 0, 170))
        self.assertEqual(_hex_to_rgb("00ff11"), (0, 255, 17))

    def test_rgb_to_xterm256_handles_grayscale_edges(self):
        self.assertEqual(_rgb_to_xterm256(0, 0, 0), 16)
        self.assertEqual(_rgb_to_xterm256(255, 255, 255), 231)
        self.assertEqual(_rgb_to_xterm256(128, 128, 128), 244)

    def test_rgb_to_xterm256_handles_color_cube(self):
        self.assertEqual(_rgb_to_xterm256(255, 0, 0), 196)
        self.assertEqual(_rgb_to_xterm256(0, 255, 0), 46)
        self.assertEqual(_rgb_to_xterm256(0, 0, 255), 21)

    def test_key_to_pair_id_stays_within_pair_range(self):
        for key in ("name", "email", "nested.value"):
            pair_id = _key_to_pair_id(key, 4)
            self.assertGreaterEqual(pair_id, 1)
            self.assertLessEqual(pair_id, 4)

    def test_load_theme_returns_key_colors(self):
        colors = _load_theme("catppuccin-mocha")

        self.assertTrue(colors)
        self.assertTrue(all(color.startswith("#") for color in colors))

    def test_load_theme_falls_back_for_unknown_theme(self):
        self.assertEqual(_load_theme("does-not-exist"), _load_theme("catppuccin-mocha"))


if __name__ == "__main__":
    unittest.main()
