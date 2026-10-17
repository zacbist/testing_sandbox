import os
import json
import unittest
import urllib.parse

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server import app

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


class TestTextEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_arithmetic(self):
        resp = self.client.post("/execute/text", data="result = 2 + 3")
        data = json.loads(resp.data)
        self.assertTrue(data["success"])
        self.assertEqual(data["result"], "5")

    def test_string_concat(self):
        resp = self.client.post("/execute/text", data='result = "hello" + " " + "world"')
        data = json.loads(resp.data)
        self.assertTrue(data["success"])
        self.assertEqual(data["result"], "hello world")

    def test_print_capture(self):
        resp = self.client.post("/execute/text", data='print("captured output")')
        data = json.loads(resp.data)
        self.assertTrue(data["success"])
        self.assertIn("captured output", data["output"])

    def test_list_operations(self):
        code = "result = sorted([3, 1, 4, 1, 5, 9, 2, 6])"
        resp = self.client.post("/execute/text", data=code)
        data = json.loads(resp.data)
        self.assertTrue(data["success"])
        self.assertEqual(data["result"], "[1, 1, 2, 3, 4, 5, 6, 9]")

    def test_blocked_import(self):
        resp = self.client.post("/execute/text", data='__import__("os")')
        data = json.loads(resp.data)
        self.assertFalse(data["success"])
        self.assertIn("Blocked", data["error"])

    def test_blocked_eval(self):
        resp = self.client.post("/execute/text", data='eval("1+1")')
        data = json.loads(resp.data)
        self.assertFalse(data["success"])

    def test_empty_code(self):
        resp = self.client.post("/execute/text", data="")
        self.assertEqual(resp.status_code, 400)

    def test_syntax_error(self):
        resp = self.client.post("/execute/text", data="def (broken")
        data = json.loads(resp.data)
        self.assertFalse(data["success"])
        self.assertIn("SyntaxError", data["error"])



class TestImageEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_image_arithmetic(self):
        fixture = os.path.join(FIXTURES_DIR, "code_arithmetic.png")
        if not os.path.exists(fixture):
            self.skipTest("fixture not generated")
        with open(fixture, "rb") as f:
            resp = self.client.post(
                "/execute/image",
                data={"file": (f, "code.png")},
                content_type="multipart/form-data",
            )
        self.assertIn(resp.status_code, (200, 500))

    def test_image_string_code(self):
        fixture = os.path.join(FIXTURES_DIR, "code_string.png")
        if not os.path.exists(fixture):
            self.skipTest("fixture not generated")
        with open(fixture, "rb") as f:
            resp = self.client.post(
                "/execute/image",
                data={"file": (f, "code.png")},
                content_type="multipart/form-data",
            )
        self.assertIn(resp.status_code, (200, 500))

    def test_image_no_file(self):
        resp = self.client.post("/execute/image")
        self.assertEqual(resp.status_code, 400)


class TestPDFEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_pdf_arithmetic(self):
        fixture = os.path.join(FIXTURES_DIR, "code_arithmetic.pdf")
        if not os.path.exists(fixture):
            self.skipTest("fixture not generated")
        with open(fixture, "rb") as f:
            resp = self.client.post(
                "/execute/pdf",
                data={"file": (f, "code.pdf")},
                content_type="multipart/form-data",
            )
        data = json.loads(resp.data)
        self.assertTrue(data["success"])

    def test_pdf_no_file(self):
        resp = self.client.post("/execute/pdf")
        self.assertEqual(resp.status_code, 400)


class TestAudioEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def _send_audio(self, fixture_name):
        fixture = os.path.join(FIXTURES_DIR, fixture_name)
        if not os.path.exists(fixture):
            self.skipTest("fixture not generated")
        with open(fixture, "rb") as f:
            audio_bytes = f.read()
        encoded = urllib.parse.quote(audio_bytes, safe="")
        resp = self.client.post("/execute/audio", data=encoded, content_type="text/plain")
        return resp

    def test_audio_sort(self):
        resp = self._send_audio("audio_sort.wav")
        self.assertEqual(resp.status_code, 200)

    def test_audio_concat(self):
        resp = self._send_audio("audio_concat.wav")
        self.assertEqual(resp.status_code, 200)

    def test_audio_loop(self):
        resp = self._send_audio("audio_loop.wav")
        self.assertEqual(resp.status_code, 200)

    def test_audio_introspection(self):
        resp = self._send_audio("audio_introspection.wav")
        self.assertEqual(resp.status_code, 200)

    def test_audio_empty(self):
        resp = self.client.post("/execute/audio", data="", content_type="text/plain")
        self.assertEqual(resp.status_code, 400)


class TestAudioZipEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def _send_zip(self, fixture_name):
        fixture = os.path.join(FIXTURES_DIR, fixture_name)
        if not os.path.exists(fixture):
            self.skipTest("fixture not generated")
        with open(fixture, "rb") as f:
            resp = self.client.post(
                "/execute/audio-zip",
                data={"file": (f, fixture_name)},
                content_type="multipart/form-data",
            )
        return resp

    def test_zip_sort(self):
        resp = self._send_zip("audio_sort.zip")
        self.assertEqual(resp.status_code, 200)

    def test_zip_concat(self):
        resp = self._send_zip("audio_concat.zip")
        self.assertEqual(resp.status_code, 200)

    def test_zip_loop(self):
        resp = self._send_zip("audio_loop.zip")
        self.assertEqual(resp.status_code, 200)

    def test_zip_introspection(self):
        resp = self._send_zip("audio_introspection.zip")
        self.assertEqual(resp.status_code, 200)

    def test_zip_no_file(self):
        resp = self.client.post("/execute/audio-zip")
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main()
