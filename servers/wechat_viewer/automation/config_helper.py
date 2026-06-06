"""
Configuration Helper

Helper class for loading and managing configuration.
"""
import logging
import os
from typing import Dict, Any, Optional


class ConfigHelper:
    """Helper class for configuration management"""

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize config helper

        Args:
            logger: Logger instance
        """
        self.logger = logger or logging.getLogger(__name__)

    def load_bool_from_env(
        self,
        env_key: str,
        default: bool = True,
        env_var_prefix: str = ""
    ) -> bool:
        """
        Load boolean value from environment variable

        Args:
            env_key: Environment variable key
            default: Default value if not found
            env_var_prefix: Prefix to add to env_key

        Returns:
            Boolean value
        """
        full_key = f"{env_var_prefix}{env_key}" if env_var_prefix else env_key
        env_value = os.getenv(full_key, '').lower()

        if env_value:
            # Support multiple formats: true, false, yes, no, 1, 0
            if env_value in ('true', 'yes', '1'):
                self.logger.info(f"{full_key} enabled from environment: True (value: {env_value})")
                return True
            elif env_value in ('false', 'no', '0'):
                self.logger.info(f"{full_key} disabled from environment: False (value: {env_value})")
                return False
            else:
                self.logger.warning(f"Invalid {full_key} value: {env_value}, using default: {default}")

        return default

    def load_ocr_enabled(self, config_enabled: bool) -> bool:
        """
        Load OCR enabled status from environment

        Args:
            config_enabled: Default value from config

        Returns:
            Boolean indicating if OCR is enabled
        """
        return self.load_bool_from_env('OCR_ENABLED', config_enabled)

    def load_llm_enabled(self, llm_client=None) -> bool:
        """
        Load LLM enabled status from environment

        Args:
            llm_client: LLM client instance (optional, for fallback)

        Returns:
            Boolean indicating if LLM is enabled
        """
        # Try to load from environment first
        env_value = os.getenv('LLM_ENABLED', '').lower()

        if env_value:
            if env_value in ('true', 'yes', '1'):
                self.logger.info(f"LLM enabled from environment: True (value: {env_value})")
                return True
            elif env_value in ('false', 'no', '0'):
                self.logger.info(f"LLM disabled from environment: False (value: {env_value})")
                return False
            else:
                self.logger.warning(f"Invalid LLM_ENABLED value: {env_value}, defaulting based on client availability")

        # Fallback: use client availability
        enabled = llm_client is not None
        self.logger.info(f"LLM enabled based on llm_client availability: {enabled}")
        return enabled

    def get_llm_config(self) -> Dict[str, Any]:
        """
        Get LLM configuration from environment

        Returns:
            Dictionary with LLM configuration
        """
        return {
            "api_key": os.getenv("OPENAI_API_KEY", "your_llm_api_key"),
            "model": os.getenv("AI_REQUEST_MODEL", "gpt-4"),
            "timeout": int(os.getenv("VERIFY_TIMEOUT", "30"))
        }

    def load_wechat_config(self) -> Dict[str, Any]:
        """
        Load WeChat-specific configuration from environment

        Returns:
            Dictionary with WeChat configuration
        """
        return {
            "search_timeout": int(os.getenv("WECHAT_SEARCH_TIMEOUT", "30")),
            "read_timeout": int(os.getenv("WECHAT_READ_TIMEOUT", "60")),
            "max_retries": int(os.getenv("WECHAT_MAX_RETRIES", "3")),
            "bundle_id": os.getenv("WECHAT_BUNDLE_ID", "com.tencent.xinWeChat")
        }
