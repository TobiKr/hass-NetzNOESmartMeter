"""Netz NO Smartmeter API wrapper."""
from importlib.metadata import version

from .client import Smartmeter

try:
    __version__ = version(__name__)
except Exception:  # pylint: disable=broad-except
    pass

__all__ = ["Smartmeter"]
