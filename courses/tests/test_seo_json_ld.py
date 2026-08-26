from django.test import SimpleTestCase

from website.seo import dumps_json_ld


class DumpsJsonLdTests(SimpleTestCase):
    def test_escapes_script_breakout(self):
        payload = {'name': 'Venue</script><script>alert(1)'}
        encoded = dumps_json_ld(payload)
        self.assertNotIn('</script>', encoded)
        self.assertIn('\\u003c', encoded)
        self.assertIn('Venue', encoded)
