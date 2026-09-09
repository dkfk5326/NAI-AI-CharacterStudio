"""Frontend MIME types must remain valid with Windows registry overrides."""
import mimetypes
import tempfile
import unittest
from pathlib import Path
from backend.app.main import FrontendStaticFiles, index


class FrontendStaticTests(unittest.IsolatedAsyncioTestCase):
    async def test_registry_types_do_not_block_modules_or_styles(self):
        with tempfile.TemporaryDirectory() as directory:
            files = FrontendStaticFiles(directory=directory)
            for suffix, expected in [('.js', 'text/javascript'), ('.mjs', 'text/javascript'), ('.css', 'text/css')]:
                filename = 'asset' + suffix
                Path(directory, filename).write_text('/* test */', encoding='utf-8')
                original = mimetypes.guess_type(filename)[0]
                try:
                    mimetypes.add_type('text/plain', suffix)
                    response = await files.get_response(filename, {'type': 'http', 'method': 'GET', 'headers': []})
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.headers['content-type'], expected + '; charset=utf-8')
                finally:
                    if original:
                        mimetypes.add_type(original, suffix)
                    else:
                        mimetypes.types_map.pop(suffix, None)

    def test_entry_page_revalidates_after_update(self):
        response = index()
        self.assertEqual(response.headers['cache-control'], 'no-cache')
        self.assertTrue(response.headers['content-type'].startswith('text/html'))
