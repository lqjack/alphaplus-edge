"""
State Persistence Layer

Provides robust state management and checkpointing capabilities:
- Checkpoint System: Saves and restores automation session state
- Learned Strategy Storage: Persists successful element location strategies
- Session Data Management: Stores and retrieves session-specific data
- Metadata Tracking: Records execution metadata for analysis and optimization
"""

import json
import os
import time
import logging
from typing import Dict, List, Optional, Any
from .interfaces import IStatePersistenceLayer, ExecutionContext
from .dependency_types import STATE_PERSISTENCE_LAYER


class StatePersistenceLayer(IStatePersistenceLayer):
    """State persistence and checkpointing component"""

    def __init__(self, dependency_manager):
        self.dep_manager = dependency_manager
        self.logger = logging.getLogger("mcp-server-wechat-viewer-mcp.state_persistence")

        # Storage directories
        self._storage_dir = ".mcp_state"
        self._checkpoints_dir = os.path.join(self._storage_dir, "checkpoints")
        self._strategies_dir = os.path.join(self._storage_dir, "strategies")
        self._sessions_dir = os.path.join(self._storage_dir, "sessions")

        # Ensure storage directories exist
        self._ensure_directories()

        # In-memory caches for performance
        self._strategy_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._session_cache: Dict[str, Dict[str, Any]] = {}

    def _ensure_directories(self):
        """Ensure all required storage directories exist"""
        for directory in [self._storage_dir, self._checkpoints_dir, self._strategies_dir, self._sessions_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)
                self.logger.debug(f"Created directory: {directory}")

    def save_checkpoint(self,
                       session_id: str,
                       context: ExecutionContext,
                       metadata: Dict[str, Any] = None) -> str:
        """Save an execution checkpoint"""
        try:
            # Generate checkpoint ID
            timestamp = int(time.time())
            checkpoint_id = f"checkpoint_{session_id}_{timestamp}"

            # Prepare checkpoint data
            checkpoint_data = {
                "checkpoint_id": checkpoint_id,
                "session_id": session_id,
                "timestamp": timestamp,
                "context": {
                    "session_id": context.session_id,
                    "start_time": context.start_time,
                    "last_checkpoint": context.last_checkpoint,
                    "retry_count": context.retry_count,
                    "learned_strategies": context.learned_strategies,
                    "performance_metrics": context.performance_metrics
                },
                "metadata": metadata or {}
            }

            # Save to file
            checkpoint_file = os.path.join(self._checkpoints_dir, f"{checkpoint_id}.json")
            with open(checkpoint_file, 'w') as f:
                json.dump(checkpoint_data, f, indent=2)

            self.logger.info(f"Saved checkpoint {checkpoint_id} for session {session_id}")
            return checkpoint_id

        except Exception as e:
            self.logger.error(f"Failed to save checkpoint for session {session_id}: {e}")
            raise

    def load_checkpoint(self, checkpoint_id: str) -> Optional[ExecutionContext]:
        """Load an execution checkpoint"""
        try:
            checkpoint_file = os.path.join(self._checkpoints_dir, f"{checkpoint_id}.json")

            if not os.path.exists(checkpoint_file):
                self.logger.warning(f"Checkpoint file not found: {checkpoint_id}")
                return None

            with open(checkpoint_file, 'r') as f:
                checkpoint_data = json.load(f)

            # Reconstruct ExecutionContext
            context_data = checkpoint_data["context"]
            context = ExecutionContext(
                session_id=context_data["session_id"],
                start_time=context_data["start_time"],
                last_checkpoint=context_data["last_checkpoint"],
                retry_count=context_data["retry_count"],
                learned_strategies=context_data["learned_strategies"],
                performance_metrics=context_data["performance_metrics"]
            )

            self.logger.info(f"Loaded checkpoint {checkpoint_id}")
            return context

        except Exception as e:
            self.logger.error(f"Failed to load checkpoint {checkpoint_id}: {e}")
            return None

    def save_learned_strategy(self,
                             task_type: str,
                             strategy: str,
                             success_rate: float) -> bool:
        """Save a learned element location strategy"""
        try:
            # Update in-memory cache
            if task_type not in self._strategy_cache:
                self._strategy_cache[task_type] = []

            # Check if strategy already exists for this task type
            existing_strategy = None
            for i, strategy_entry in enumerate(self._strategy_cache[task_type]):
                if strategy_entry["strategy"] == strategy:
                    existing_strategy = i
                    break

            strategy_entry = {
                "strategy": strategy,
                "success_rate": success_rate,
                "timestamp": time.time(),
                "usage_count": 1
            }

            if existing_strategy is not None:
                # Update existing strategy
                old_entry = self._strategy_cache[task_type][existing_strategy]
                strategy_entry["usage_count"] = old_entry["usage_count"] + 1
                # Weighted average of success rate
                total_weight = old_entry["usage_count"] + 1
                strategy_entry["success_rate"] = (
                    (old_entry["success_rate"] * old_entry["usage_count"] + success_rate) / total_weight
                )
                self._strategy_cache[task_type][existing_strategy] = strategy_entry
            else:
                # Add new strategy
                self._strategy_cache[task_type].append(strategy_entry)

            # Sort by success rate (descending) and usage count (descending)
            self._strategy_cache[task_type].sort(
                key=lambda x: (x["success_rate"], x["usage_count"]),
                reverse=True
            )

            # Keep only top 10 strategies per task type
            if len(self._strategy_cache[task_type]) > 10:
                self._strategy_cache[task_type] = self._strategy_cache[task_type][:10]

            # Persist to disk
            self._persist_strategies(task_type)

            self.logger.debug(f"Saved learned strategy '{strategy}' for task type '{task_type}' with success rate {success_rate:.2f}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to save learned strategy for task type '{task_type}': {e}")
            return False

    def get_learned_strategies(self, task_type: str) -> List[Dict[str, Any]]:
        """Get learned strategies for a specific task type"""
        try:
            # Return cached strategies if available
            if task_type in self._strategy_cache:
                return self._strategy_cache[task_type].copy()

            # Otherwise, load from disk
            strategies = self._load_strategies(task_type)
            self._strategy_cache[task_type] = strategies
            return strategies.copy()

        except Exception as e:
            self.logger.error(f"Failed to get learned strategies for task type '{task_type}': {e}")
            return []

    def save_session_data(self, session_id: str, data: Dict[str, Any]) -> bool:
        """Save session-specific data"""
        try:
            # Update in-memory cache
            self._session_cache[session_id] = data.copy()

            # Persist to disk
            session_file = os.path.join(self._sessions_dir, f"{session_id}.json")
            with open(session_file, 'w') as f:
                json.dump(data, f, indent=2)

            self.logger.debug(f"Saved session data for session {session_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to save session data for session {session_id}: {e}")
            return False

    def load_session_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load session-specific data"""
        try:
            # Return cached data if available
            if session_id in self._session_cache:
                return self._session_cache[session_id].copy()

            # Otherwise, load from disk
            session_file = os.path.join(self._sessions_dir, f"{session_id}.json")

            if not os.path.exists(session_file):
                self.logger.debug(f"No session data found for session {session_id}")
                return None

            with open(session_file, 'r') as f:
                data = json.load(f)

            # Cache the data
            self._session_cache[session_id] = data.copy()

            self.logger.debug(f"Loaded session data for session {session_id}")
            return data

        except Exception as e:
            self.logger.error(f"Failed to load session data for session {session_id}: {e}")
            return None

    # Private helper methods

    def _persist_strategies(self, task_type: str):
        """Persist strategies for a task type to disk"""
        try:
            strategies_file = os.path.join(self._strategies_dir, f"{task_type}_strategies.json")
            with open(strategies_file, 'w') as f:
                json.dump(self._strategy_cache[task_type], f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to persist strategies for task type '{task_type}': {e}")

    def _load_strategies(self, task_type: str) -> List[Dict[str, Any]]:
        """Load strategies for a task type from disk"""
        try:
            strategies_file = os.path.join(self._strategies_dir, f"{task_type}_strategies.json")

            if not os.path.exists(strategies_file):
                return []

            with open(strategies_file, 'r') as f:
                strategies = json.load(f)

            return strategies if isinstance(strategies, list) else []

        except Exception as e:
            self.logger.error(f"Failed to load strategies for task type '{task_type}': {e}")
            return []