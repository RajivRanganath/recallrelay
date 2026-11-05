import base64
from io import BytesIO
import unittest

from PIL import Image

from evidence.backend.images import decode_image
from evidence.backend.json_input import strict_json
from evidence.backend.validation import InvalidInput


class ImageAndJSONTests(unittest.TestCase):
    def encoded(self, size=(32, 16), format='PNG'):
        with BytesIO() as output, Image.new('RGB', size, 'white') as image:
            image.save(output, format=format)
            return base64.b64encode(output.getvalue()).decode()

    def test_both_supported_formats_decode_and_representations_omit_bytes(self):
        for format, mime in [('PNG', 'image/png'), ('JPEG', 'image/jpeg')]:
            image = decode_image(self.encoded(format=format), mime)
            self.assertEqual((image.width, image.height), (32, 16))
            self.assertNotIn('content=', repr(image))

    def test_mime_mismatch_dimensions_and_truncation_are_rejected(self):
        for encoded, mime in [(self.encoded(), 'image/jpeg'),
                              (self.encoded((4097, 1)), 'image/png'),
                              (self.encoded((3000, 3000)), 'image/png'),
                              (base64.b64encode(base64.b64decode(self.encoded())[:-16]).decode(), 'image/png')]:
            with self.subTest(mime=mime, size=len(encoded)):
                with self.assertRaises(InvalidInput):
                    decode_image(encoded, mime)

    def test_animated_png_is_rejected(self):
        with BytesIO() as output, Image.new('RGB', (32, 16), 'white') as first, Image.new('RGB', (32, 16), 'black') as second:
            first.save(output, format='PNG', save_all=True, append_images=[second])
            with self.assertRaises(InvalidInput):
                decode_image(base64.b64encode(output.getvalue()).decode(), 'image/png')

    def test_ambiguous_non_finite_and_deep_json_are_rejected(self):
        for raw in ('{"a":1,"a":2}', '{"nested":{"a":1,"a":2}}', '{"a":NaN}',
                    '{"a":Infinity}', '{"a":1e999}', '[' * 1500 + '0' + ']' * 1500, b'\xff'):
            with self.assertRaises(InvalidInput):
                strict_json(raw)
        self.assertEqual(strict_json('{"a":[1,2]}'), {'a': [1, 2]})
