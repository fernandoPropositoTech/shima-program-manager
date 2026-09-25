"""Testes do envio para o pen drive simulado."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app import config
from app.program_finder import find_program
from app.program_sender import send_program


class ProgramSenderTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        repository = root / "repository"
        source = repository / "2026/ARAMIS/AR09FC1/00_ZERO_ZERO/AR09FC1.000"
        source.parent.mkdir(parents=True)
        source.write_text("ZERO-ZERO SIMULADO para testes.", encoding="utf-8")
        self.usb = root / "simulated_usb"
        self.usb.mkdir()
        paths_patch = patch.multiple(
            config, REPOSITORY_PATH=repository, USB_PATH=self.usb
        )
        paths_patch.start()
        self.addCleanup(paths_patch.stop)

    def test_send_existing_zero_zero(self):
        destination = self.usb / "AR09FC1.000"
        source = Path(find_program("AR09FC1")["caminho_arquivo"])
        original_content = source.read_bytes()
        original_mtime = source.stat().st_mtime_ns

        result = send_program("AR09FC1")

        self.assertEqual(result["status"], "sucesso")
        self.assertEqual(result["programa"], "AR09FC1")
        self.assertEqual(Path(result["arquivo_origem"]), source)
        self.assertEqual(Path(result["arquivo_destino"]), destination)
        self.assertTrue(destination.is_file())
        self.assertTrue(source.is_file())
        self.assertEqual(destination.read_bytes(), original_content)
        self.assertEqual(source.read_bytes(), original_content)
        self.assertEqual(source.stat().st_mtime_ns, original_mtime)

    def test_missing_program_creates_no_file(self):
        before = set(self.usb.iterdir())

        result = send_program("PROGRAMA_INEXISTENTE")

        self.assertEqual(result["status"], "nao_encontrado")
        self.assertIsNone(result["arquivo_origem"])
        self.assertIsNone(result["arquivo_destino"])
        self.assertEqual(set(self.usb.iterdir()), before)


if __name__ == "__main__":
    unittest.main()
