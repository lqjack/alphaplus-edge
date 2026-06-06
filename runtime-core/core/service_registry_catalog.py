# -*- coding: utf-8 -*-
"""
Service registry catalog — abstract service definitions with static + runtime layers.

Canonical static ports: dataproai/resources/service_ports.json
Runtime registrations: dataproai/data/service_registry/runtime.json (auto-persisted)

Reverse index: port -> service id + protocol
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_DATAPROAI_ROOT = Path(__file__).resolve().parent.parent.parent
_PROJECT_ROOT = _DATAPROAI_ROOT.parent
_STATIC_FILE = _DATAPROAI_ROOT / "resources" / "service_ports.json"
_RUNTIME_DIR = _DATAPROAI_ROOT / "data" / "service_registry"
_RUNTIME_FILE = _RUNTIME_DIR / "runtime.json"
_SCHEMA_ENTRY = _PROJECT_ROOT / "schemas" / "service-registry-v1.schema.json"

_SERVICE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_REPO_REF_FIELDS = ("schema_ref", "manifest_ref", "openapi_ref")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _save_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _validate_start_bundle(working_dir: str, entry_point: str) -> None:
    """Ensure working_dir (repo-relative dir) and entry_point (file under it) exist."""
    wd = str(working_dir or "").strip()
    ep = str(entry_point or "").strip()
    if not wd or not ep:
        raise ValueError("working_dir and entry_point are both required for startable services")
    root = _PROJECT_ROOT.resolve()
    wd_path = (root / wd).resolve()
    try:
        wd_path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"working_dir must be under project root: {wd}") from exc
    if not wd_path.is_dir():
        raise ValueError(f"working_dir not found: {wd}")
    entry_path = (wd_path / ep).resolve()
    try:
        entry_path.relative_to(wd_path)
    except ValueError as exc:
        raise ValueError(f"entry_point must be inside working_dir: {ep}") from exc
    if not entry_path.is_file():
        raise ValueError(f"entry_point file not found: {wd}/{ep}")


def _start_bundle_valid(working_dir: Optional[str], entry_point: Optional[str]) -> bool:
    wd = str(working_dir or "").strip()
    ep = str(entry_point or "").strip()
    if not wd or not ep:
        return False
    try:
        _validate_start_bundle(wd, ep)
        return True
    except ValueError:
        return False


def _extract_start_fields(entry: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Any]:
    meta = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}
    working_dir = entry.get("working_dir") or meta.get("working_dir")
    entry_point = entry.get("entry_point") or meta.get("entry_point")
    start_command = entry.get("start_command") or meta.get("start_command")
    wd = str(working_dir).strip() if working_dir else None
    ep = str(entry_point).strip() if entry_point else None
    return wd or None, ep or None, start_command


def _compute_startable(
    entry: Dict[str, Any],
    *,
    source: str,
    working_dir: Optional[str],
    entry_point: Optional[str],
    explicit: Optional[bool] = None,
) -> bool:
    if explicit is not None:
        if explicit and not _start_bundle_valid(working_dir, entry_point):
            raise ValueError(
                "startable=true requires valid repo-relative working_dir and entry_point"
            )
        return bool(explicit)
    if "startable" in entry:
        return bool(entry.get("startable"))
    if source == "runtime":
        return _start_bundle_valid(working_dir, entry_point)
    return _start_bundle_valid(working_dir, entry_point)


def _validate_repo_ref(ref: Optional[str], field_name: str) -> None:
    """Ensure schema/manifest/openapi paths exist under the repo root."""
    if not ref:
        return
    text = str(ref).strip()
    if text.startswith(("http://", "https://")):
        return
    root = _PROJECT_ROOT.resolve()
    path = (root / text).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be under project root: {text}") from exc
    if not path.is_file():
        raise ValueError(f"{field_name} file not found: {text}")


class ServiceRegistryCatalog:
    """Merged static + runtime service catalog with port allocation and reverse lookup."""

    def __init__(
        self,
        *,
        static_file: Path = _STATIC_FILE,
        runtime_file: Path = _RUNTIME_FILE,
    ) -> None:
        self.static_file = static_file
        self.runtime_file = runtime_file
        self._static_raw: Dict[str, Any] = {}
        self._runtime_raw: Dict[str, Any] = {}
        self._services: Dict[str, Dict[str, Any]] = {}
        self._port_index: Dict[int, List[Dict[str, Any]]] = {}
        self.reload()

    def reload(self) -> None:
        self._static_raw = _load_json(self.static_file)
        self._runtime_raw = _load_json(self.runtime_file)
        self._services = {}
        self._port_index = {}
        static_services = self._static_raw.get("services") or {}
        if isinstance(static_services, dict):
            for sid, entry in static_services.items():
                if not isinstance(entry, dict):
                    continue
                if (entry.get("metadata") or {}).get("alias_for"):
                    continue
                self._services[sid] = self._normalize_entry(sid, entry, source="static")
        runtime_services = self._runtime_raw.get("services") or {}
        if isinstance(runtime_services, dict):
            for sid, entry in runtime_services.items():
                if not isinstance(entry, dict):
                    continue
                self._services[sid] = self._normalize_entry(sid, entry, source="runtime")
        self._rebuild_port_index()

    def _normalize_entry(
        self, service_id: str, entry: Dict[str, Any], *, source: str
    ) -> Dict[str, Any]:
        ports = entry.get("ports") or {}
        if not isinstance(ports, dict):
            ports = {}
        ports = {str(k): int(v) for k, v in ports.items() if v is not None}
        meta = dict(entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {})
        working_dir, entry_point, start_command = _extract_start_fields(entry)
        if working_dir:
            meta.setdefault("working_dir", working_dir)
        if entry_point:
            meta.setdefault("entry_point", entry_point)
        if start_command is not None:
            meta.setdefault("start_command", start_command)
        schema_ref = entry.get("schema_ref") or meta.get("schema_ref")
        manifest_ref = entry.get("manifest_ref") or meta.get("manifest_ref")
        explicit_startable = entry.get("startable") if "startable" in entry else None
        startable = _compute_startable(
            entry,
            source=source,
            working_dir=working_dir,
            entry_point=entry_point,
            explicit=explicit_startable,
        )
        return {
            "id": service_id,
            "description": entry.get("description") or "",
            "ports": ports,
            "schema_ref": schema_ref,
            "manifest_ref": manifest_ref,
            "openapi_ref": entry.get("openapi_ref") or meta.get("openapi_ref"),
            "submodule": entry.get("submodule") or meta.get("submodule"),
            "tags": list(entry.get("tags") or meta.get("tags") or []),
            "depends": list(entry.get("depends") or []),
            "health_endpoint": (
                entry.get("health_endpoint")
                or meta.get("health_endpoint")
                or "/health"
            ),
            "source": source,
            "registered_at": entry.get("registered_at"),
            "metadata": meta,
            "index": entry.get("index"),
            "enabled": entry.get("enabled", True),
            "working_dir": working_dir,
            "entry_point": entry_point,
            "start_command": start_command,
            "startable": startable,
        }

    def _rebuild_port_index(self) -> None:
        self._port_index = {}
        for sid, entry in self._services.items():
            for protocol, port in (entry.get("ports") or {}).items():
                self._port_index.setdefault(int(port), []).append(
                    {
                        "service_id": sid,
                        "protocol": protocol,
                        "description": entry.get("description"),
                        "schema_ref": entry.get("schema_ref"),
                        "manifest_ref": entry.get("manifest_ref"),
                        "source": entry.get("source"),
                    }
                )

    def list_services(self, *, source: Optional[str] = None) -> List[Dict[str, Any]]:
        out = [deepcopy(v) for v in self._services.values()]
        if source:
            out = [s for s in out if s.get("source") == source]
        return sorted(out, key=lambda s: s["id"])

    def get_service(self, service_id: str) -> Optional[Dict[str, Any]]:
        entry = self._services.get(service_id)
        return deepcopy(entry) if entry else None

    def get_port(self, service_id: str, protocol: str = "api") -> int:
        entry = self._services.get(service_id)
        if not entry:
            raise KeyError(f"Service '{service_id}' not found")
        ports = entry.get("ports") or {}
        if protocol not in ports:
            raise KeyError(f"Protocol '{protocol}' not found for service '{service_id}'")
        return int(ports[protocol])

    def resolve_by_port(self, port: int) -> List[Dict[str, Any]]:
        return deepcopy(self._port_index.get(int(port), []))

    def get_port_rules(self) -> Dict[str, Any]:
        return deepcopy(self._static_raw.get("port_allocation_rules") or {})

    def get_schema_uri(self) -> str:
        return "schemas/service-registry-v1.schema.json"

    def _used_ports(self) -> set[int]:
        used: set[int] = set()
        for entry in self._services.values():
            for p in (entry.get("ports") or {}).values():
                used.add(int(p))
        infra = self._static_raw.get("infrastructure_ports") or {}
        for spec in infra.values():
            if isinstance(spec, dict):
                for key, val in spec.items():
                    if key != "description" and isinstance(val, int):
                        used.add(val)
        return used

    def _next_mcp_block_index(self) -> int:
        rules = self._static_raw.get("port_allocation_rules") or {}
        base = int(rules.get("base_port", 10300))
        per = int(rules.get("ports_per_service", 10))
        max_index = -1
        for entry in self._services.values():
            api_port = (entry.get("ports") or {}).get("api")
            if api_port is None:
                continue
            api_port = int(api_port)
            if base <= api_port < base + 200:
                idx = (api_port - base) // per
                max_index = max(max_index, idx)
        return max_index + 1

    def allocate_ports(
        self,
        *,
        submodule: str = "dataproai",
        protocols: Optional[List[str]] = None,
    ) -> Dict[str, int]:
        """Allocate a new port block using service_ports.json rules (MCP range)."""
        rules = self._static_raw.get("port_allocation_rules") or {}
        base = int(rules.get("base_port", 10300))
        per = int(rules.get("ports_per_service", 10))
        offsets = rules.get("protocol_offsets") or {
            "api": 0,
            "mcp": 1,
            "sse": 2,
            "http": 3,
            "ws": 4,
        }
        if protocols is None:
            protocols = ["api", "mcp", "sse", "http", "ws"]
        used = self._used_ports()
        index = self._next_mcp_block_index()
        while True:
            block_base = base + index * per
            candidate = {
                proto: block_base + int(offsets.get(proto, 0))
                for proto in protocols
                if proto in offsets or proto == "api"
            }
            if "api" not in candidate:
                candidate["api"] = block_base + int(offsets.get("api", 0))
            if not any(p in used for p in candidate.values()):
                return candidate
            index += 1
            if index > 200:
                raise RuntimeError("No free port block in MCP allocation range")

    def register_service(
        self,
        *,
        service_id: str,
        description: str = "",
        ports: Optional[Dict[str, int]] = None,
        auto_allocate: bool = True,
        schema_ref: Optional[str] = None,
        manifest_ref: Optional[str] = None,
        openapi_ref: Optional[str] = None,
        submodule: str = "custom",
        tags: Optional[List[str]] = None,
        depends: Optional[List[str]] = None,
        health_endpoint: str = "/health",
        working_dir: Optional[str] = None,
        entry_point: Optional[str] = None,
        start_command: Optional[Any] = None,
        startable: Optional[bool] = None,
        overwrite: bool = False,
    ) -> Dict[str, Any]:
        if not _SERVICE_ID_RE.match(service_id):
            raise ValueError(
                f"Invalid service id '{service_id}' (use lowercase snake_case)"
            )
        static_services = self._static_raw.get("services") or {}
        if service_id in static_services:
            raise ValueError(
                f"Service '{service_id}' is defined in static service_ports.json; "
                "add ports there via PR instead of runtime register"
            )
        if service_id in self._services and not overwrite:
            existing = self._services[service_id]
            if existing.get("source") == "static":
                raise ValueError(
                    f"Service '{service_id}' is static; cannot overwrite via runtime API"
                )
            raise ValueError(f"Service '{service_id}' already registered")

        for field_name in _REPO_REF_FIELDS:
            _validate_repo_ref(locals().get(field_name), field_name)

        wd = str(working_dir or "").strip() or None
        ep = str(entry_point or "").strip() or None
        if ep and not wd:
            raise ValueError("working_dir is required when entry_point is set")
        if wd and ep:
            _validate_start_bundle(wd, ep)
        elif wd or ep:
            raise ValueError("entry_point and working_dir must be provided together")

        if ports is None:
            if not auto_allocate:
                raise ValueError("ports required when auto_allocate=false")
            ports = self.allocate_ports(submodule=submodule)
        else:
            ports = {str(k): int(v) for k, v in ports.items()}
            used = self._used_ports()
            for proto, port in ports.items():
                conflicts = [
                    c
                    for c in self._port_index.get(int(port), [])
                    if c["service_id"] != service_id or c["protocol"] != proto
                ]
                if conflicts and service_id not in self._services:
                    raise ValueError(f"Port {port} already used by {conflicts[0]['service_id']}")

        start_meta: Dict[str, Any] = {}
        if wd:
            start_meta["working_dir"] = wd
        if ep:
            start_meta["entry_point"] = ep
        if start_command is not None:
            start_meta["start_command"] = start_command

        entry = {
            "description": description,
            "ports": ports,
            "schema_ref": schema_ref,
            "manifest_ref": manifest_ref,
            "openapi_ref": openapi_ref,
            "submodule": submodule,
            "tags": tags or [],
            "depends": depends or [],
            "health_endpoint": health_endpoint,
            "registered_at": _utc_now(),
            "source": "runtime",
            "metadata": start_meta,
            **start_meta,
        }
        if startable is not None:
            entry["startable"] = bool(startable)
        elif _start_bundle_valid(wd, ep):
            entry["startable"] = True
        else:
            entry["startable"] = False
        if entry.get("startable") and not _start_bundle_valid(wd, ep):
            raise ValueError(
                "startable=true requires valid repo-relative working_dir and entry_point"
            )

        runtime_services = dict(self._runtime_raw.get("services") or {})
        runtime_services[service_id] = entry
        self._runtime_raw["version"] = "1"
        self._runtime_raw["updated_at"] = _utc_now()
        self._runtime_raw["services"] = runtime_services
        _save_json(self.runtime_file, self._runtime_raw)
        self.reload()
        return self.get_service(service_id) or entry

    def to_public_catalog(self) -> Dict[str, Any]:
        return {
            "version": "1",
            "static_file": str(self.static_file.relative_to(_PROJECT_ROOT)),
            "runtime_file": str(self.runtime_file.relative_to(_PROJECT_ROOT)),
            "schema_ref": self.get_schema_uri(),
            "port_rules": self.get_port_rules(),
            "service_count": len(self._services),
            "services": self.list_services(),
            "port_index_sample": {
                str(port): entries for port, entries in sorted(self._port_index.items())[:20]
            },
        }


_catalog: Optional[ServiceRegistryCatalog] = None


def get_catalog() -> ServiceRegistryCatalog:
    global _catalog
    if _catalog is None:
        _catalog = ServiceRegistryCatalog()
    return _catalog


def reload_catalog() -> ServiceRegistryCatalog:
    global _catalog
    _catalog = ServiceRegistryCatalog()
    return _catalog
