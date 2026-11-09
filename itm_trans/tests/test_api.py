import unittest
from unittest.mock import patch

from itm_trans import api


class TestItemTranslation(unittest.TestCase):
    def test_mixed_item_name_keeps_codes_and_translates_unknown_text(self):
        with patch(
            "itm_trans.api.translate_text_safely",
            return_value=("مكثف", True),
        ) as translator:
            result = api.translate_en_to_ar("332 AFM A/C CONDENSER CTR")

        self.assertEqual(result, "332 AFM A/C مكثف CTR")
        translator.assert_called_once_with("CONDENSER")

    def test_provider_failure_returns_empty_string_for_retry(self):
        with patch(
            "itm_trans.api.translate_text_safely",
            return_value=("CONDENSER", False),
        ):
            result = api.translate_en_to_ar("332 AFM A/C CONDENSER CTR")

        self.assertEqual(result, "")

    def test_google_error_page_is_rejected(self):
        self.assertTrue(
            api.is_bad_translation(
                "Error 500 (Server Error)!! That's an error. Please try again later."
            )
        )


if __name__ == "__main__":
    unittest.main()
