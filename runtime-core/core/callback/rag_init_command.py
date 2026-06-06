from core.tools.annotations import startup_before
from core.settings import AI_MODEL, AI_REQUEST_MODEL, AI_KEY
import logging
rag = None

logger = logging.getLogger(__name__)

# @startup_before(priority=100)
def init_rag_before_startup():
    global rag
    if rag:
        return rag
    # MCP Architecture: RAG is an independent server. No local initialization needed.
    rag = None
    logger.info(f'init rag success')
    return rag
