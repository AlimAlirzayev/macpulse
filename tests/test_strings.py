import re
import unittest

from _loader import load_macpulse  # noqa: F401  (sets HOME and sys.path)

import macpulse_strings as ms


class StringTables(unittest.TestCase):
    def test_languages_declared(self):
        self.assertEqual(set(ms.STRINGS), {"az", "en", "ru"})

    def test_key_parity_across_languages(self):
        en = set(ms.STRINGS["en"])
        for lang in ("az", "ru"):
            keys = set(ms.STRINGS[lang])
            self.assertEqual(sorted(en - keys), [], f"{lang} is missing keys")
            self.assertEqual(sorted(keys - en), [], f"{lang} has extra keys")

    def test_values_are_nonempty_strings(self):
        for lang, table in ms.STRINGS.items():
            for k, v in table.items():
                self.assertIsInstance(v, str, (lang, k))
                self.assertTrue(v.strip(), (lang, k))

    def test_placeholders_match_across_languages(self):
        ph = lambda s: set(re.findall(r"\{(\w+)\}", s))  # noqa: E731
        for k, v in ms.STRINGS["en"].items():
            for lang in ("az", "ru"):
                self.assertEqual(ph(v), ph(ms.STRINGS[lang][k]), (lang, k))

    def test_t_falls_back_to_key(self):
        self.assertEqual(ms.t("en", "no.such.key"), "no.such.key")


if __name__ == "__main__":
    unittest.main()
