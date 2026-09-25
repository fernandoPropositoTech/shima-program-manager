"""Testes de lote com arquivos exclusivamente simulados."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app import adjustment_importer, config
from app.batch_processor import process_usb_returns


class BatchProcessorTests(unittest.TestCase):
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

    def snapshot(self, root):
        return {str(p.relative_to(root)): (p.read_bytes(), p.stat().st_mtime_ns)
                if p.is_file() else None for p in root.rglob("*")}

    def create_program(self, year, client, name, stored=None):
        base = self.repository / str(year) / client / name
        zero = base / "00_ZERO_ZERO" / f"{name}.000"
        zero.parent.mkdir(parents=True)
        zero.write_bytes(b"ZERO-ZERO SIMULADO")
        destination = base / "01_AJUSTES" / f"{name}.112"
        if stored is not None:
            destination.parent.mkdir()
            destination.write_bytes(stored)
        return zero, destination

    def assert_counts(self, result, **expected):
        keys = ("importados", "atualizados", "sem_alteracao", "nao_identificados", "ambiguos", "erros")
        for key in keys:
            self.assertEqual(result[key], expected.get(key, 0), key)
        self.assertEqual(result["total_encontrados"], sum(result[k] for k in keys))
        self.assertEqual(len(result["resultados"]), result["total_encontrados"])

    def test_empty_usb(self):
        result = process_usb_returns()
        self.assert_counts(result)
        self.assertEqual(result["total_encontrados"], 0)
        self.assertEqual(result["resultados"], [])

    def test_other_files_and_subdirectories_are_ignored(self):
        for name in ("AR09FC1.000", "README.txt", "imagem.jpg", "A.112.txt"):
            (self.usb / name).write_bytes(b"IGNORADO")
        folder = self.usb / "SUBPASTA.112"
        folder.mkdir()
        (folder / "INTERNO.112").write_bytes(b"IGNORADO")
        before = self.snapshot(self.root)
        result = process_usb_returns()
        self.assert_counts(result)
        self.assertEqual(self.snapshot(self.root), before)

    def test_mixed_batch_counts_and_preserves_originals(self):
        fixtures = [
            (2026, "ARAMIS", "AR09FC1", None),
            (2026, "URBAM", "UBFC1", b"ANTIGO"),
            (2027, "CLIENTE_X", "XYZ123", b"NOVO"),
            (2024, "CLIENTE_TESTE", "AR99FC1", None),
        ]
        destinations = []
        for year, client, name, stored in fixtures:
            zero, destination = self.create_program(year, client, name, stored)
            destinations.append((client, name, destination))
        for year, client in ((2025, "CLIENTE_A"), (2026, "CLIENTE_B")):
            self.create_program(year, client, "ABC1")
        names = ["XYZ123", "UBFC1", "DESCONHECIDO", "AR99FC1", "AR09FC1", "ABC1"]
        for name in names:
            (self.usb / f"{name}.112").write_bytes(b"NOVO")
        usb_before = self.snapshot(self.usb)
        zero_before = {p: (p.read_bytes(), p.stat().st_mtime_ns)
                       for p in self.repository.rglob("*.000")}
        directories_before = {p for p in self.repository.rglob("*") if p.is_dir()}

        result = process_usb_returns()

        self.assert_counts(result, importados=2, atualizados=1, sem_alteracao=1,
                           nao_identificados=1, ambiguos=1)
        self.assertEqual(result["total_encontrados"], 6)
        self.assertEqual([r["nome_arquivo"] for r in result["resultados"]],
                         sorted(f"{name}.112" for name in names))
        by_program = {r["programa"]: r for r in result["resultados"]}
        for client, name, destination in destinations:
            self.assertEqual(by_program[name]["cliente"], client)
            self.assertEqual(Path(by_program[name]["arquivo_destino"]), destination)
            self.assertEqual(destination.read_bytes(), b"NOVO")
            self.assertEqual(list(destination.parent.iterdir()), [destination])
        self.assertEqual(by_program["XYZ123"]["ano"], 2027)
        self.assertIsNone(by_program["ABC1"]["arquivo_destino"])
        self.assertEqual(list(self.repository.rglob("ABC1.112")), [])
        self.assertEqual(self.snapshot(self.usb), usb_before)
        for path, previous in zero_before.items():
            self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), previous)
        directories_after = {p for p in self.repository.rglob("*") if p.is_dir()}
        self.assertEqual(directories_after, directories_before | {d.parent for _, _, d in destinations})

    def test_exception_is_isolated_and_processing_order_is_deterministic(self):
        for name in ("zUltimo", "AFALHA", "bSegundo"):
            self.create_program(2030, "CLIENTE_ARBITRARIO", name)
            (self.usb / f"{name}.112").write_bytes(b"SIMULADO")
        real_import = adjustment_importer.import_adjustment

        def import_with_failure(filename):
            if filename == "AFALHA.112":
                raise OSError("Detalhe privado que nao deve aparecer")
            return real_import(filename)

        before = self.snapshot(self.usb)
        with patch("app.batch_processor.adjustment_importer.import_adjustment",
                   side_effect=import_with_failure) as importer:
            result = process_usb_returns()
        self.assert_counts(result, importados=2, erros=1)
        self.assertEqual([call.args[0] for call in importer.call_args_list],
                         ["AFALHA.112", "bSegundo.112", "zUltimo.112"])
        failed = result["resultados"][0]
        self.assertEqual(failed["status"], "erro")
        self.assertIn("OSError", failed["erro"])
        self.assertNotIn("Detalhe privado", failed["erro"])
        self.assertEqual(self.snapshot(self.usb), before)

    def test_file_disappearing_after_discovery_counts_as_error(self):
        (self.usb / "A.112").write_bytes(b"SIMULADO")
        real_import = adjustment_importer.import_adjustment

        def remove_before_import(filename):
            (self.usb / filename).unlink()
            return real_import(filename)

        with patch("app.batch_processor.adjustment_importer.import_adjustment",
                   side_effect=remove_before_import):
            result = process_usb_returns()
        self.assert_counts(result, erros=1)
        self.assertEqual(result["resultados"][0]["status"], "arquivo_nao_encontrado")


if __name__ == "__main__":
    unittest.main()
