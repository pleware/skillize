"""Enable agent skills and say when they fire."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("skillize")
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = ["__version__"]
