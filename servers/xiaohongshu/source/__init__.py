from .application import XHS
from .module import Settings

# Keep optional CLI/TUI extras from blocking the lightweight API import path.
try:
    from .CLI import cli
except ImportError:
    cli = None

try:
    from .TUI import XHSDownloader
except ImportError:
    XHSDownloader = None

__all__ = [
    "XHS",
    "XHSDownloader",
    "cli",
    "Settings",
]
