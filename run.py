import logging
from pathlib import Path

_LOG_FILE = Path(__file__).parent / ".taskflow" / "server.log"
_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# Configure the taskflow logger before importing src.server, which triggers
# FastMCP.__init__ → configure_logging() → basicConfig(StreamHandler), making
# any subsequent basicConfig(filename=...) a no-op.
_handler = logging.FileHandler(_LOG_FILE)
_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
_logger = logging.getLogger("taskflow")
_logger.addHandler(_handler)
_logger.setLevel(logging.INFO)

from src.server import mcp  # noqa: E402

if __name__ == "__main__":
    _logger.info("taskflow MCP server starting")
    try:
        mcp.run(transport="stdio")
    except Exception:
        _logger.exception("taskflow MCP server crashed")
        raise
