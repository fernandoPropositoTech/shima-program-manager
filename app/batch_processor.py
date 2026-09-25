"""Coordena a importacao dos retornos presentes no USB simulado."""

from app import adjustment_importer, config


def process_usb_returns() -> dict:
    """Processa arquivos .112 diretamente no USB, em ordem de nome.

    A extensao numerica .112 nao possui variacao de caixa. O nome original
    e preservado, sem alterar as regras do importador. Nao percorre subpastas.
    Arquivo removido durante o lote conta como erro, mantendo seu status.
    Falhas ao listar o USB sao propagadas; excecoes individuais sao isoladas.
    """
    summary = {
        "total_encontrados": 0,
        "importados": 0,
        "atualizados": 0,
        "sem_alteracao": 0,
        "nao_identificados": 0,
        "ambiguos": 0,
        "erros": 0,
        "resultados": [],
    }
    counters = {
        "importado": "importados",
        "atualizado": "atualizados",
        "sem_alteracao": "sem_alteracao",
        "nao_identificado": "nao_identificados",
        "ambiguo": "ambiguos",
    }
    files = sorted(
        (path for path in config.USB_PATH.iterdir()
         if path.suffix == ".112" and path.is_file()),
        key=lambda path: (path.name.casefold(), path.name),
    )
    summary["total_encontrados"] = len(files)
    for path in files:
        result = {
            "nome_arquivo": path.name,
            "programa": path.stem,
            "cliente": None,
            "ano": None,
            "arquivo_destino": None,
            "erro": None,
        }
        try:
            result.update(adjustment_importer.import_adjustment(path.name))
        except Exception as error:
            # Nao expor traceback, caminhos ou conteudo arbitrario da excecao.
            result["status"] = "erro"
            result["erro"] = f"Falha ao processar arquivo ({type(error).__name__})."

        counter = counters.get(result["status"], "erros")
        if counter == "erros" and result["erro"] is None:
            result["erro"] = "Importacao nao concluida; consulte o status do arquivo."
        summary[counter] += 1
        summary["resultados"].append(result)
    return summary
