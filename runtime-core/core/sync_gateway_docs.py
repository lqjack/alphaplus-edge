#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Documentation Sync Script for MCP Gateway

This script syncs documentation from implementation to markdown files.
It extracts docstrings, generates API references, and updates architecture docs.

Usage:
    python sync_gateway_docs.py              # Sync all docs
    python sync_gateway_docs.py --module     # Generate module docs
    python sync_gateway_docs.py --api        # Generate API reference
    python sync_gateway_docs.py --arch      # Update architecture doc
"""

import os
import sys
import re
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional

# Fix Windows encoding
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
CORE_DIR = PROJECT_ROOT / "src" / "core"

# Source files to sync docs from
SOURCE_FILES = {
    "mcp_gateway": CORE_DIR / "mcp_gateway.py",
    "mcp_executor": CORE_DIR / "mcp_executor.py",
    "service_manager": CORE_DIR / "service_manager.py",
}


def extract_docstrings(file_path: Path) -> Dict[str, str]:
    """Extract docstrings from a Python file"""
    docstrings = {}
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Parse classes and functions
    current_class = None
    current_func = None
    current_doc = []
    in_docstring = False
    docstring_start = None
    
    for i, line in enumerate(content.split('\n'), 1):
        stripped = line.strip()
        
        # Check for class definition
        class_match = re.match(r'^class (\w+)', stripped)
        if class_match:
            if current_doc and current_class:
                docstrings[current_class] = '\n'.join(current_doc)
            current_class = class_match.group(1)
            current_func = None
            current_doc = []
            continue
        
        # Check for function definition
        func_match = re.match(r'^    def (\w+)\(', stripped) or re.match(r'^def (\w+)\(', stripped)
        if func_match:
            if current_doc and (current_class or current_func):
                key = f"{current_class}.{current_func}" if current_class else current_func
                if key:
                    docstrings[key] = '\n'.join(current_doc)
            current_func = func_match.group(1)
            current_doc = []
            continue
        
        # Check for docstring
        if '"""' in stripped or "'''" in stripped:
            if not in_docstring:
                in_docstring = True
                docstring_start = i
                # Extract content after """
                match = re.search(r'"""(.+?)"""', stripped) or re.search(r"'''(.+?)'''", stripped)
                if match:
                    current_doc.append(match.group(1).strip())
                    in_docstring = False
            else:
                in_docstring = False
                if current_doc:
                    key = f"{current_class}.{current_func}" if current_class and current_func else (current_class or current_func or "")
                    if key:
                        docstrings[key] = '\n'.join(current_doc)
                current_doc = []
            continue
        
        if in_docstring and stripped:
            current_doc.append(stripped)
    
    # Handle last docstring
    if current_doc and (current_class or current_func):
        key = f"{current_class}.{current_func}" if current_class and current_func else (current_class or current_func or "")
        if key:
            docstrings[key] = '\n'.join(current_doc)
    
    return docstrings


def generate_module_doc(module_name: str, file_path: Path) -> str:
    """Generate module documentation"""
    docstrings = extract_docstrings(file_path)
    
    lines = [
        f"# {module_name.replace('_', ' ').title()} Module",
        "",
        f"> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Overview",
        "",
    ]
    
    # Module docstring
    if module_name in docstrings:
        lines.append(docstrings[module_name])
        lines.append("")
    
    lines.extend([
        "## Classes",
        ""
    ])
    
    # Find classes
    classes = {k: v for k, v in docstrings.items() if '.' not in k and not k.startswith('_')}
    for class_name, doc in classes.items():
        lines.append(f"### {class_name}")
        lines.append("")
        if doc:
            lines.append(doc)
        lines.append("")
        
        # Find methods
        methods = {k: v for k, v in docstrings.items() if k.startswith(f"{class_name}.")}
        if methods:
            lines.append("**Methods:**")
            lines.append("")
            for method_name, method_doc in methods.items():
                short_name = method_name.split('.')[-1]
                if not short_name.startswith('_'):
                    lines.append(f"- `{short_name}`")
                    if method_doc:
                        # Take first line only
                        first_line = method_doc.strip().split('\n')[0]
                        lines.append(f"  - {first_line}")
            lines.append("")
    
    lines.extend([
        "## Usage Example",
        "",
        "```python",
        f"from core.{module_name} import get_mcp_gateway",
        "",
        "# Get gateway instance",
        "gateway = get_mcp_gateway()",
        "",
        "# List services",
        "services = gateway.list_services()",
        "",
        "# Get service status",
        "status = gateway.get_service_status('wechat', 'mcp')",
        "```",
        ""
    ])
    
    return '\n'.join(lines)


