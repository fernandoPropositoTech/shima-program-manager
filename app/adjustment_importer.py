"""Importa o estado atual do ajuste, sem criar historico de versoes."""

import os
from pathlib import Path
import shutil
from tempfile import NamedTemporaryFile

from app import return_identifier


def _same_content(first: Path, second: Path) -> bool:
    """Compara bytes em blocos, sem cache ou dependencias externas."""
    with first.open("rb") as left, second.open("rb") as right:
        while True:
            block = left.read(1024 * 1024)
            if block != right.read(1024 * 1024):
                return False
            if not block:
                return True


def import_adjustment(filename: str) -> dict:
    """Copia um retorno identificado e preserva o USB e o ZERO-ZERO.

    Erros de E/S sao propagados; falhas antes da substituicao preservam
    o ajuste anterior. O temporario e removido mesmo em caso de falha.
    """
    result = return_identifier.identify_return(filename)
    result["arquivo_destino"] = None
    if result["status"] != "identificado":
        return result

    source = Path(result["arquivo_ajustado"])
    program_directory = Path(result["arquivo_zero_zero"]).parent.parent.resolve()
    adjustments = program_directory / "01_AJUSTES"
    # Nao escrever por links/juncoes que redirecionem a pasta de ajustes.
    if adjustments.resolve() != adjustments:
        raise ValueError("A pasta de ajustes nao pode redirecionar o destino.")
    destination = adjustments / filename
    if destination.is_symlink():
        raise ValueError("O arquivo de destino nao pode ser um link simbolico.")
    existed = destination.exists()
    if existed and not destination.is_file():
        raise ValueError("O destino deve ser um arquivo regular.")
    result["arquivo_destino"] = str(destination)
    if existed and _same_content(source, destination):
        result["status"] = "sem_alteracao"
        return result

    adjustments.mkdir(exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(mode="wb", dir=adjustments,
                                prefix=".import-", suffix=".tmp", delete=False) as output:
            temporary = Path(output.name)
            with source.open("rb") as incoming:
                shutil.copyfileobj(incoming, output)
            output.flush()
            os.fsync(output.fileno())
        # Ambos os arquivos estao na mesma pasta/volume; fechado no Windows.
        temporary.replace(destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

    result["status"] = "atualizado" if existed else "importado"
    return result
