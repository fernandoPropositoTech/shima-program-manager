"""Testes da localizacao do ZERO-ZERO existente."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app import config
from app.program_finder import find_program


class ProgramFinderTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        repository = Path(temporary.name) / "repository"
        self.source = repository / "2026/ARAMIS/AR09FC1/00_ZERO_ZERO/AR09FC1.000"
        self.source.parent.mkdir(parents=True)
        self.source.write_text("ZERO-ZERO SIMULADO para testes.", encoding="utf-8")
        repository_patch = patch.object(config, "REPOSITORY_PATH", repository)
        repository_patch.start()
        self.addCleanup(repository_patch.stop)

    def test_find_existing_zero_zero(self):
        result = find_program("AR09FC1")

        self.assertIsNotNone(result)
        self.assertEqual(result["ano"], 2026)
        self.assertEqual(result["cliente"], "ARAMIS")
        self.assertEqual(result["programa"], "AR09FC1")
        self.assertEqual(result["nome_arquivo"], "AR09FC1.000")

        file_path = Path(result["caminho_arquivo"])
        self.assertTrue(file_path.is_file())
        self.assertEqual(file_path, self.source)


if __name__ == "__main__":
    unittest.main()