def generate_api_reference() -> str:
    """Generate API reference for all gateway modules"""
    lines = [
        "# MCP Gateway API Reference",
        "",
        f"> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Table of Contents",
        "",
        "- [ServiceStatus](#servicestatus)",
        "- [LoadBalancingStrategy](#loadbalancingstrategy)",
        "- [ServiceInstance](#serviceinstance)",
        "- [ServicePool](#servicepool)",
        "- [ServiceRegistry](#serviceregistry)",
        "- [MCPGateway](#mcpgateway)",
        "",
        "---",
        ""
    ]
    
    for module_name, file_path in SOURCE_FILES.items():
        if file_path.exists():
            docstrings = extract_docstrings(file_path)
            
            lines.append(f"## {module_name.replace('_', ' ').title()}")
            lines.append("")
            
            for name, doc in docstrings.items():
                if not name.startswith('_'):
                    lines.append(f"### {name}")
                    lines.append("")
                    lines.append("```python")
                    lines.append(f"# {name}")
                    lines.append("```")
                    lines.append("")
                    if doc:
                        lines.append(doc)
                    lines.append("")
    
    return '\n'.join(lines)


def update_architecture_doc() -> str:
    """Update the architecture evolution document"""
    content = """
---

## MCP Gateway Architecture (2026-03-18)

### Overview

The MCP Gateway provides unified service management with auto-start, load balancing, and health monitoring.

### Components

| Component | Description | Status |
|-----------|-------------|--------|
| `ServiceStatus` | Service state enumeration | ✅ Complete |
| `LoadBalancingStrategy` | Load balancing algorithms | ✅ Complete |
| `ServiceInstance` | Single service instance | ✅ Complete |
| `ServicePool` | Multiple instances management | ✅ Complete |
| `ServiceRegistry` | Central service registry | ✅ Complete |
| `MCPGateway` | Main gateway class | ✅ Complete |

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    job_manager_mcp.py                       │
│                    (Task Execution)                         │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    ServiceExecutor                          │
│         (Thread-safe execution + Gateway)                  │
│  • submit_call()  • list_services()  • get_service_status() │
└──────┬─────────────────────────────────────┬───────────────┘
       │                                     │
       ▼                                     ▼
┌──────────────┐                   ┌──────────────────────┐
│  Direct Call │                   │   MCP Gateway        │
│  (Original)  │                   │  • ServiceRegistry  │
│              │                   │  • ServicePool     │
│              │                   │  • Auto-start      │
└──────────────┘                   └──────────────────────┘
                                       │
                                       ▼
                          ┌──────────────────────────┐
                          │  ServiceManager        │
                          │  (Process/Client Mgmt) │
                          └──────────────────────────┘
```

### Features

1. **Auto-start**: Automatically starts services when called
2. **Load Balancing**: Supports multiple instances with configurable strategies
3. **Health Monitoring**: Tracks service health and failed checks
4. **Unified Management**: Single entry point for all service calls

### Usage

```python
from core.mcp_executor import get_service_executor

# Get executor (gateway enabled by default)
executor = get_service_executor()

# List all services
services = executor.list_services()

# Get service status
status = executor.get_service_status("wechat", "mcp")

# Submit call (auto-start enabled)
result = executor.submit_call("wechat_mcp", "wechat_sync_article", 
                           {"article_id": "123"}, timeout=60)
```

### Integration

The gateway integrates with `ServiceExecutor` and provides:
- Transparent service auto-start
- Fallback to direct calls if gateway fails
- Configurable gateway usage via `use_gateway` parameter
"""
    return content


