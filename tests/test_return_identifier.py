"""Identificacao com arquivos simulados e pastas temporarias."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app import config
from app.return_identifier import identify_return


class ReturnIdentifierTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repository = self.root / "repository"
        self.usb = self.root / "simulated_usb"
        self.repository.mkdir()
        self.usb.mkdir()
        paths = patch.multiple(config, REPOSITORY_PATH=self.repository, USB_PATH=self.usb)
        paths.start()
        self.addCleanup(paths.stop)

    def create_zero_zero(self, year, client, program):
        path = self.repository / str(year) / client / program / "00_ZERO_ZERO" / f"{program}.000"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"ZERO-ZERO SIMULADO")
        return path

    def create_return(self, program):
        path = self.usb / f"{program}.112"
        path.write_bytes(b"AJUSTADO SIMULADO")
        return path

    def snapshot(self):
        return {
            str(path.relative_to(self.root)): (path.read_bytes(), path.stat().st_mtime_ns)
            if path.is_file() else None
            for path in self.root.rglob("*")
        }

    def identify_unchanged(self, filename):
        before = self.snapshot()
        result = identify_return(filename)
        self.assertEqual(self.snapshot(), before)
        return result

    def check_unique(self, year, client, program):
        source = self.create_zero_zero(year, client, program)
        adjusted = self.create_return(program)
        result = self.identify_unchanged(adjusted.name)
        self.assertEqual(result["status"], "identificado")
        self.assertEqual(result["ano"], year)
        self.assertEqual(result["cliente"], client)
        self.assertEqual(result["programa"], program)
        self.assertEqual(Path(result["arquivo_zero_zero"]), source)
        self.assertEqual(Path(result["arquivo_ajustado"]), adjusted)
        self.assertEqual(len(result["correspondencias"]), 1)

    def test_identifies_aramis(self):
        self.check_unique(2026, "ARAMIS", "AR09FC1")

    def test_identifies_urbam(self):
        self.check_unique(2026, "URBAM", "UBFC1")

    def test_client_is_not_inferred_from_prefix(self):
        self.check_unique(2026, "CLIENTE_TESTE", "AR99FC1")

    def test_arbitrary_names_and_year(self):
        self.check_unique(2024, "OUTRO_CLIENTE", "XYZ123")
        self.check_unique(2027, "CLIENTE_NOVO", "TESTE01")

    def test_no_corresponding_zero_zero(self):
        self.create_return("SEM_ORIGEM")
        self.create_zero_zero(2026, "CLIENTE", "OUTRO")
        result = self.identify_unchanged("SEM_ORIGEM.112")
        self.assertEqual(result["status"], "nao_identificado")
        self.assertEqual(result["correspondencias"], [])
        self.assertIsNone(result["arquivo_zero_zero"])
        self.assertIsNone(result["cliente"])

    def test_ambiguous_matches_are_not_selected(self):
        first = self.create_zero_zero(2025, "CLIENTE_A", "ABC1")
        second = self.create_zero_zero(2026, "CLIENTE_B", "ABC1")
        self.create_return("ABC1")
        result = self.identify_unchanged("ABC1.112")
        self.assertEqual(result["status"], "ambiguo")
        for key in ("ano", "cliente", "arquivo_zero_zero"):
            self.assertIsNone(result[key])
        self.assertEqual(result["correspondencias"], [
            {"ano": 2025, "cliente": "CLIENTE_A", "programa": "ABC1", "arquivo_zero_zero": str(first)},
            {"ano": 2026, "cliente": "CLIENTE_B", "programa": "ABC1", "arquivo_zero_zero": str(second)},
        ])

    def test_missing_adjusted_file(self):
        self.create_zero_zero(2026, "CLIENTE", "ABC1")
        result = self.identify_unchanged("ABC1.112")
        self.assertEqual(result["status"], "arquivo_nao_encontrado")
        self.assertEqual(result["correspondencias"], [])

    def test_invalid_names_are_rejected(self):
        before = self.snapshot()
        for filename in (None, "", ".112", "..112", "../ABC1.112", "..\\ABC1.112",
                         "/ABC1.112", "C:ABC1.112", "ABC1.112:stream", "*.112",
                         "A?.112", "A\x00.112", "CON.112", "LPT1.112", "ABC1.000",
                         " ABC1.112", "ABC1 .112", "ABC1.112 "):
            with self.subTest(filename=filename):
                with self.assertRaises(ValueError):
                    identify_return(filename)
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
