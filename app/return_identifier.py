"""Identificacao somente de leitura de retornos .112 no USB simulado."""

from pathlib import Path

from app import config


def _validate_filename(filename: str) -> str:
    """Aceita somente um nome de arquivo .112 valido no Windows."""
    if (
        not isinstance(filename, str)
        or not filename.endswith(".112")
        or any(char in filename for char in '<>:"/\\|?*')
        or any(ord(char) < 32 for char in filename)
    ):
        raise ValueError("Informe apenas o nome de um arquivo .112, sem caminho.")
    program = filename[:-4]
    reserved = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    reserved.update(f"{prefix}{number}" for prefix in ("COM", "LPT")
                    for number in "123456789¹²³")
    if (not program or program != program.strip() or program.endswith(".")
            or program.split(".")[0].upper() in reserved):
        raise ValueError("Nome de programa invalido.")
    return program


def _require_contained(path: Path, root: Path) -> None:
    """Impede que links redirecionem a identificacao para fora da area."""
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        raise ValueError("Caminho fora da area configurada.") from None


def _find_matches(program: str) -> list:
    repository = config.REPOSITORY_PATH
    matches = []
    for path in sorted(repository.glob("*/*/*/00_ZERO_ZERO/*.000")):
        year, client, name, _, filename = path.relative_to(repository).parts
        if name != program or filename != f"{program}.000":
            continue
        if not year.isdecimal() or not path.is_file():
            continue
        _require_contained(path, repository)
        matches.append({
            "ano": int(year),
            "cliente": client,
            "programa": name,
            "arquivo_zero_zero": str(path),
        })
    return matches


def identify_return(filename: str) -> dict:
    """Identifica, por exemplo, 'AR09FC1.112', sem modificar arquivos.

    Retorna todas as correspondencias; so preenche ano, cliente e
    arquivo_zero_zero no nivel principal quando ha uma unica correspondencia.
    Entradas invalidas ou caminhos fora das areas geram ValueError.
    """
    program = _validate_filename(filename)
    adjusted = config.USB_PATH / filename
    _require_contained(adjusted, config.USB_PATH)
    result = {
        "ano": None,
        "cliente": None,
        "programa": program,
        "arquivo_ajustado": str(adjusted),
        "arquivo_zero_zero": None,
        "status": "arquivo_nao_encontrado",
        "correspondencias": [],
    }
    if not adjusted.is_file():
        return result

    matches = _find_matches(program)
    result["correspondencias"] = matches
    if len(matches) == 1:
        result.update(matches[0])
        result["status"] = "identificado"
    elif matches:
        result["status"] = "ambiguo"
    else:
        result["status"] = "nao_identificado"
    return result
