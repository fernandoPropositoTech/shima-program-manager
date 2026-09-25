"""Cadastro seguro de novos programas ZERO-ZERO."""

import os
from pathlib import Path
import shutil
from tempfile import NamedTemporaryFile

from app import config


def _validate_name(name):
    reserved = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    reserved.update(f"{prefix}{n}" for prefix in ("COM", "LPT") for n in "123456789¹²³")
    if (not isinstance(name, str) or not name or name != name.strip()
            or name.endswith(".") or any(c in name for c in '<>:"/\\|?*')
            or any(ord(c) < 32 for c in name)
            or name.split(".")[0].upper() in reserved):
        raise ValueError("Nome de cliente ou programa invalido.")


def register_program(year, client, program_name, source_file) -> dict:
    """Copia um .000 para um ano de quatro digitos (1000 a 9999).

    Aceita ano inteiro ou texto ASCII de quatro digitos. Entradas invalidas
    geram ValueError; falhas de E/S sao propagadas. Nao sobrescreve destinos.
    """
    if (type(year) not in (int, str) or len(str(year)) != 4
            or not str(year).isascii() or not str(year).isdecimal()
            or not 1000 <= int(year) <= 9999):
        raise ValueError("Ano deve ter quatro digitos, entre 1000 e 9999.")
    _validate_name(client)
    _validate_name(program_name)
    if not isinstance(source_file, (str, os.PathLike)) or not str(source_file):
        raise ValueError("Arquivo de origem invalido.")
    source = Path(source_file).absolute()
    if source.name != f"{program_name}.000" or not source.is_file():
        raise ValueError("Origem deve ser um arquivo existente com nome exato PROGRAMA.000.")

    root = config.REPOSITORY_PATH.resolve()
    program = root / str(year) / client / program_name
    folders = [program / name for name in ("00_ZERO_ZERO", "01_AJUSTES", "02_APROVADO")]
    destination = folders[0] / source.name
    for path in [program.parent.parent, program.parent, program, *folders, destination]:
        if path.is_symlink() or path.resolve() != path:
            raise ValueError("O destino nao pode redirecionar caminhos por links ou juncoes.")
    result = {
        "ano": int(year), "cliente": client, "programa": program_name,
        "arquivo_origem": str(source), "arquivo_zero_zero": str(destination),
        "pasta_programa": str(program), "status": "ja_existe",
    }
    if destination.exists():
        if not destination.is_file():
            raise ValueError("Destino existente nao e um arquivo regular.")
        return result

    created = []
    temporary = None
    published = False
    try:
        for folder in [root, program.parent.parent, program.parent, program, *folders]:
            try:
                folder.mkdir()
                created.append(folder)
            except FileExistsError:
                if not folder.is_dir():
                    raise
        with NamedTemporaryFile(dir=folders[0], prefix=".cadastro-", suffix=".tmp",
                                mode="wb", delete=False) as output:
            temporary = Path(output.name)
            with source.open("rb") as incoming:
                shutil.copyfileobj(incoming, output)
            output.flush()
            os.fsync(output.fileno())
        try:
            # Publica os bytes completos sem substituir um destino concorrente.
            # Link apenas para o temporario local, nunca para o arquivo de origem.
            os.link(temporary, destination)
        except FileExistsError:
            return result
        published = True
        result["status"] = "cadastrado"
        return result
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        if not published:
            for folder in reversed(created):
                try:
                    folder.rmdir()  # Remove somente pastas criadas aqui e vazias.
                except OSError:
                    pass
