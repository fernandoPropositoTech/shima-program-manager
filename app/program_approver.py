"""Aprovacao explicita do ajuste armazenado no repositorio."""

import os
from pathlib import Path
import shutil
from tempfile import NamedTemporaryFile

from app import config
from app.adjustment_importer import _same_content
from app.program_registrar import _validate_name


def _paths(year, client, program_name):
    if (type(year) not in (int, str) or len(str(year)) != 4
            or not str(year).isascii() or not str(year).isdecimal()
            or not 1000 <= int(year) <= 9999):
        raise ValueError("Ano deve ter quatro digitos, entre 1000 e 9999.")
    _validate_name(client)
    _validate_name(program_name)
    root = config.REPOSITORY_PATH.resolve()
    base = root / str(year) / client / program_name
    source = base / "01_AJUSTES" / f"{program_name}.112"
    destination = base / "02_APROVADO" / f"{program_name}.112"
    for path in (base.parent.parent, base.parent, base, source.parent,
                 destination.parent, source, destination):
        if path.is_symlink() or path.resolve() != path:
            raise ValueError("Links e juncoes nao sao permitidos no caminho do programa.")
    for path in (source, destination):
        if path.exists() and not path.is_file():
            raise ValueError("Ajuste e aprovado devem ser arquivos regulares.")
    return source, destination


def _result(year, client, program_name, source, destination, status):
    return {"ano": int(year), "cliente": client, "programa": program_name,
            "arquivo_ajustado": str(source), "arquivo_aprovado": str(destination),
            "status": status}


def get_approval_status(year, client, program_name) -> dict:
    """Consulta somente por conteudo, sem escrever arquivos.

    Ajuste ausente (inclusive programa inexistente) retorna sem_ajuste.
    """
    source, destination = _paths(year, client, program_name)
    if not source.is_file():
        status = "sem_ajuste"
    elif not destination.is_file():
        status = "aguardando_aprovacao"
    elif _same_content(source, destination):
        status = "aprovado"
    else:
        status = "novo_ajuste_aguardando_aprovacao"
    return _result(year, client, program_name, source, destination, status)


def approve_program(year, client, program_name) -> dict:
    """Aprova por chamada explicita; nao acessa USB nem modifica ZERO-ZERO.

    Falhas de E/S sao propagadas. O aprovado so e substituido apos a copia
    completa e sincronizada; temporarios sao removidos tambem em falhas.
    """
    source, destination = _paths(year, client, program_name)
    if not source.is_file():
        return _result(year, client, program_name, source, destination, "ajuste_nao_encontrado")
    existed = destination.is_file()
    if existed and _same_content(source, destination):
        return _result(year, client, program_name, source, destination, "ja_aprovado")

    destination.parent.mkdir(exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(mode="wb", dir=destination.parent,
                                prefix=".aprovacao-", suffix=".tmp", delete=False) as output:
            temporary = Path(output.name)
            with source.open("rb") as incoming:
                shutil.copyfileobj(incoming, output)
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return _result(year, client, program_name, source, destination,
                   "reaprovado" if existed else "aprovado")