def sync_docs(output_dir: Optional[Path] = None):
    """Sync all documentation"""
    if output_dir is None:
        output_dir = DOCS_DIR
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results = {}
    
    # Generate module docs
    for module_name, file_path in SOURCE_FILES.items():
        if file_path.exists():
            doc = generate_module_doc(module_name, file_path)
            output_file = output_dir / f"gateway_{module_name}_docs.md"
            output_file.write_text(doc, encoding='utf-8')
            results[module_name] = output_file
            print(f"[OK] Generated: {output_file}")
    
    # Generate API reference
    api_doc = generate_api_reference()
    api_file = output_dir / "gateway_api_reference.md"
    api_file.write_text(api_doc, encoding='utf-8')
    print(f"[OK] Generated: {api_file}")
    results["api_reference"] = api_file
    
    # Update architecture doc
    arch_doc = update_architecture_doc()
    
    # Try to append to existing architecture doc
    arch_file = DOCS_DIR / "ARCHITECTURE_EVOLUTION.md"
    if arch_file.exists():
        existing = arch_file.read_text(encoding='utf-8')
        # Find position to insert (before the last ---)
        if "<!-- GATEWAY DOCS INSERT -->" in existing:
            existing = existing.replace(
                "<!-- GATEWAY DOCS INSERT -->",
                f"<!-- GATEWAY DOCS INSERT -->\n{arch_doc}"
            )
        else:
            existing = existing + f"\n{arch_doc}"
        arch_file.write_text(existing, encoding='utf-8')
        print(f"[OK] Updated: {arch_file}")
    else:
        arch_file = output_dir / "gateway_architecture.md"
        arch_file.write_text(f"# MCP Gateway Architecture\n{arch_doc}", encoding='utf-8')
        print(f"[OK] Generated: {arch_file}")
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Sync MCP Gateway documentation")
    parser.add_argument('--output', '-o', type=str, help='Output directory')
    parser.add_argument('--module', '-m', action='store_true', help='Generate module docs only')
    parser.add_argument('--api', '-a', action='store_true', help='Generate API reference only')
    parser.add_argument('--arch', action='store_true', help='Update architecture doc only')
    
    args = parser.parse_args()
    
    output_dir = Path(args.output) if args.output else None
    
    if args.module:
        # Generate module docs only
        for module_name, file_path in SOURCE_FILES.items():
            if file_path.exists():
                doc = generate_module_doc(module_name, file_path)
                output_file = (output_dir or DOCS_DIR) / f"gateway_{module_name}_docs.md"
                output_file.write_text(doc, encoding='utf-8')
                print(f"[OK] Generated: {output_file}")
    elif args.api:
        # Generate API reference only
        api_doc = generate_api_reference()
        api_file = (output_dir or DOCS_DIR) / "gateway_api_reference.md"
        api_file.write_text(api_doc, encoding='utf-8')
        print(f"[OK] Generated: {api_file}")
    elif args.arch:
        # Update architecture doc only
        arch_doc = update_architecture_doc()
        arch_file = (output_dir or DOCS_DIR) / "gateway_architecture.md"
        arch_file.write_text(f"# MCP Gateway Architecture\n{arch_doc}", encoding='utf-8')
        print(f"[OK] Generated: {arch_file}")
    else:
        # Sync all
        results = sync_docs(output_dir)
        print(f"\n[OK] Documentation sync complete! ({len(results)} files)")


if __name__ == "__main__":
    main()
