"""Simulacao de ajuste SSR, exclusiva para arquivos de teste."""

from app import config


def simulate_ssr_adjustment(program_name: str) -> dict:
    """Gera um .112 simulado sem interpretar o formato industrial Shima.

    Preserva o .000 e gera FileExistsError se o .112 ja existir.
    """
    if not program_name or any(char in program_name for char in '/\\:'):
        raise ValueError("Informe somente o nome do programa, sem caminho.")

    source = config.USB_PATH / f"{program_name}.000"
    adjusted = config.USB_PATH / f"{program_name}.112"
    if not source.is_file():
        return {
            "programa": program_name,
            "arquivo_origem": str(source),
            "arquivo_ajustado": None,
            "status": "origem_nao_encontrada",
        }

    content = source.read_bytes()
    with adjusted.open("xb") as output:
        output.write(content)
        output.write(b"\nAJUSTE SSR SIMULADO - apenas para testes.\n")

    return {
        "programa": program_name,
        "arquivo_origem": str(source),
        "arquivo_ajustado": str(adjusted),
        "status": "sucesso",
    }
