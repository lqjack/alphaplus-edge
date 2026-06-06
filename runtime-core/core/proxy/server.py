import asyncio
import os
import logging
from mitmproxy import options
from mitmproxy.tools.dump import DumpMaster
from mitmproxy import tls
from core.tools.addons import WeiXinProxy

from core.settings import PROXY_LISTEN_HOST, PROXY_PORT, PROXY_ALLOW_HOSTS

logger = logging.getLogger(__name__)


class MinTls:
    def __init__(self):
        from core.tools.files import get_main_root

        path = os.path.join(get_main_root(), "logs", "proxy", "instance.log")
        if not os.path.exists(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))
        logging.basicConfig(
            level=logging.WARN,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[logging.FileHandler(path), logging.StreamHandler()],
        )

    def tls_start_client(self, data: tls.TlsData) -> None:
        if data.ssl_conn:
            logging.info(
                f"Client TLS handshake started with version: {data.ssl_conn.get_protocol_version_name()}"
            )

    def tls_start_server(self, data: tls.TlsData) -> None:
        if data.ssl_conn:
            logging.info(
                f"Server TLS handshake started with version: {data.ssl_conn.get_protocol_version_name()}"
            )

    def tls_error(self, data: tls.TlsData) -> None:
        if data.ssl_conn:
            logging.error(f"TLS error: {data.ssl_conn.get_error()}")

    def load(self, loader) -> None:
        loader.add_option(
            name="tls_version_client_min",
            typespec=str,
            default="TLS1_2",
            help="Set the minimum TLS version for clients",
        )
        loader.add_option(
            name="tls_version_server_min",
            typespec=str,
            default="TLS1_2",
            help="Set the minimum TLS version for servers",
        )

        loader.add_option(
            name="confdir",
            typespec=str,
            default=get_ca_path(),
            help="Path to the directory containing CA certificates",
        )


class ErrorLogLevel:
    def load(self, loader) -> None:
        loader.add_option(
            name="console_eventlog_verbosity",
            typespec=str,
            default="error",
            help="Set log level",
        )


from core.tools.article_content_check import run_with_app


class PerformanceOptimizer:
    """Optimize proxy performance by reducing unnecessary processing"""

    def load(self, loader) -> None:
        # Set performance-focused options
        loader.add_option(
            name="stream_large_bodies",
            typespec=int,
            default=1024 * 1024,  # 1MB threshold for streaming
            help="Stream large response bodies to reduce memory usage",
        )
        loader.add_option(
            name="keep_host_header",
            typespec=bool,
            default=True,
            help="Preserve original Host header to avoid DNS lookups",
        )
        loader.add_option(
            name="http2",
            typespec=bool,
            default=True,
            help="Enable HTTP/2 for better performance",
        )


@run_with_app
async def run_mitmproxy():
    try:
        proxy_http2_enabled = os.getenv("PROXY_ENABLE_HTTP2", "false").lower() == "true"
        opts = options.Options(
            listen_host=PROXY_LISTEN_HOST,
            listen_port=int(PROXY_PORT) if PROXY_PORT else 10500,
            confdir=get_ca_path(),
            allow_hosts=PROXY_ALLOW_HOSTS,
            # Performance optimizations
            # stream_large_bodies=1024 * 1024,
            # keep_host_header=True,
            http2=proxy_http2_enabled,
        )

        master = DumpMaster(opts, with_dumper=False, with_termlog=False)
        min_tls, weixin_addon = MinTls(), WeiXinProxy()
        performance_optimizer = PerformanceOptimizer()
        master.addons.add(min_tls)
        master.addons.add(weixin_addon)
        # master.addons.add(performance_optimizer)
        master.addons.add(ErrorLogLevel())
        await master.run()
    except Exception as e:
        logger.error(f"Error running mitmproxy: {e}")
        raise e


def start_proxy():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_mitmproxy())
    loop.close()


@staticmethod
def get_ca_path():
    from core.tools.files import get_project_root
    from core.settings import CUSTOM_CA_PATH

    CA_PATH = os.path.join(get_project_root(), CUSTOM_CA_PATH)
    return CA_PATH


if __name__ == "__main__":
    start_proxy()
