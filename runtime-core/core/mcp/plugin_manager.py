# -*- coding: utf-8 -*-
"""
Plugin Manager for MCP Servers.
Responsible for:
- Discovering MCP plugins.
- Managing plugin dependencies and virtual environments (.mcp-venv).
- Providing Python executable paths for plugins.
"""

import logging
import os
import sys
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional

class PluginManager:
    """MCP Server Plugin Manager - Independent Venv Support"""

    def __init__(self, servers_dir: str = None):
        project_root = Path(__file__).parent.parent.parent.parent

        if servers_dir is None:
            # 新架构优先使用 src/servers，同时兼容旧目录 src/mcp_legacy/servers
            self.servers_dirs = [
                project_root / "src" / "servers",
                project_root / "src" / "mcp_legacy" / "servers",
            ]
        else:
            self.servers_dirs = [Path(servers_dir)]

        self.plugins: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger("mcp-plugin-manager")
        self.venv_dir_name = ".mcp-venv"  # Specific venv name for MCP servers

    def discover_plugins(self):
        """Discover all available MCP server plugins"""
        existing_dirs = [d for d in self.servers_dirs if d.exists()]
        if not existing_dirs:
            self.logger.warning(f"MCP servers directories not found: {self.servers_dirs}")
            return

        # 新目录优先，同名插件不重复加载
        plugin_name_to_dir = {}
        for base_dir in existing_dirs:
            plugin_dirs = [d for d in base_dir.iterdir() if d.is_dir()]
            self.logger.info(f"Found {len(plugin_dirs)} plugin directories at {base_dir}")
            for plugin_dir in plugin_dirs:
                plugin_name_to_dir.setdefault(plugin_dir.name, plugin_dir)

        plugin_items = list(plugin_name_to_dir.items())
        total_plugins = len(plugin_items)

        for index, (plugin_name, server_dir) in enumerate(plugin_items, 1):
            self.logger.info(f"Loading plugin {index}/{total_plugins}: {plugin_name}")

            # Load as MCP (stdio/sse)
            self._load_plugin(plugin_name, server_dir, "mcp")

            # Load as API (http/rest)
            self._load_plugin(plugin_name, server_dir, "api")

    def _load_plugin(self, base_name: str, plugin_dir: Path, protocol: str = "mcp"):
        """Load a single plugin variant"""
        # Check for dependency files
        pyproject_path = plugin_dir / "pyproject.toml"
        requirements_path = plugin_dir / "requirements.txt"

        if not pyproject_path.exists() and requirements_path.exists():
            # Auto-generate pyproject.toml from requirements.txt
            self._generate_pyproject_from_requirements(base_name, plugin_dir, requirements_path)

        # Find server entry point
        server_entry = self._find_server_entry(plugin_dir, protocol)
        if not server_entry:
            # Only log warning if strictly expecting it, but some plugins might support only one protocol
            # self.logger.debug(f"No server entry found for plugin: {base_name}, protocol: {protocol}")
            return

        # Create unique plugin key: e.g., "ai_mcp", "ai_api"
        plugin_key = f"{base_name}_{protocol}"

        self.plugins[plugin_key] = {
            'name': plugin_key,
            'base_name': base_name,
            'protocol': protocol,
            'dir': plugin_dir,
            'entry': server_entry,
            'venv_path': plugin_dir / self.venv_dir_name,
            'pyproject_path': pyproject_path,
            'requirements_path': requirements_path
        }

        self.logger.info(f"Plugin {plugin_key} loaded successfully (Entry: {server_entry.name})")

    def _find_server_entry(self, plugin_dir: Path, protocol: str = "mcp") -> Optional[Path]:
        """Find server entry file based on protocol"""
        # Common entry names
        entry_names = ["mcp_server.py", "server.py"] # Default for MCP
        
        if protocol == "api":
            entry_names = ["api_server.py"]

        for entry_name in entry_names:
            entry_path = plugin_dir / entry_name
            if entry_path.exists():
                return entry_path
        return None

    def _generate_pyproject_from_requirements(self, plugin_name: str, plugin_dir: Path, requirements_path: Path):
        """Generate pyproject.toml from requirements.txt"""
        try:
            with open(requirements_path, 'r', encoding='utf-8') as f:
                requirements = f.read().strip()

            deps_list = [f'    "{req.strip()}",' for req in requirements.split('\n') if req.strip() and not req.startswith('#')]
            deps_str = "\n".join(deps_list)

            pyproject_content = f"""[build-system]
requires = ["setuptools>=61.0.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "{plugin_name}"
version = "0.1.0"
description = "{plugin_name} MCP server"
authors = [
    {{name = "DataProAI", email = "admin@dataproai.com"}}
]
requires-python = ">=3.10"
dependencies = [
{deps_str}
]
"""
            pyproject_path = plugin_dir / "pyproject.toml"
            with open(pyproject_path, 'w', encoding='utf-8') as f:
                f.write(pyproject_content)
            
            self.logger.info(f"Generated pyproject.toml for {plugin_name}")

        except Exception as e:
            self.logger.error(f"Failed to generate pyproject.toml for {plugin_name}: {e}")

    def get_plugin_python(self, plugin_key: str, install_if_missing: bool = True) -> Optional[Path]:
        """Get the Python interpreter path for a plugin"""
        if plugin_key not in self.plugins:
            return None

        plugin_info = self.plugins[plugin_key]
        venv_path = plugin_info['venv_path']
        
        # Determine python executable path
        if os.name == 'nt':  # Windows
            python_path = venv_path / "Scripts" / "python.exe"
        else:  # Unix (Linux, macOS)
            python_path = venv_path / "bin" / "python"

        # Install dependencies if missing and requested
        if (not python_path.exists()) and install_if_missing:
            self._ensure_plugin_deps_installed(plugin_info['base_name'], plugin_info['dir'])

        if python_path.exists():
            return python_path
        
        return None

    def _ensure_plugin_deps_installed(self, plugin_name: str, plugin_dir: Path):
        """Ensure plugin dependencies are installed in isolated venv"""
        venv_path = plugin_dir / self.venv_dir_name
        
        try:
            # Create venv if not exists
            if not venv_path.exists():
                self.logger.info(f"Creating virtual environment for {plugin_name} at {venv_path}")
                # Try uv first
                try:
                    subprocess.run(["uv", "venv", str(venv_path)], 
                                 capture_output=True, text=True, cwd=plugin_dir, check=True)
                except (subprocess.CalledProcessError, FileNotFoundError):
                    # Fallback to python -m venv
                    self.logger.info(f"uv not found/failed, using venv for {plugin_name}")
                    subprocess.run([sys.executable, "-m", "venv", str(venv_path)],
                                 capture_output=True, text=True, cwd=plugin_dir, check=True)

            # Determine pip path
            if os.name == 'nt':
                pip_path = venv_path / "Scripts" / "pip.exe"
            else:
                pip_path = venv_path / "bin" / "pip"

            # Check if pip exists, install if missing
            if not pip_path.exists():
                self._install_pip(plugin_name, plugin_dir, venv_path)

            if not pip_path.exists():
                self.logger.error(f"Pip still missing for {plugin_name}, cannot install deps.")
                return

            # Install dependencies
            self.logger.info(f"Installing dependencies for {plugin_name}")
            
            # Prepare env (clear VIRTUAL_ENV)
            env = os.environ.copy()
            if "VIRTUAL_ENV" in env:
                del env["VIRTUAL_ENV"]

            # Try install from current directory (setup.py/pyproject.toml)
            result = subprocess.run(
                [str(pip_path), "install", "-e", ".", "--timeout", "1800"],
                capture_output=True, text=True, cwd=plugin_dir, env=env, timeout=1800
            )

            if result.returncode != 0:
                self.logger.warning(f"Standard install failed for {plugin_name}: {result.stderr}")
                # Fallback to requirements.txt
                self._install_requirements_fallback(plugin_name, plugin_dir, pip_path)
            else:
                self.logger.info(f"Successfully installed dependencies for {plugin_name}")

        except Exception as e:
            self.logger.error(f"Error ensuring deps for {plugin_name}: {e}", exc_info=True)

    def _install_pip(self, plugin_name: str, plugin_dir: Path, venv_path: Path):
        """Install pip into venv if missing"""
        python_exe = venv_path / ("Scripts/python.exe" if os.name == 'nt' else "bin/python")
        try:
            subprocess.run([str(python_exe), "-m", "ensurepip", "--upgrade"], 
                         capture_output=True, text=True, cwd=plugin_dir, check=True)
        except Exception as e:
            self.logger.error(f"Failed to install pip for {plugin_name}: {e}")

    def _install_requirements_fallback(self, plugin_name: str, plugin_dir: Path, pip_path: Path):
        """Fallback installation using requirements.txt"""
        requirements_path = plugin_dir / "requirements.txt"
        if requirements_path.exists():
            self.logger.info(f"Installing requirements.txt for {plugin_name}")
            subprocess.run(
                [str(pip_path), "install", "-r", str(requirements_path)],
                capture_output=True, text=True, cwd=plugin_dir
            )

# Singleton instance
_plugin_manager = None

def get_plugin_manager():
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
        _plugin_manager.discover_plugins()
    return _plugin_manager
