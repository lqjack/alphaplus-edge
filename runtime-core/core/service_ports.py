# -*- coding: utf-8 -*-
"""
Service Port Configuration
=========================

Port Allocation Rules (端口分配原则):
-------------------------------------
1. 端口范围: 10300-10499 (MCP Server Range)
2. 每个服务占用 10 个连续端口，用于协议扩展
3. 基础公式: base_port + (service_index * 10) + protocol_offset

协议偏移量 (Protocol Offsets):
- api: 0  (主要 API 端口)
- mcp: 1  (MCP 协议端口)
- sse: 2  (Server-Sent Events，预留)
- http: 3 (HTTP 协议，预留)
- ws: 4   (WebSocket 协议，预留)
- 5-9: 保留用于未来扩展

子模块端口分配规则 (五位数编码):
- 千位 (第1位): 定义 submodule
  - 1: dataproai
  - 3: mirofish
  - 4: rag
  - 5: stock

- 百位 (第3位): 划分子模块的不同部分
  - 0: backend
  - 1: frontend
  - 2: native

- 十位+个位 (后2位): submodule 内部不同的 server

端口配置文件: dataproai/resources/service_ports.json

使用示例:
- ai_api: 10300 + (0 * 10) + 0 = 10300
- ai_mcp: 10300 + (0 * 10) + 1 = 10301
- wechat_api: 10300 + (1 * 10) + 0 = 10310
- wechat_mcp: 10300 + (1 * 10) + 1 = 10311

NOTE: 此文件从 JSON 配置文件加载数据
JSON 文件路径: dataproai/resources/service_ports.json
"""

import json
from pathlib import Path
from typing import Dict, Tuple, List, Optional

# 获取配置目录路径
# 配置文件路径: dataproai/resources/service_ports.json
# Path: dataproai/src/core/service_ports.py -> dataproai/resources/
_config_dir = Path(__file__).parent.parent.parent / "resources"
_config_file = _config_dir / "service_ports.json"


