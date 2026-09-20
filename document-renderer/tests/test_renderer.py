import io
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import RenderDocxRequest, _render_docx_bytes


class RendererTest(unittest.TestCase):
    def test_blank_template_generates_docx(self):
        payload=_render_docx_bytes(RenderDocxRequest(markdown="# Title\n\nBody",title="Test",template_id=""))
        self.assertTrue(payload.startswith(b"PK"))
        self.assertGreater(len(payload),1000)


if __name__=="__main__":
    unittest.main()
