"""Post-execution audit helpers; no model/browser calls."""
import base64
import importlib.util
from io import BytesIO
from pathlib import Path
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("four_audit_test", ROOT / "scripts/audit-expanded-four-way.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class AuditTests(unittest.TestCase):
    def test_zero_usage_is_known_but_missing_usage_is_not(self):
        row = {"seq": 1, "input": 0, "cached_input": 0, "output": 0}
        usage = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}
        audit.validate_usage(row, usage)
        for key in usage:
            with self.subTest(key=key), self.assertRaises(AssertionError):
                audit.validate_usage(row, {k: v for k, v in usage.items() if k != key})

    def test_wrong_or_negative_usage_and_fabricated_request_count_are_rejected(self):
        row = {"seq": 1, "input": 10, "cached_input": 8, "output": 2}
        usage = {"input_tokens": 10, "cached_input_tokens": 8, "output_tokens": 2}
        for changed in ({"input": 11}, {"cached_input": -1}, {"requests": 4}, {"first_input": 10}, {"cost": 0}):
            with self.subTest(changed=changed), self.assertRaises(AssertionError):
                audit.validate_usage({**row, **changed}, usage)

    def test_review_normalization_leaves_external_urls_visible_and_arguments_unchanged(self):
        args = {"url": "http://127.0.0.1:1234/t/" + "a" * 32 + "/article", "other": "https://example.com/private"}
        original = dict(args)
        text = audit.normalized(args)
        self.assertIn("FIXTURE/article", text)
        self.assertIn("https://example.com/private", text)
        self.assertEqual(args, original)

    def test_png_jpeg_and_webp_are_verified_as_images_not_assumed_png(self):
        for mime, encoding in (("image/png", "PNG"), ("image/jpeg", "JPEG"), ("image/webp", "WEBP")):
            with self.subTest(mime=mime):
                stream = BytesIO()
                Image.new("RGB", (16, 9), "white").save(stream, format=encoding)
                result = audit.image_evidence({"mimeType": mime, "data": base64.b64encode(stream.getvalue()).decode()})
                self.assertEqual(result["dimensions"], (16, 9))
                self.assertEqual(result["mime_type"], mime)
                self.assertGreater(result["bytes"], 0)

    def test_mislabeled_image_is_rejected(self):
        stream = BytesIO()
        Image.new("RGB", (2, 2)).save(stream, format="JPEG")
        with self.assertRaises(AssertionError):
            audit.image_evidence({"mimeType": "image/png", "data": base64.b64encode(stream.getvalue()).decode()})


if __name__ == "__main__":
    unittest.main()
