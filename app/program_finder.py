"""Localiza programas ZERO-ZERO no repositorio local."""

from typing import Optional

from app import config


def find_program(program_name: str) -> Optional[dict]:
    """Retorna os dados da primeira correspondencia, ou None se nao existir.

    Considera a estrutura ano/cliente/programa/00_ZERO_ZERO/programa.000.
    O caminho retornado e absoluto; o arquivo nao e aberto nem modificado.
    """
    repository = config.REPOSITORY_PATH

    for file_path in sorted(repository.glob("*/*/*/00_ZERO_ZERO/*.000")):
        year, client, program, _, filename = file_path.relative_to(repository).parts
        if program != program_name or filename != f"{program_name}.000":
            continue
        if not year.isdecimal() or not file_path.is_file():
            continue

        return {
            "ano": int(year),
            "cliente": client,
            "programa": program,
            "nome_arquivo": filename,
            "caminho_arquivo": str(file_path),
        }

    return None
