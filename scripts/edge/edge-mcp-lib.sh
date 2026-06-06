#!/usr/bin/env bash
# Shared helpers for Edge-local MCP API servers (xiaohongshu, wx_cli, opencli_weixin, wechat_viewer).
set -euo pipefail

edge_mcp_clear_proxy() {
  unset ALL_PROXY all_proxy HTTP_PROXY http_proxy HTTPS_PROXY https_proxy
}

edge_mcp_service_port() {
  local service="$1"
  case "${service}" in
    xiaohongshu) echo 10350 ;;
    wx_cli) echo 10475 ;;
    wechat_viewer) echo 10470 ;;
    opencli_weixin) echo 10485 ;;
    *) echo "ERROR: unknown edge MCP service: ${service}" >&2; return 1 ;;
  esac
}

edge_mcp_service_dir() {
  local repo_root="$1"
  local service="$2"
  echo "${repo_root}/servers/${service}"
}

edge_mcp_service_python() {
  local repo_root="$1"
  local service="$2"
  case "${service}" in
    xiaohongshu)
      echo "${repo_root}/servers/xiaohongshu/.mcp_venv/bin/python3.12"
      ;;
    wechat_viewer)
      echo "${repo_root}/servers/wechat_viewer/.mcp_venv/bin/python3.12"
      ;;
    wx_cli | opencli_weixin)
      echo "${repo_root}/.venv/bin/python"
      ;;
    *)
      echo "ERROR: unknown edge MCP service: ${service}" >&2
      return 1
      ;;
  esac
}

edge_mcp_ensure_xhs_deps() {
  local repo_root="$1"
  local xhs_py="$2"
  local xhs_dir
  xhs_dir="$(edge_mcp_service_dir "${repo_root}" xiaohongshu)"
  if ! ( cd "${xhs_dir}" && "${xhs_py}" -c "from source import XHS" ) 2>/dev/null; then
    echo "==> Installing xiaohongshu MCP dependencies (browser-cookie3 fallback)"
    uv pip install fastapi fastmcp 'httpx[socks]' socksio httpcore lxml aiofiles aiosqlite sqlalchemy pymysql \
      pyyaml emoji click flask-cors flask-restful flask-sqlalchemy uvicorn websockets browser-cookie3 rich pyperclip \
      --python "${xhs_py}" >/dev/null
  fi
  if ! ( cd "${xhs_dir}" && "${xhs_py}" -c "from source import XHS" ) 2>/dev/null; then
    echo "ERROR: xiaohongshu XHS downloader unavailable after dep install" >&2
    ( cd "${xhs_dir}" && "${xhs_py}" -c "from source import XHS" ) 2>&1 | tail -5 >&2 || true
    return 1
  fi
}

edge_mcp_pythonpath() {
  local repo_root="$1"
  echo "${repo_root}/runtime-core:${repo_root}/servers"
}

edge_mcp_ensure_wx_deps() {
  local repo_root="$1"
  local py="$2"
  local dir
  dir="$(edge_mcp_service_dir "${repo_root}" wx_cli)"
  (
    cd "${dir}"
    export PYTHONPATH="$(edge_mcp_pythonpath "${repo_root}"):${PYTHONPATH:-}"
    "${py}" -c "from handlers.tool_handler import WxCliToolHandler; WxCliToolHandler()"
  ) >/dev/null
}

edge_mcp_ensure_opencli_weixin_deps() {
  local repo_root="$1"
  local py="$2"
  local dir
  dir="$(edge_mcp_service_dir "${repo_root}" opencli_weixin)"
  (
    cd "${dir}"
    export PYTHONPATH="$(edge_mcp_pythonpath "${repo_root}"):${PYTHONPATH:-}"
    "${py}" -c "from handlers.tool_handler import OpenCLIWeixinToolHandler; OpenCLIWeixinToolHandler()"
  ) >/dev/null
}

edge_mcp_ensure_wechat_viewer_deps() {
  local repo_root="$1"
  local py="$2"
  local dir req_file backend
  dir="$(edge_mcp_service_dir "${repo_root}" wechat_viewer)"
  backend="$(echo "${WECHAT_VIEWER_BACKEND:-opencli}" | tr '[:upper:]' '[:lower:]')"
  if [[ "${backend}" == "legacy" ]]; then
    req_file="${dir}/requirements-legacy.txt"
  else
    req_file="${dir}/requirements-opencli.txt"
  fi
  if [[ -f "${req_file}" ]] && command -v uv >/dev/null 2>&1; then
    if ! "${py}" -c "import flask, httpx" 2>/dev/null; then
      echo "==> Installing wechat_viewer deps (${req_file##*/})"
      uv pip install -r "${req_file}" --python "${py}" >/dev/null
    fi
  fi
  (
    cd "${dir}"
    export PYTHONPATH="$(edge_mcp_pythonpath "${repo_root}"):${dir}:${PYTHONPATH:-}"
    export WECHAT_VIEWER_BACKEND="${WECHAT_VIEWER_BACKEND:-opencli}"
    "${py}" -c "from api_server import WeChatViewerAPIServer; WeChatViewerAPIServer()"
  )
}

edge_mcp_ensure_deps() {
  local repo_root="$1"
  local service="$2"
  local py
  py="$(edge_mcp_service_python "${repo_root}" "${service}")"
  case "${service}" in
    xiaohongshu) edge_mcp_ensure_xhs_deps "${repo_root}" "${py}" ;;
    wx_cli) edge_mcp_ensure_wx_deps "${repo_root}" "${py}" ;;
    opencli_weixin) edge_mcp_ensure_opencli_weixin_deps "${repo_root}" "${py}" ;;
    wechat_viewer) edge_mcp_ensure_wechat_viewer_deps "${repo_root}" "${py}" ;;
    *) echo "ERROR: unknown edge MCP service: ${service}" >&2; return 1 ;;
  esac
}

edge_mcp_service_env() {
  local repo_root="$1"
  local service="$2"
  export PYTHONPATH="$(edge_mcp_pythonpath "${repo_root}"):${PYTHONPATH:-}"
  case "${service}" in
    wechat_viewer)
      export WECHAT_VIEWER_BACKEND="${WECHAT_VIEWER_BACKEND:-opencli}"
      ;;
  esac
  edge_mcp_clear_proxy
}
