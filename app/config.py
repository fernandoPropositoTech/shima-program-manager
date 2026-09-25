"""Caminhos locais relativos a localizacao do projeto."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPOSITORY_PATH = PROJECT_ROOT / "repository"
USB_PATH = PROJECT_ROOT / "simulated_usb"
