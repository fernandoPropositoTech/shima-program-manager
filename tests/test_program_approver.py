"""Aprovacao manual com arquivos simulados e isolados."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app import config
from app.adjustment_importer import import_adjustment
from app.program_approver import approve_program, get_approval_status


class ProgramApproverTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repository = self.root / "repository"
        self.usb = self.root / "simulated_usb"
        self.usb.mkdir()
        (self.usb / "AR09FC1.112").write_bytes(b"RETORNO SIMULADO B")
        override = patch.multiple(config, REPOSITORY_PATH=self.repository, USB_PATH=self.usb)
        override.start()
        self.addCleanup(override.stop)
        self.args = (2026, "ARAMIS", "AR09FC1")
        self.base = self.repository / "2026/ARAMIS/AR09FC1"
        self.zero = self.base / "00_ZERO_ZERO/AR09FC1.000"
        self.zero.parent.mkdir(parents=True)
        self.zero.write_bytes(b"ZERO-ZERO SIMULADO")
        self.source = self.base / "01_AJUSTES/AR09FC1.112"
        self.source.parent.mkdir()
        self.source.write_bytes(b"AJUSTE SIMULADO A")
        self.destination = self.base / "02_APROVADO/AR09FC1.112"
        self.protected = self.snapshot(self.zero.parent), self.snapshot(self.usb)

    def tearDown(self):
        self.assertEqual((self.snapshot(self.zero.parent), self.snapshot(self.usb)), self.protected)

    def snapshot(self, root):
        return {str(p.relative_to(root)): (p.read_bytes(), p.stat().st_mtime_ns)
                if p.is_file() else None for p in root.rglob("*")}

    def test_first_approval_preserves_adjustment(self):
        before = self.snapshot(self.source.parent)
        result = approve_program(*self.args)
        self.assertEqual(result["status"], "aprovado")
        self.assertEqual(result["ano"], 2026)
        self.assertEqual(result["cliente"], "ARAMIS")
        self.assertEqual(result["programa"], "AR09FC1")
        self.assertEqual(Path(result["arquivo_aprovado"]), self.destination)
        self.assertEqual(Path(result["arquivo_ajustado"]), self.source)
        self.assertEqual(self.destination.read_bytes(), self.source.read_bytes())
        self.assertEqual(self.snapshot(self.source.parent), before)

    def test_identical_approval_does_not_rewrite(self):
        approve_program(*self.args)
        before = self.snapshot(self.repository)
        with patch("app.program_approver.Path.replace") as replace:
            self.assertEqual(approve_program(*self.args)["status"], "ja_aprovado")
        replace.assert_not_called()
        self.assertEqual(self.snapshot(self.repository), before)

    def test_new_return_requires_explicit_reapproval(self):
        approve_program(*self.args)
        previous = self.snapshot(self.destination.parent)
        self.assertEqual(import_adjustment("AR09FC1.112")["status"], "atualizado")
        self.assertEqual(self.snapshot(self.destination.parent), previous)
        self.assertEqual(get_approval_status(*self.args)["status"], "novo_ajuste_aguardando_aprovacao")
        self.assertEqual(approve_program(*self.args)["status"], "reaprovado")
        self.assertEqual(self.destination.read_bytes(), self.source.read_bytes())
        self.assertEqual(get_approval_status(*self.args)["status"], "aprovado")
        self.assertEqual({p.relative_to(self.base).as_posix() for p in self.base.rglob("*")}, {
            "00_ZERO_ZERO", "00_ZERO_ZERO/AR09FC1.000", "01_AJUSTES",
            "01_AJUSTES/AR09FC1.112", "02_APROVADO", "02_APROVADO/AR09FC1.112"})

    def test_missing_adjustment_does_not_create_approval(self):
        self.source.unlink()
        before = self.snapshot(self.repository)
        self.assertEqual(get_approval_status(*self.args)["status"], "sem_ajuste")
        self.assertEqual(approve_program(*self.args)["status"], "ajuste_nao_encontrado")
        self.assertEqual(self.snapshot(self.repository), before)

    def test_query_is_read_only_and_uses_content(self):
        before = self.snapshot(self.repository)
        self.assertEqual(get_approval_status(*self.args)["status"], "aguardando_aprovacao")
        self.assertEqual(self.snapshot(self.repository), before)
        approve_program(*self.args)
        self.assertEqual(get_approval_status(*self.args)["status"], "aprovado")
        timestamp = self.source.stat().st_mtime_ns
        self.source.write_bytes(b"AJUSTE SIMULADO B")
        os.utime(self.source, ns=(timestamp, timestamp))
        before = self.snapshot(self.repository)
        self.assertEqual(get_approval_status(*self.args)["status"], "novo_ajuste_aguardando_aprovacao")
        self.assertEqual(self.snapshot(self.repository), before)

    def test_arbitrary_client(self):
        source = self.repository / "2027/CLIENTE_X/XYZ123/01_AJUSTES/XYZ123.112"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"SIMULADO")
        result = approve_program(2027, "CLIENTE_X", "XYZ123")
        self.assertEqual(result["status"], "aprovado")
        self.assertEqual(result["cliente"], "CLIENTE_X")
        self.assertEqual(Path(result["arquivo_aprovado"]).read_bytes(), b"SIMULADO")

    def test_invalid_inputs(self):
        before = self.snapshot(self.root)
        invalid = [(year, "CLIENTE", "ABC") for year in (None, True, "../2026", 0, 2026.0)]
        for name in ("", "..", "../x", "..\\x", "C:\\x", "x/y", "CON", "a*", "a."):
            invalid.extend([(2026, name, "ABC"), (2026, "CLIENTE", name)])
        for args in invalid:
            for function in (approve_program, get_approval_status):
                with self.subTest(args=args, function=function.__name__), self.assertRaises(ValueError):
                    function(*args)
        self.assertEqual(self.snapshot(self.root), before)

    def test_copy_failure_preserves_previous_approval(self):
        approve_program(*self.args)
        self.source.write_bytes(b"NOVO SIMULADO")
        before = self.snapshot(self.repository)

        def fail(incoming, output):
            output.write(b"PARCIAL")
            raise OSError("Falha simulada")

        with patch("app.program_approver.shutil.copyfileobj", side_effect=fail):
            with self.assertRaises(OSError):
                approve_program(*self.args)
        self.assertEqual(self.snapshot(self.repository), before)

    def test_replace_failure_preserves_previous_approval(self):
        approve_program(*self.args)
        self.source.write_bytes(b"NOVO SIMULADO")
        before = self.snapshot(self.repository)
        with patch("app.program_approver.Path.replace", side_effect=OSError("Falha simulada")):
            with self.assertRaises(OSError):
                approve_program(*self.args)
        self.assertEqual(self.snapshot(self.repository), before)


if __name__ == "__main__":
    unittest.main()
