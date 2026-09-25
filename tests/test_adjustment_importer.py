"""Importacoes controladas, sem acessar programas industriais reais."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app import config
from app.adjustment_importer import import_adjustment


class AdjustmentImporterTests(unittest.TestCase):
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
        self.zero = self.create_zero(2026, "ARAMIS", "AR09FC1")
        self.source = self.usb / "AR09FC1.112"
        self.source.write_bytes(b"AJUSTE SIMULADO inicial")
        self.destination = self.zero.parent.parent / "01_AJUSTES/AR09FC1.112"

    def create_zero(self, year, client, program):
        path = self.repository / str(year) / client / program / "00_ZERO_ZERO" / f"{program}.000"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"ZERO-ZERO SIMULADO")
        return path

    def snapshot(self, root):
        return {str(p.relative_to(root)): (p.read_bytes(), p.stat().st_mtime_ns)
                if p.is_file() else None for p in root.rglob("*")}

    def run_import(self):
        originals = (self.zero.read_bytes(), self.zero.stat().st_mtime_ns)
        usb_before = self.snapshot(self.usb)
        try:
            return import_adjustment(self.source.name)
        finally:
            self.assertEqual((self.zero.read_bytes(), self.zero.stat().st_mtime_ns), originals)
            self.assertEqual(self.snapshot(self.usb), usb_before)

    def test_first_import_preserves_zero_zero_and_usb(self):
        result = self.run_import()
        self.assertEqual(result["status"], "importado")
        self.assertEqual(Path(result["arquivo_destino"]), self.destination)
        self.assertEqual(self.destination.read_bytes(), self.source.read_bytes())
        self.assertEqual(set(self.zero.parent.parent.iterdir()),
                         {self.zero.parent, self.destination.parent})

    def test_update_keeps_same_name_without_versions(self):
        self.run_import()
        self.source.write_bytes(b"AJUSTE SIMULADO novo")
        result = self.run_import()
        self.assertEqual(result["status"], "atualizado")
        self.assertEqual(self.destination.read_bytes(), self.source.read_bytes())
        self.assertEqual(list(self.destination.parent.iterdir()), [self.destination])
        self.assertEqual(set(self.zero.parent.parent.iterdir()),
                         {self.zero.parent, self.destination.parent})

    def test_identical_return_does_not_replace_file(self):
        self.run_import()
        before = self.snapshot(self.repository)
        with patch("app.adjustment_importer.Path.replace") as replace:
            result = self.run_import()
        replace.assert_not_called()
        self.assertEqual(result["status"], "sem_alteracao")
        self.assertEqual(self.snapshot(self.repository), before)

    def test_unidentified_return_changes_nothing(self):
        (self.usb / "UNKNOWN.112").write_bytes(b"SIMULADO")
        before = self.snapshot(self.repository)
        result = import_adjustment("UNKNOWN.112")
        self.assertEqual(result["status"], "nao_identificado")
        self.assertEqual(self.snapshot(self.repository), before)

    def test_ambiguous_return_changes_nothing(self):
        self.create_zero(2025, "CLIENTE_X", "AR09FC1")
        before = self.snapshot(self.repository)
        result = self.run_import()
        self.assertEqual(result["status"], "ambiguo")
        self.assertEqual(len(result["correspondencias"]), 2)
        self.assertEqual(self.snapshot(self.repository), before)

    def test_missing_return_changes_nothing(self):
        before = self.snapshot(self.repository)
        result = import_adjustment("MISSING.112")
        self.assertEqual(result["status"], "arquivo_nao_encontrado")
        self.assertEqual(self.snapshot(self.repository), before)

    def test_invalid_names_change_nothing(self):
        before = self.snapshot(self.root)
        for name in ("../AR09FC1.112", "..\\AR09FC1.112", "C:AR09FC1.112",
                     "*.112", "CON.112", "AR09FC1.000", "", None):
            with self.subTest(name=name), self.assertRaises(ValueError):
                import_adjustment(name)
        self.assertEqual(self.snapshot(self.root), before)

    def test_copy_failure_preserves_previous_adjustment(self):
        self.run_import()
        self.source.write_bytes(b"AJUSTE SIMULADO novo")
        before = self.snapshot(self.repository)

        def fail_copy(incoming, output):
            output.write(b"COPIA PARCIAL")
            raise OSError("Falha simulada durante copia")

        with patch("app.adjustment_importer.shutil.copyfileobj", side_effect=fail_copy):
            with self.assertRaises(OSError):
                self.run_import()
        self.assertEqual(self.snapshot(self.repository), before)

    def test_replace_failure_preserves_previous_adjustment(self):
        self.run_import()
        self.source.write_bytes(b"AJUSTE SIMULADO novo")
        before = self.snapshot(self.repository)
        with patch("app.adjustment_importer.Path.replace", side_effect=OSError("Falha simulada")):
            with self.assertRaises(OSError):
                self.run_import()
        self.assertEqual(self.snapshot(self.repository), before)

    def test_destination_comes_from_repository_not_prefix(self):
        for client, program in (("URBAM", "UBFC1"), ("CLIENTE_X", "XYZ123"),
                                ("CLIENTE_TESTE", "AR99FC1")):
            with self.subTest(client=client):
                zero = self.create_zero(2024, client, program)
                source = self.usb / f"{program}.112"
                source.write_bytes(b"SIMULADO")
                result = import_adjustment(source.name)
                expected = zero.parent.parent / "01_AJUSTES" / source.name
                self.assertEqual(result["status"], "importado")
                self.assertEqual(result["cliente"], client)
                self.assertEqual(Path(result["arquivo_destino"]), expected)
                self.assertEqual(expected.read_bytes(), source.read_bytes())


if __name__ == "__main__":
    unittest.main()
