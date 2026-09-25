"""Envia uma copia do ZERO-ZERO para o pen drive simulado."""

from pathlib import Path
import shutil

from app import config
from app.program_finder import find_program


def send_program(program_name: str) -> dict:
    """Copia o programa encontrado sem alterar a origem.

    Retorna status 'nao_encontrado' se o programa nao existir.
    Um destino ja existente gera FileExistsError, preservando seu conteudo.
    """
    program = find_program(program_name)
    if program is None:
        return {
            "programa": program_name,
            "arquivo_origem": None,
            "arquivo_destino": None,
            "status": "nao_encontrado",
        }

    source = Path(program["caminho_arquivo"])
    usb = config.USB_PATH
    usb.mkdir(exist_ok=True)
    destination = usb / program["nome_arquivo"]

    with source.open("rb") as original, destination.open("xb") as copy:
        shutil.copyfileobj(original, copy)

    return {
        "programa": program["programa"],
        "arquivo_origem": str(source),
        "arquivo_destino": str(destination),
        "status": "sucesso",
    }
