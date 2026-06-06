# -*- coding: utf-8 -*-
"""
Core RAG Manager.
Centralized management for NanoGraphRAG instances.
Used by both local services and MCP tool handlers.
"""

import asyncio
import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class CoreRAGManager:
    """Singleton manager for specialized RAG instances."""
    
    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance._instances = {}
            cls._instance._init_lock = asyncio.Lock()
        return cls._instance

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or os.path.join(os.getcwd(), 'cache', 'rag')
        os.makedirs(self.base_dir, exist_ok=True)

    async def get_instance(self, sub_dir: str = "default") -> Any:
        """Get or initialize a NanoGraphRAG instance for a specific domain."""
        if sub_dir in self._instances:
            return self._instances[sub_dir]

        async with self._init_lock:
            if sub_dir in self._instances:
                return self._instances[sub_dir]

            logger.info(f"[CoreRAGManager] Initializing NanoGraphRAG for: {sub_dir}")
            try:
                # Late import to avoid dependency issues if legacy RAG is not installed
                from nano_graphrag import NanoGraphRAG
                from nano_graphrag._storage import HNSWVectorStorage
                
                working_dir = os.path.join(self.base_dir, sub_dir)
                os.makedirs(working_dir, exist_ok=True)
                
                # Default LLM/Embedding functions would be injected or resolved via core settings
                # For now, we assume standard configuration
                instance = NanoGraphRAG(
                    working_dir=working_dir,
                    vector_db_storage_cls=HNSWVectorStorage,
                    enable_llm_cache=True
                )
                self._instances[sub_dir] = instance
                return instance
            except ImportError:
                logger.error("[CoreRAGManager] NanoGraphRAG not installed. Failed to init.")
                raise RuntimeError("NanoGraphRAG dependency missing")
            except Exception as e:
                logger.error(f"[CoreRAGManager] Failed to init RAG {sub_dir}: {e}")
                raise

    async def insert(self, content: str, sub_dir: str = "default") -> str:
        instance = await self.get_instance(sub_dir)
        # NanoGraphRAG.insert is often sync but we use to_thread to keep loop free
        await asyncio.to_thread(instance.insert, content)
        import hashlib
        return hashlib.md5(content.encode()).hexdigest()

    async def query(self, query_text: str, sub_dir: str = "default") -> str:
        instance = await self.get_instance(sub_dir)
        return await asyncio.to_thread(instance.query, query_text)

def get_core_rag_manager() -> CoreRAGManager:
    return CoreRAGManager()
