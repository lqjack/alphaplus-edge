# -*- coding: utf-8 -*-
"""Tests for service registry catalog (static + runtime overlay)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.service_registry_catalog import ServiceRegistryCatalog


class ServiceRegistryCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        static = root / "service_ports.json"
        static.write_text(
            json.dumps(
                {
                    "port_allocation_rules": {
                        "base_port": 10300,
                        "ports_per_service": 10,
                        "protocol_offsets": {
                            "api": 0,
                            "mcp": 1,
                        },
                    },
                    "services": {
                        "demo_static": {
                            "description": "static demo",
                            "ports": {"api": 10300, "mcp": 10301},
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        self.catalog = ServiceRegistryCatalog(
            static_file=static,
            runtime_file=root / "runtime.json",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_static_port_lookup(self):
        self.assertEqual(self.catalog.get_port("demo_static", "api"), 10300)

    def test_register_runtime_persists(self):
        entry = self.catalog.register_service(
            service_id="demo_runtime",
            description="runtime demo",
            schema_ref="schemas/service-registry-v1.schema.json",
        )
        self.assertIn("api", entry["ports"])
        self.assertEqual(entry["source"], "runtime")
        self.assertFalse(entry.get("startable"))
        reloaded = ServiceRegistryCatalog(
            static_file=self.catalog.static_file,
            runtime_file=self.catalog.runtime_file,
        )
        self.assertIsNotNone(reloaded.get_service("demo_runtime"))

    def test_resolve_by_port(self):
        self.catalog.register_service(
            service_id="demo_runtime",
            ports={"api": 10999},
            auto_allocate=False,
        )
        matches = self.catalog.resolve_by_port(10999)
        self.assertEqual(matches[0]["service_id"], "demo_runtime")

    def test_static_service_cannot_be_registered_at_runtime(self):
        with self.assertRaises(ValueError):
            self.catalog.register_service(service_id="demo_static")

    def test_register_validates_schema_ref_exists(self):
        with self.assertRaises(ValueError):
            self.catalog.register_service(
                service_id="demo_bad_schema",
                schema_ref="schemas/does-not-exist.schema.json",
                auto_allocate=True,
            )

    def test_register_accepts_existing_schema_ref(self):
        entry = self.catalog.register_service(
            service_id="demo_with_schema",
            schema_ref="schemas/service-registry-v1.schema.json",
        )
        self.assertEqual(
            entry["schema_ref"], "schemas/service-registry-v1.schema.json"
        )

    def test_register_rejects_missing_schema_ref(self):
        with self.assertRaises(ValueError) as ctx:
            self.catalog.register_service(
                service_id="bad_schema",
                schema_ref="schemas/does-not-exist-v99.schema.json",
            )
        self.assertIn("schema_ref", str(ctx.exception))

    def test_register_accepts_existing_manifest_ref(self):
        entry = self.catalog.register_service(
            service_id="with_manifest",
            manifest_ref="dataproai/src/servers/stock_backend/manifest.json",
            ports={"api": 10998},
            auto_allocate=False,
        )
        self.assertEqual(
            entry.get("manifest_ref"),
            "dataproai/src/servers/stock_backend/manifest.json",
        )

    def test_register_startable_when_entry_point_valid(self):
        entry = self.catalog.register_service(
            service_id="demo_startable",
            ports={"api": 10997},
            auto_allocate=False,
            working_dir="dataproai",
            entry_point="src/main.py",
            schema_ref="schemas/service-registry-v1.schema.json",
        )
        self.assertTrue(entry.get("startable"))
        self.assertEqual(entry.get("working_dir"), "dataproai")
        self.assertEqual(entry.get("entry_point"), "src/main.py")

    def test_register_rejects_startable_without_paths(self):
        with self.assertRaises(ValueError):
            self.catalog.register_service(
                service_id="demo_bad_start",
                ports={"api": 10996},
                auto_allocate=False,
                startable=True,
            )

    def test_register_rejects_entry_point_without_working_dir(self):
        with self.assertRaises(ValueError):
            self.catalog.register_service(
                service_id="demo_orphan_ep",
                entry_point="src/main.py",
            )


if __name__ == "__main__":
    unittest.main()