# 尝试加载 JSON 配置
def _load_port_config() -> dict:
    """从 JSON 文件加载端口配置"""
    if _config_file.exists():
        try:
            with open(_config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load port config from JSON: {e}")
            print("Using fallback hardcoded configuration")
    return {}


# 加载配置
_port_config = _load_port_config()


# Service Configuration - 从 JSON 加载或使用默认值
def _get_service_ports() -> Dict[str, Dict[str, int]]:
    """获取服务端口配置"""
    if _port_config and "services" in _port_config:
        services = {}
        for service_name, service_data in _port_config["services"].items():
            services[service_name] = service_data.get("ports", {})
        return services
    # Fallback to hardcoded values
    return _FALLBACK_SERVICE_PORTS


def _get_protocol_offsets() -> Dict[str, int]:
    """获取协议偏移量"""
    if _port_config and "port_allocation_rules" in _port_config:
        return _port_config["port_allocation_rules"].get("protocol_offsets", {})
    return {
        "api": 0,
        "mcp": 1,
        "sse": 2,
        "http": 3,
        "ws": 4,
    }


def _get_service_aliases() -> Dict[str, Tuple[str, str]]:
    """获取服务别名"""
    if _port_config and "aliases" in _port_config:
        aliases = {}
        for alias, (service, protocol) in _port_config["aliases"].items():
            aliases[alias] = (service, protocol)
        return aliases
    return {}


def _get_infrastructure_ports() -> Dict[str, Dict]:
    """获取基础设施端口配置"""
    if _port_config and "infrastructure_ports" in _port_config:
        return _port_config["infrastructure_ports"]
    return {}


# Fallback configurations (当 JSON 文件不存在时使用)
_FALLBACK_SERVICE_PORTS = {
    "gateway": {"api": 8001},
    # dataproai services (103xx)
    "ai": {"api": 10300, "mcp": 10301, "sse": 10302, "http": 10303, "ws": 10304},
    "wechat": {"api": 10310, "mcp": 10311, "sse": 10312, "http": 10313, "ws": 10314},
    "tts": {"api": 10320, "mcp": 10321, "sse": 10322, "http": 10323, "ws": 10324},
    "douyin": {"api": 10330, "mcp": 10331, "sse": 10332, "http": 10333, "ws": 10334},
    "youtube": {"api": 10340, "mcp": 10341, "sse": 10342, "http": 10343, "ws": 10344},
    "xiaohongshu": {
        "api": 10350,
        "mcp": 10351,
        "sse": 10352,
        "http": 10353,
        "ws": 10354,
    },
    "fundflow": {"api": 10360, "mcp": 10361, "sse": 10362, "http": 10363, "ws": 10364},
    "market": {"api": 10370, "mcp": 10371, "sse": 10372, "http": 10373, "ws": 10374},
    "sentiment": {"api": 10380, "mcp": 10381, "sse": 10382, "http": 10383, "ws": 10384},
    "news": {"api": 10390, "mcp": 10391, "sse": 10392, "http": 10393, "ws": 10394},
    "a_stock_data": {"api": 10395, "mcp": 10396, "sse": 10397, "http": 10398, "ws": 10399},
    "cls": {"api": 10400, "mcp": 10401, "sse": 10402, "http": 10403, "ws": 10404},
    "macro_data": {
        "api": 10580,
        "mcp": 10581,
        "sse": 10582,
        "http": 10583,
        "ws": 10584,
    },
    "file_parser": {
        "api": 10410,
        "mcp": 10411,
        "sse": 10412,
        "http": 10413,
        "ws": 10414,
    },
    "subtitles": {"api": 10420, "mcp": 10421, "sse": 10422, "http": 10423, "ws": 10424},
    "task_factory": {
        "api": 10430,
        "mcp": 10431,
        "sse": 10432,
        "http": 10433,
        "ws": 10434,
    },
    "telegram": {"api": 10440, "mcp": 10441, "sse": 10442, "http": 10443, "ws": 10444},
    "video_editor": {
        "api": 10450,
        "mcp": 10451,
        "sse": 10452,
        "http": 10453,
        "ws": 10454,
    },
    "video_generator": {
        "api": 10460,
        "mcp": 10461,
        "sse": 10462,
        "http": 10463,
        "ws": 10464,
    },
    "wechat_viewer": {
        "api": 10470,
        "mcp": 10471,
        "sse": 10472,
        "http": 10473,
        "ws": 10474,
    },
    "wx_cli": {
        "api": 10475,
        "mcp": 10476,
        "sse": 10477,
        "http": 10478,
        "ws": 10479,
    },
    "opencli_weixin": {
        "api": 10485,
        "mcp": 10486,
        "sse": 10487,
        "http": 10488,
        "ws": 10489,
    },
    "kuaishou": {"api": 10480, "mcp": 10481, "sse": 10482, "http": 10483, "ws": 10484},
    "douyin_viewer": {
        "api": 10620,
        "mcp": 10621,
        "sse": 10622,
        "http": 10623,
        "ws": 10624,
    },
    "youtube_viewer": {
        "api": 10495,
        "mcp": 10496,
        "sse": 10497,
        "http": 10498,
        "ws": 10499,
    },
    # NEW: Situation Monitor servers (105xx)
    "alerts": {"api": 10570, "mcp": 10571, "sse": 10572, "http": 10573, "ws": 10574},
    "economic": {"api": 10550, "mcp": 10551, "sse": 10552, "http": 10553, "ws": 10554},
    # web automation (105xx)
    "web_automation": {
        "api": 10560,
        "mcp": 10561,
        "sse": 10562,
        "http": 10563,
        "ws": 10564,
    },
    "agent_orchestrator": {
        "api": 10590,
        "mcp": 10591,
        "sse": 10592,
        "http": 10593,
        "ws": 10594,
    },
    # rag services (40xxx) - submodule=4, backend=0
    "rag": {"api": 40000, "mcp": 40001, "sse": 40002, "http": 40003, "ws": 40004},
    # stock services (50xxx) - submodule=5, backend=0
    "stock": {"api": 50000, "mcp": 50001, "sse": 50002, "http": 50003, "ws": 50004},
}

# 导出配置
SERVICE_PORTS: Dict[str, Dict[str, int]] = _get_service_ports()
PROTOCOL_OFFSETS: Dict[str, int] = _get_protocol_offsets()
SERVICE_ALIASES: Dict[str, Tuple[str, str]] = _get_service_aliases()
INFRASTRUCTURE_PORTS: Dict[str, Dict] = _get_infrastructure_ports()


def get_port(service_name: str, protocol: str = "api") -> int:
    """
    Get port for a service/protocol combination.

    Uses merged catalog (static service_ports.json + runtime overlay).
    """
    if f"{service_name}_{protocol}" in SERVICE_ALIASES:
        actual_service, actual_protocol = SERVICE_ALIASES[f"{service_name}_{protocol}"]
        service_name, protocol = actual_service, actual_protocol
    try:
        from core.service_registry_catalog import get_catalog

        return get_catalog().get_port(service_name, protocol)
    except Exception:
        if service_name not in SERVICE_PORTS:
            raise KeyError(f"Service '{service_name}' not found in port configuration")
        if protocol not in SERVICE_PORTS[service_name]:
            raise KeyError(f"Protocol '{protocol}' not found for service '{service_name}'")
        return SERVICE_PORTS[service_name][protocol]


def get_all_ports() -> Dict[str, Dict[str, int]]:
    """Get all configured ports"""
    return SERVICE_PORTS


def get_service_list() -> List[str]:
    """Get list of all configured services"""
    return list(SERVICE_PORTS.keys())


def get_service_info(service_name: str) -> Optional[Dict]:
    """获取服务详细信息，包括描述、端口、schema_ref（含 runtime 注册）"""
    try:
        from core.service_registry_catalog import get_catalog

        return get_catalog().get_service(service_name)
    except Exception:
        if _port_config and "services" in _port_config:
            return _port_config["services"].get(service_name)
        return None


def register_runtime_service(**kwargs):
    """Register a service into runtime overlay (persisted). See service_registry_catalog."""
    from core.service_registry_catalog import get_catalog

    return get_catalog().register_service(**kwargs)


def resolve_service_by_port(port: int):
    """Reverse lookup: port -> service bindings."""
    from core.service_registry_catalog import get_catalog

    return get_catalog().resolve_by_port(port)


def get_infrastructure_port(service: str, protocol: str = "port") -> int:
    """获取基础设施服务端口"""
    if service in INFRASTRUCTURE_PORTS:
        return INFRASTRUCTURE_PORTS[service].get(protocol, 0)
    raise KeyError(f"Infrastructure service '{service}' not found")


def validate_port(port: int, service_name: str, protocol: str) -> bool:
    """
    Validate if a port matches the expected configuration.

    Args:
        port: Port to validate
        service_name: Service name
        protocol: Protocol

    Returns:
        True if port matches configuration, False otherwise
    """
    try:
        expected_port = get_port(service_name, protocol)
        return port == expected_port
    except KeyError:
        return False


def get_service_url(service_name: str, protocol: str = "http") -> str:
    """
    Get validated service URL based on service name and protocol.

    Args:
        service_name: Name of the service
        protocol: Protocol type ("http", "mcp", "sse", "ws", "api")

    Returns:
        Service URL string
    """
    # Normalize protocol
    protocol = protocol.lower()
    if protocol == "api":
        protocol = "api"

    try:
        port = get_port(service_name, protocol)
        return f"http://localhost:{port}"
    except KeyError:
        # Fallback to hash-based port as defined in ServiceManager
        base = 10500
        offset = abs(hash(f"{service_name}_{protocol}")) % 100
        port = base + offset
        return f"http://localhost:{port}"


def parse_service_alias(alias: str) -> Tuple[str, str]:
    """
    Parse service alias into (service_name, protocol).
    """
    # Check if it's a known alias
    if alias in SERVICE_ALIASES:
        return SERVICE_ALIASES[alias]

    # Try to parse from alias format: {service}_{protocol}
    for protocol in PROTOCOL_OFFSETS.keys():
        if alias.endswith(f"_{protocol}"):
            service_name = alias[: -len(protocol) - 1]
            return (service_name, protocol)

    # Default: assume it's a service name with api protocol
    return (alias, "api")


def resolve_legacy_port(old_port: int) -> Tuple[str, str]:
    """Resolve legacy ports to new service and protocol."""
    legacy_mapping = {
        10370: ("stock_market", "http"),
        10360: ("stock_fundflow", "http"),
        10380: ("stock_sentiment", "http"),
    }
    return legacy_mapping.get(old_port, ("stock_market", "http"))


def get_port_rules() -> Dict:
    """获取端口分配规则"""
    if _port_config and "port_allocation_rules" in _port_config:
        return _port_config["port_allocation_rules"]
    return {}


def get_submodule_ranges() -> Dict:
    """获取子模块端口范围"""
    if _port_config and "submodule_port_ranges" in _port_config:
        return _port_config["submodule_port_ranges"]
    return {}


if __name__ == "__main__":
    # Test the configuration
    print("=" * 60)
    print("Service Port Configuration Test")
    print("=" * 60)
    print(f"Config file: {_config_file}")
    print(f"Config loaded: {bool(_port_config)}")
    print()

    # Print port allocation rules
    rules = get_port_rules()
    if rules:
        print("Port Allocation Rules:")
        print(f"  Base port: {rules.get('base_port')}")
        print(f"  Max port: {rules.get('max_port')}")
        print(f"  Ports per service: {rules.get('ports_per_service')}")
        print(f"  Formula: {rules.get('formula')}")
        print()

    # Print submodule ranges
    ranges = get_submodule_ranges()
    if ranges:
        print("Submodule Port Ranges:")
        for key, value in ranges.items():
            if isinstance(value, dict):
                print(f"  {key}: {value.get('submodule', 'N/A')}")
                for range_name, range_val in value.get("ranges", {}).items():
                    print(f"    - {range_name}: {range_val}")
            else:
                print(f"  {key}: {value}")
        print()

    # Test specific ports
    test_cases = [
        ("wechat", "api"),
        ("wechat", "mcp"),
        ("ai", "api"),
        ("ai", "mcp"),
        ("fundflow", "api"),
        ("market", "mcp"),
    ]

    print("Port Lookup:")
    for service, protocol in test_cases:
        try:
            port = get_port(service, protocol)
            print(f"  {service}_{protocol}: {port}")
        except KeyError as e:
            print(f"  {service}_{protocol}: ERROR - {e}")

    print("\nAlias Parsing:")
    test_aliases = ["wechat_api", "wechat_mcp", "ai", "fundflow_mcp"]
    for alias in test_aliases:
        result = parse_service_alias(alias)
        print(f"  {alias} -> {result}")

    print("\nAll Services:")
    for service in get_service_list():
        ports = SERVICE_PORTS[service]
        print(f"  {service}: {ports}")
