import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from i18n import t, set_language, get_language, get_language_name, SUPPORTED_LANGUAGES, _LANG_DICTS
from i18n.en import TRANSLATIONS as EN_TRANS

class TestI18n(unittest.TestCase):
    def setUp(self):
        set_language("en")

    def test_default_language_is_english(self):
        self.assertEqual(get_language(), "en")
        self.assertEqual(get_language_name("en"), "English")

    def test_all_8_languages_registered(self):
        expected = {"en", "pt", "es", "fr", "de", "it", "ru", "uk"}
        self.assertEqual(set(SUPPORTED_LANGUAGES.keys()), expected)

    def test_dictionary_key_coverage(self):
        """Every translation dictionary should cover all keys defined in English."""
        en_keys = set(EN_TRANS.keys())
        for lang_code, d in _LANG_DICTS.items():
            diff = en_keys - set(d.keys())
            self.assertEqual(len(diff), 0, f"Language '{lang_code}' is missing keys: {diff}")

    def test_language_switching(self):
        set_language("pt")
        self.assertEqual(get_language(), "pt")
        self.assertIn("Criar", t("menu_create"))

        set_language("es")
        self.assertEqual(get_language(), "es")
        self.assertIn("Crear", t("menu_create"))

        set_language("fr")
        self.assertEqual(get_language(), "fr")
        self.assertIn("Créer", t("menu_create"))

        set_language("de")
        self.assertEqual(get_language(), "de")
        self.assertIn("Erstellen", t("menu_create"))

        set_language("it")
        self.assertEqual(get_language(), "it")
        self.assertIn("Crea", t("menu_create"))

        set_language("ru")
        self.assertEqual(get_language(), "ru")
        self.assertIn("Создать", t("menu_create"))

        set_language("uk")
        self.assertEqual(get_language(), "uk")
        self.assertIn("Створити", t("menu_create"))

    def test_formatting_substitution(self):
        set_language("en")
        formatted = t("local_address", ip="127.0.0.1", port=54321)
        self.assertIn("127.0.0.1:54321", formatted)

if __name__ == "__main__":
    unittest.main()
