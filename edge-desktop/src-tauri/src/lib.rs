use std::path::PathBuf;
use std::process::Stdio;
use std::sync::Mutex;

use serde::{Deserialize, Serialize};
use tauri::State;
use tokio::process::{Child, Command};

#[derive(Default)]
struct EdgeRuntime {
    health: Mutex<Option<Child>>,
    tunnel: Mutex<Option<Child>>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct EdgeConfig {
    gateway_url: String,
    public_url: Option<String>,
    edge_id: String,
    device_token: String,
    health_port: u16,
}

#[derive(Debug, Serialize)]
struct EdgeStatus {
    running: bool,
    health_pid: Option<u32>,
    tunnel_pid: Option<u32>,
}

fn installed_runtime_root() -> Option<PathBuf> {
    let home = std::env::var_os("HOME")?;
    let root = PathBuf::from(home).join("Library/Application Support/AlphaPlus-Edge/runtime");
    let marker = root.join("scripts/edge/edge_health_server.py");
    if marker.is_file() {
        Some(root)
    } else {
        None
    }
}

fn repo_root() -> PathBuf {
    if let Ok(root) = std::env::var("ALPHAPLUS_REPO_ROOT") {
        return PathBuf::from(root);
    }
    if let Some(root) = installed_runtime_root() {
        return root;
    }
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .unwrap_or_else(|_| PathBuf::from("."))
}

fn python_bin() -> String {
    std::env::var("EDGE_PYTHON_BIN").unwrap_or_else(|_| "python3".to_string())
}

async fn spawn_python(script: &str, envs: &[(String, String)]) -> Result<Child, String> {
    let root = repo_root();
    let script_path = root.join(script);
    if !script_path.exists() {
        return Err(format!("script not found: {}", script_path.display()));
    }

    let mut command = Command::new(python_bin());
    command
        .arg(script_path)
        .current_dir(&root)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .kill_on_drop(true);

    command.env(
        "PYTHONPATH",
        root.join("dataproai/src").to_string_lossy().to_string(),
    );
    for (key, value) in envs {
        command.env(key, value);
    }

    command
        .spawn()
        .map_err(|err| format!("failed to spawn {script}: {err}"))
}

#[tauri::command]
async fn edge_stack_status(runtime: State<'_, EdgeRuntime>) -> Result<EdgeStatus, String> {
    let health_pid = runtime
        .health
        .lock()
        .map_err(|_| "lock poisoned".to_string())?
        .as_ref()
        .map(|child| child.id().unwrap_or(0));
    let tunnel_pid = runtime
        .tunnel
        .lock()
        .map_err(|_| "lock poisoned".to_string())?
        .as_ref()
        .map(|child| child.id().unwrap_or(0));
    Ok(EdgeStatus {
        running: health_pid.is_some() || tunnel_pid.is_some(),
        health_pid,
        tunnel_pid,
    })
}

#[tauri::command]
async fn start_edge_stack(
    runtime: State<'_, EdgeRuntime>,
    config: EdgeConfig,
) -> Result<EdgeStatus, String> {
    let callback = format!("http://127.0.0.1:{}", config.health_port);
    let health_env = vec![
        ("EDGE_HEALTH_PORT".to_string(), config.health_port.to_string()),
        ("EDGE_ID".to_string(), config.edge_id.clone()),
    ];

    let needs_health = runtime
        .health
        .lock()
        .map_err(|_| "lock poisoned".to_string())?
        .is_none();
    if needs_health {
        let child = spawn_python("scripts/edge/edge_health_server.py", &health_env).await?;
        *runtime
            .health
            .lock()
            .map_err(|_| "lock poisoned".to_string())? = Some(child);
    }

    let mut tunnel_env = vec![
        ("GATEWAY_URL".to_string(), config.gateway_url.clone()),
        ("EDGE_ID".to_string(), config.edge_id.clone()),
        ("EDGE_DEVICE_TOKEN".to_string(), config.device_token.clone()),
        ("EDGE_CALLBACK_BASE_URL".to_string(), callback),
    ];
    if let Some(public_url) = config.public_url.filter(|value| !value.trim().is_empty()) {
        tunnel_env.push(("GATEWAY_PUBLIC_URL".to_string(), public_url));
    }

    let needs_tunnel = runtime
        .tunnel
        .lock()
        .map_err(|_| "lock poisoned".to_string())?
        .is_none();
    if needs_tunnel {
        let child = spawn_python("scripts/edge/edge_tunnel_client.py", &tunnel_env).await?;
        *runtime
            .tunnel
            .lock()
            .map_err(|_| "lock poisoned".to_string())? = Some(child);
    }

    edge_stack_status(runtime).await
}

#[tauri::command]
async fn stop_edge_stack(runtime: State<'_, EdgeRuntime>) -> Result<EdgeStatus, String> {
    let health_child = runtime
        .health
        .lock()
        .map_err(|_| "lock poisoned".to_string())?
        .take();
    if let Some(mut child) = health_child {
        let _ = child.kill().await;
    }

    let tunnel_child = runtime
        .tunnel
        .lock()
        .map_err(|_| "lock poisoned".to_string())?
        .take();
    if let Some(mut child) = tunnel_child {
        let _ = child.kill().await;
    }

    edge_stack_status(runtime).await
}

#[tauri::command]
async fn register_with_gateway(config: EdgeConfig) -> Result<serde_json::Value, String> {
    let callback = format!("http://127.0.0.1:{}", config.health_port);
    let payload = serde_json::json!({
        "edge_id": config.edge_id,
        "device_token": config.device_token,
        "callback_base_url": callback,
        "services": ["xiaohongshu", "wx_cli", "opencli_weixin", "wechat_viewer"],
        "capabilities": {"profile": "edge-user", "client": "tauri"}
    });

    let client = reqwest::Client::new();
    let response = client
        .post(format!("{}/api/edge/devices/register", config.gateway_url.trim_end_matches('/')))
        .json(&payload)
        .send()
        .await
        .map_err(|err| format!("register request failed: {err}"))?;

    let status = response.status();
    let body: serde_json::Value = response
        .json()
        .await
        .map_err(|err| format!("register response parse failed: {err}"))?;
    if !status.is_success() {
        return Err(format!("register failed: {body}"));
    }
    Ok(body)
}

#[tauri::command]
async fn rotate_device_token(config: EdgeConfig) -> Result<serde_json::Value, String> {
    let payload = serde_json::json!({
        "edge_id": config.edge_id,
        "device_token": config.device_token,
    });
    let client = reqwest::Client::new();
    let response = client
        .post(format!(
            "{}/api/edge/devices/rotate-token",
            config.gateway_url.trim_end_matches('/')
        ))
        .json(&payload)
        .send()
        .await
        .map_err(|err| format!("rotate request failed: {err}"))?;

    let status = response.status();
    let body: serde_json::Value = response
        .json()
        .await
        .map_err(|err| format!("rotate response parse failed: {err}"))?;
    if !status.is_success() {
        return Err(format!("rotate failed: {body}"));
    }
    Ok(body)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(EdgeRuntime::default())
        .invoke_handler(tauri::generate_handler![
            start_edge_stack,
            stop_edge_stack,
            edge_stack_status,
            register_with_gateway,
            rotate_device_token
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
