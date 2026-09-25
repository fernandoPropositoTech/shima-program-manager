"""Cadastro com arquivos simulados em diretorios temporarios."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app import config
from app.program_registrar import register_program


class ProgramRegistrarTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repository = self.root / "repository"
        self.repository.mkdir()
        override = patch.object(config, "REPOSITORY_PATH", self.repository)
        override.start()
        self.addCleanup(override.stop)

    def source(self, name):
        path = self.root / name
        path.write_bytes(b"ZERO-ZERO SIMULADO\x00\xff")
        return path

    def test_registration_for_arbitrary_clients_and_names(self):
        for year, client, name in ((2026, "ARAMIS", "AR09FC1"), (2026, "URBAM", "UBFC1"),
                                   (2027, "CLIENTE_X", "XYZ123"), ("2028", "MALHARIA_TESTE", "AR09M1")):
            with self.subTest(client=client):
                source = self.source(f"{name}.000")
                before = (source.read_bytes(), source.stat().st_mtime_ns)
                result = register_program(year, client, name, source)
                base = self.repository / str(year) / client / name
                destination = base / "00_ZERO_ZERO" / source.name
                self.assertEqual(result, {
                    "ano": int(year), "cliente": client, "programa": name,
                    "arquivo_origem": str(source), "arquivo_zero_zero": str(destination),
                    "pasta_programa": str(base), "status": "cadastrado",
                })
                self.assertEqual({p.name for p in base.iterdir()},
                                 {"00_ZERO_ZERO", "01_AJUSTES", "02_APROVADO"})
                self.assertEqual(list((base / "01_AJUSTES").iterdir()), [])
                self.assertEqual(list((base / "02_APROVADO").iterdir()), [])
                self.assertEqual(list(destination.parent.iterdir()), [destination])
                self.assertEqual(destination.read_bytes(), before[0])
                self.assertEqual((source.read_bytes(), source.stat().st_mtime_ns), before)
                source.write_bytes(b"ORIGEM ALTERADA APOS CADASTRO")
                self.assertEqual(destination.read_bytes(), before[0])

    def test_existing_zero_zero_is_preserved(self):
        source = self.source("ABC.000")
        first = register_program(2026, "CLIENTE", "ABC", source)
        destination = Path(first["arquivo_zero_zero"])
        before = (destination.read_bytes(), destination.stat().st_mtime_ns)
        source.write_bytes(b"OUTRO CONTEUDO")
        result = register_program(2026, "CLIENTE", "ABC", source)
        self.assertEqual(result["status"], "ja_existe")
        self.assertEqual((destination.read_bytes(), destination.stat().st_mtime_ns), before)

    def test_invalid_sources(self):
        directory = self.root / "DIR.000"
        directory.mkdir()
        for name, source in (("ABC", self.root / "ABC.000"), ("ABC", self.source("ABC.112")),
                             ("ABC", self.source("OUTRO.000")), ("DIR", directory), ("ABC", None)):
            with self.subTest(source=source), self.assertRaises(ValueError):
                register_program(2026, "CLIENTE", name, source)
        self.assertEqual(list(self.repository.iterdir()), [])

    def test_invalid_years(self):
        source = self.source("ABC.000")
        for year in (None, True, 2026.0, "", "../2026", "2026/", "C:\\", 0, 999, 10000, "２０２６"):
            with self.subTest(year=year), self.assertRaises(ValueError):
                register_program(year, "CLIENTE", "ABC", source)
        self.assertEqual(list(self.repository.iterdir()), [])

    def test_dangerous_and_empty_names(self):
        source = self.source("ABC.000")
        for name in (None, "", ".", "..", "../", "..\\", "C:\\", "sub/pasta", "sub\\pasta",
                     "CON", "LPT1", "a*", "a?", "a:", "a\x00", "a.", " a", "a "):
            for client, program in ((name, "ABC"), ("CLIENTE", name)):
                with self.subTest(client=client, program=program), self.assertRaises(ValueError):
                    register_program(2026, client, program, source)
        self.assertEqual(list(self.repository.iterdir()), [])

    def test_copy_failure_cleans_partial_registration(self):
        source = self.source("ABC.000")
        before = source.read_bytes()

        def fail(incoming, output):
            output.write(b"PARCIAL")
            raise OSError("Falha simulada")

        with patch("app.program_registrar.shutil.copyfileobj", side_effect=fail):
            with self.assertRaises(OSError):
                register_program(2026, "CLIENTE", "ABC", source)
        self.assertEqual(list(self.repository.iterdir()), [])
        self.assertEqual(source.read_bytes(), before)

    def test_publication_failure_cleans_temporary(self):
        source = self.source("ABC.000")
        with patch("app.program_registrar.os.link", side_effect=OSError("Falha simulada")):
            with self.assertRaises(OSError):
                register_program(2026, "CLIENTE", "ABC", source)
        self.assertEqual(list(self.repository.iterdir()), [])

    def test_concurrent_destination_is_not_overwritten(self):
        source = self.source("ABC.000")

        def concurrent(temporary, destination):
            destination.write_bytes(b"ZERO-ZERO CONCORRENTE")
            raise FileExistsError("Destino criado durante copia")

        with patch("app.program_registrar.os.link", side_effect=concurrent):
            result = register_program(2026, "CLIENTE", "ABC", source)
        self.assertEqual(result["status"], "ja_existe")
        destination = Path(result["arquivo_zero_zero"])
        self.assertEqual(destination.read_bytes(), b"ZERO-ZERO CONCORRENTE")
        self.assertEqual(list(destination.parent.iterdir()), [destination])


if __name__ == "__main__":
    unittest.main()
