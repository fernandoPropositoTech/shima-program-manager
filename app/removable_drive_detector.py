"""Descoberta somente de leitura de volumes classificados como removiveis."""

import json
import re
import subprocess
import sys


class DriveDetectionError(RuntimeError):
    """Falha na consulta ou resposta invalida do Windows."""


_QUERY = """
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
try {
    $disks = @(Get-CimInstance -ClassName Win32_LogicalDisk -ErrorAction Stop |
        Select-Object DeviceID, DriveType, VolumeName, FileSystem)
    ConvertTo-Json -InputObject $disks -Compress
} catch {
    exit 1
}
"""


def _query_windows() -> str:
    if sys.platform != "win32":
        raise DriveDetectionError("Deteccao real disponivel somente no Windows.")
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", _QUERY],
            capture_output=True, text=True, encoding="utf-8", check=True,
            timeout=20, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError, UnicodeError) as error:
        raise DriveDetectionError("Falha ao consultar unidades no Windows.") from error
    return result.stdout


def _normalize(response: str) -> list:
    try:
        records = json.loads(response)
    except (ValueError, TypeError) as error:
        raise DriveDetectionError("Resposta JSON invalida na consulta de unidades.") from error
    if not isinstance(records, list):
        raise DriveDetectionError("Resposta de unidades deve ser uma lista.")
    drives = []
    seen = set()
    for record in records:
        if (not isinstance(record, dict) or type(record.get("DriveType")) is not int
                or record["DriveType"] not in range(7)):
            raise DriveDetectionError("Classificacao de unidade invalida ou ausente.")
        if record["DriveType"] != 2:
            continue
        device = record.get("DeviceID")
        if not isinstance(device, str) or not re.fullmatch(r"[A-Za-z]:", device):
            raise DriveDetectionError("Letra de unidade removivel invalida.")
        drive = device.upper() + "\\"
        if drive in seen:
            raise DriveDetectionError("Unidade duplicada na resposta do Windows.")
        seen.add(drive)
        optional = []
        for key in ("VolumeName", "FileSystem"):
            value = record.get(key)
            if value is not None and not isinstance(value, str):
                raise DriveDetectionError("Metadados de unidade invalidos.")
            optional.append(value or None)
        drives.append({"drive": drive, "label": optional[0], "filesystem": optional[1]})
    return sorted(drives, key=lambda item: item["drive"])


def detect_removable_drives() -> list:
    """Lista volumes DriveType=2, sem selecionar ou acessar seus arquivos.

    Nao garante midia pronta nem permissao de escrita. Dispositivos USB que
    o Windows classifica como discos fixos nao sao incluidos. Campos opcionais
    ausentes retornam None. Sem volumes removiveis retorna []; falhas geram
    DriveDetectionError, inclusive em plataformas diferentes do Windows.
    """
    return _normalize(_query_windows())
