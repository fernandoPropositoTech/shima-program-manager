"""Testes com dados simulados, isolados dos programas locais."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app import config
from app.shima_simulator import simulate_ssr_adjustment


class ShimaSimulatorTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.usb = root / "simulated_usb"
        self.usb.mkdir()
        repository = root / "repository"
        self.zero_zero = repository / "2026/ARAMIS/AR09FC1/00_ZERO_ZERO/AR09FC1.000"
        self.zero_zero.parent.mkdir(parents=True)
        self.content = b"ZERO-ZERO SIMULADO para testes.\n"
        self.zero_zero.write_bytes(self.content)
        paths_patch = patch.multiple(
            config, USB_PATH=self.usb, REPOSITORY_PATH=repository
        )
        paths_patch.start()
        self.addCleanup(paths_patch.stop)

    def test_adjustment_preserves_originals_and_program_names(self):
        repository_mtime = self.zero_zero.stat().st_mtime_ns
        for name in ("AR09FC1", "AR09M1", "AR09F1", "AR09C1"):
            with self.subTest(program=name):
                source = self.usb / f"{name}.000"
                adjusted = self.usb / f"{name}.112"
                source.write_bytes(self.content)
                original_mtime = source.stat().st_mtime_ns

                result = simulate_ssr_adjustment(name)

                self.assertEqual(result["status"], "sucesso")
                self.assertEqual(result["programa"], name)
                self.assertEqual(Path(result["arquivo_origem"]), source)
                self.assertEqual(Path(result["arquivo_ajustado"]), adjusted)
                self.assertTrue(adjusted.is_file())
                self.assertTrue(source.is_file())
                self.assertNotEqual(adjusted.read_bytes(), source.read_bytes())
                self.assertEqual(source.read_bytes(), self.content)
                self.assertEqual(source.stat().st_mtime_ns, original_mtime)

        self.assertEqual(self.zero_zero.read_bytes(), self.content)
        self.assertEqual(self.zero_zero.stat().st_mtime_ns, repository_mtime)

    def test_missing_usb_source_creates_no_file(self):
        result = simulate_ssr_adjustment("AR09FC1")

        self.assertEqual(result["status"], "origem_nao_encontrada")
        self.assertEqual(result["programa"], "AR09FC1")
        self.assertEqual(Path(result["arquivo_origem"]), self.usb / "AR09FC1.000")
        self.assertIsNone(result["arquivo_ajustado"])
        self.assertEqual(list(self.usb.iterdir()), [])

    def test_existing_adjusted_file_is_preserved(self):
        source = self.usb / "AR09FC1.000"
        adjusted = self.usb / "AR09FC1.112"
        source.write_bytes(self.content)
        adjusted.write_bytes(b"AJUSTE SIMULADO PREEXISTENTE")
        previous_content = adjusted.read_bytes()
        previous_mtime = adjusted.stat().st_mtime_ns

        with self.assertRaises(FileExistsError):
            simulate_ssr_adjustment("AR09FC1")

        self.assertEqual(adjusted.read_bytes(), previous_content)
        self.assertEqual(adjusted.stat().st_mtime_ns, previous_mtime)
        self.assertEqual(source.read_bytes(), self.content)

    def test_rejects_paths_as_program_names(self):
        for name in ("", "../AR09FC1", "..\\AR09FC1", "C:AR09FC1"):
            with self.subTest(program=name):
                with self.assertRaises(ValueError):
                    simulate_ssr_adjustment(name)
        self.assertEqual(list(self.usb.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
