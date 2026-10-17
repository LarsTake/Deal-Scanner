use serde::{Deserialize, Serialize};
use std::{
    collections::BTreeMap,
    fs,
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::Mutex,
};
use tauri::{Manager, State, WebviewWindow};

#[derive(Default)]
pub struct LocalWorker(pub Mutex<Option<Child>>);

impl LocalWorker {
    pub fn shutdown(&self) {
        if let Ok(mut process) = self.0.lock() {
            if let Some(mut child) = process.take() {
                let _ = child.kill();
                let _ = child.wait();
            }
        }
    }
}

#[derive(Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", default)]
pub struct WorkerConfig {
    pub server_url: String,
    pub executable: String,
    pub supabase_url: String,
    pub publishable_key: String,
    pub email: String,
    pub text_model: String,
    pub vision_model: String,
    pub images: bool,
    pub password_file: String,
}

impl Default for WorkerConfig {
    fn default() -> Self {
        Self {
            server_url: "http://192.168.178.169:8088".into(),
            executable: String::new(),
            supabase_url: String::new(),
            publishable_key: String::new(),
            email: String::new(),
            text_model: String::new(),
            vision_model: String::new(),
            images: false,
            password_file: String::new(),
        }
    }
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WorkerStatus {
    running: bool,
    legacy_service: bool,
    password_saved: bool,
    config: WorkerConfig,
}

fn local_only(window: &WebviewWindow) -> Result<(), String> {
    let url = window.url().map_err(|_| "Fensteradresse nicht verfügbar")?;
    let trusted = window.label() == "main"
        && (url.scheme() == "tauri" && url.host_str() == Some("localhost")
            || url.scheme() == "http" && url.host_str() == Some("tauri.localhost")
            || url.scheme() == "http"
                && url.host_str() == Some("127.0.0.1")
                && url.port() == Some(4200));
    if trusted {
        Ok(())
    } else {
        Err("Nur die lokale Desktop-Oberfläche darf den Worker steuern.".into())
    }
}

fn data_dir(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    let path = app
        .path()
        .app_local_data_dir()
        .map_err(|_| "App-Verzeichnis nicht verfügbar")?
        .join("local-worker");
    fs::create_dir_all(&path).map_err(|_| "App-Verzeichnis konnte nicht erstellt werden")?;
    Ok(path)
}

pub fn server_url(value: &str) -> Result<url::Url, String> {
    let parsed = url::Url::parse(value).map_err(|_| "Ungültige Serveradresse")?;
    let local = parsed
        .host_str()
        .map(|host| {
            host == "localhost"
                || host.ends_with(".local")
                || host.ends_with(".fritz.box")
                || host
                    .parse::<std::net::Ipv4Addr>()
                    .map(|ip| ip.is_private() || ip.is_loopback())
                    .unwrap_or(false)
        })
        .unwrap_or(false);
    if (parsed.scheme() != "https" && !(parsed.scheme() == "http" && local))
        || parsed.host_str().is_none()
        || !parsed.username().is_empty()
        || parsed.password().is_some()
        || parsed.query().is_some()
        || parsed.fragment().is_some()
    {
        return Err("HTTPS verwenden; HTTP ist nur für lokale/Heimnetz-Adressen erlaubt. Keine Zugangsdaten in der URL.".into());
    }
    Ok(parsed)
}

fn load(app: &tauri::AppHandle) -> Result<WorkerConfig, String> {
    let path = data_dir(app)?.join("config.json");
    if path.exists() {
        return serde_json::from_slice(&fs::read(path).map_err(|_| "Konfiguration nicht lesbar")?)
            .map_err(|_| "Konfiguration ungültig".into());
    }
    let mut config = WorkerConfig::default();
    #[cfg(target_os = "macos")]
    if let Ok(home) = app.path().home_dir() {
        let path = home.join("Library/LaunchAgents/de.deal-scanner.text-worker.plist");
        if path.exists() {
            if let Ok(output) = Command::new("/usr/bin/plutil")
                .args(["-convert", "json", "-o", "-"])
                .arg(path)
                .output()
            {
                if let Ok(value) = serde_json::from_slice::<serde_json::Value>(&output.stdout) {
                    let get = |key: &str| {
                        value["EnvironmentVariables"][key]
                            .as_str()
                            .unwrap_or("")
                            .to_owned()
                    };
                    config.server_url = get("DEAL_SCANNER_API_URL");
                    config.executable = value["ProgramArguments"][0]
                        .as_str()
                        .unwrap_or("")
                        .to_owned();
                    config.supabase_url = get("DEAL_SCANNER_SUPABASE_URL");
                    config.publishable_key = get("DEAL_SCANNER_SUPABASE_PUBLISHABLE_KEY");
                    config.email = get("DEAL_SCANNER_SERVICE_EMAIL");
                    config.text_model = get("DEAL_SCANNER_OLLAMA_EXTRACTION_MODEL");
                    config.password_file = get("DEAL_SCANNER_SERVICE_PASSWORD_FILE");
                }
            }
        }
    }
    Ok(config)
}

#[cfg(target_os = "macos")]
fn legacy_target() -> String {
    let uid = Command::new("/usr/bin/id")
        .arg("-u")
        .output()
        .ok()
        .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_owned())
        .unwrap_or_default();
    format!("gui/{uid}/de.deal-scanner.text-worker")
}

fn legacy_running() -> bool {
    #[cfg(target_os = "macos")]
    {
        Command::new("/bin/launchctl")
            .args(["print", &legacy_target()])
            .output()
            .map(|o| o.status.success())
            .unwrap_or(false)
    }
    #[cfg(not(target_os = "macos"))]
    {
        false
    }
}

#[tauri::command]
pub fn local_worker_status(
    window: WebviewWindow,
    state: State<'_, LocalWorker>,
) -> Result<WorkerStatus, String> {
    local_only(&window)?;
    let mut child = state.0.lock().map_err(|_| "Worker gesperrt")?;
    let running = child
        .as_mut()
        .map(|c| c.try_wait().map(|exit| exit.is_none()).unwrap_or(false))
        .unwrap_or(false);
    let legacy = legacy_running();
    let config = load(window.app_handle())?;
    Ok(WorkerStatus {
        running: running || legacy,
        legacy_service: legacy,
        password_saved: !config.password_file.is_empty()
            && PathBuf::from(&config.password_file).is_file(),
        config,
    })
}

#[tauri::command]
pub async fn select_worker_executable(window: WebviewWindow) -> Result<Option<String>, String> {
    local_only(&window)?;
    Ok(rfd::AsyncFileDialog::new()
        .set_title("deal-scanner-worker aus der Python-Installation wählen")
        .pick_file()
        .await
        .map(|p| p.path().to_string_lossy().into_owned()))
}

#[tauri::command]
pub fn save_local_worker(
    window: WebviewWindow,
    mut config: WorkerConfig,
    password: String,
) -> Result<(), String> {
    local_only(&window)?;
    server_url(&config.server_url)?;
    let dir = data_dir(window.app_handle())?;
    // Never accept a password-file path supplied by web content.
    config.password_file = load(window.app_handle())?.password_file;
    if !password.is_empty() {
        let path = dir.join("password");
        #[cfg(unix)]
        {
            use std::io::Write;
            use std::os::unix::fs::OpenOptionsExt;
            let mut file = fs::OpenOptions::new()
                .write(true)
                .create(true)
                .truncate(true)
                .mode(0o600)
                .open(&path)
                .map_err(|_| "Passwortdatei nicht schreibbar")?;
            file.write_all(password.as_bytes())
                .map_err(|_| "Passwort konnte nicht gespeichert werden")?;
        }
        #[cfg(windows)]
        {
            fs::write(&path, "").map_err(|_| "Passwortdatei nicht schreibbar")?;
            let user = std::env::var("USERNAME").map_err(|_| "Benutzer nicht verfügbar")?;
            let ok = Command::new("icacls")
                .arg(&path)
                .args(["/inheritance:r", "/grant:r", &format!("{user}:F")])
                .output()
                .map(|o| o.status.success())
                .unwrap_or(false);
            if !ok {
                let _ = fs::remove_file(path);
                return Err("Passwortdatei konnte nicht abgesichert werden".into());
            }
            fs::write(&path, password.as_bytes())
                .map_err(|_| "Passwort konnte nicht gespeichert werden")?;
        }
        config.password_file = path.to_string_lossy().into_owned();
    }
    fs::write(
        dir.join("config.json"),
        serde_json::to_vec_pretty(&config).map_err(|_| "Konfiguration ungültig")?,
    )
    .map_err(|_| "Konfiguration nicht gespeichert".into())
}

pub fn worker_env(config: &WorkerConfig) -> BTreeMap<&'static str, String> {
    BTreeMap::from([
        ("DEAL_SCANNER_ENVIRONMENT", "production".into()),
        ("DEAL_SCANNER_API_URL", config.server_url.clone()),
        ("DEAL_SCANNER_SERVICE_AUTH_MODE", "supabase".into()),
        ("DEAL_SCANNER_SERVICE_EMAIL", config.email.clone()),
        (
            "DEAL_SCANNER_SERVICE_PASSWORD_FILE",
            config.password_file.clone(),
        ),
        ("DEAL_SCANNER_SUPABASE_URL", config.supabase_url.clone()),
        (
            "DEAL_SCANNER_SUPABASE_PUBLISHABLE_KEY",
            config.publishable_key.clone(),
        ),
        ("DEAL_SCANNER_API_TOKEN", "".into()),
        ("DEAL_SCANNER_DEVELOPMENT_USER_ID", "".into()),
        ("DEAL_SCANNER_WORKER_MODE", "ai".into()),
        ("DEAL_SCANNER_WORKER_NAME", "Desktop-KI".into()),
        ("DEAL_SCANNER_OLLAMA_URL", "http://127.0.0.1:11434".into()),
        (
            "DEAL_SCANNER_OLLAMA_EXTRACTION_MODEL",
            config.text_model.clone(),
        ),
        ("DEAL_SCANNER_OLLAMA_TEXT_MODEL", "".into()),
        ("DEAL_SCANNER_OLLAMA_REASONING_MODEL", "".into()),
        ("DEAL_SCANNER_OLLAMA_EMBEDDING_MODEL", "".into()),
        (
            "DEAL_SCANNER_OLLAMA_VISION_MODEL",
            if config.images {
                config.vision_model.clone()
            } else {
                "".into()
            },
        ),
        ("DEAL_SCANNER_TESSERACT_COMMAND", "disabled".into()),
    ])
}

#[tauri::command]
pub fn start_local_worker(
    window: WebviewWindow,
    state: State<'_, LocalWorker>,
) -> Result<(), String> {
    local_only(&window)?;
    if legacy_running() {
        return Err("Der bisherige Mac-Dienst ist aktiv. Zuerst über Stopp deaktivieren, dann mit den App-Einstellungen starten.".into());
    }
    let mut child = state.0.lock().map_err(|_| "Worker gesperrt")?;
    if child
        .as_mut()
        .map(|c| c.try_wait().ok() == Some(None))
        .unwrap_or(false)
    {
        return Ok(());
    }
    let config = load(window.app_handle())?;
    server_url(&config.server_url)?;
    if config.email.is_empty()
        || config.supabase_url.is_empty()
        || config.publishable_key.is_empty()
        || config.text_model.is_empty()
        || !PathBuf::from(&config.password_file).is_file()
        || (config.images && config.vision_model.is_empty())
    {
        return Err("Anmeldung, Passwortdatei und Modellzuordnung vervollständigen.".into());
    }
    let exe = PathBuf::from(&config.executable);
    if !exe.is_absolute()
        || !exe.is_file()
        || !matches!(
            exe.file_name().and_then(|n| n.to_str()),
            Some("deal-scanner-worker" | "deal-scanner-worker.exe")
        )
    {
        return Err("Installierte deal-scanner-worker Programmdatei auswählen.".into());
    }
    let dir = data_dir(window.app_handle())?;
    let log = fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(dir.join("worker.log"))
        .map_err(|_| "Logdatei nicht schreibbar")?;
    let mut command = Command::new(exe);
    command
        .current_dir(dir)
        .envs(worker_env(&config))
        .stdin(Stdio::null())
        .stdout(log.try_clone().map_err(|_| "Logdatei nicht verfügbar")?)
        .stderr(log);
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000);
    }
    *child = Some(
        command
            .spawn()
            .map_err(|_| "Worker konnte nicht gestartet werden")?,
    );
    Ok(())
}

#[tauri::command]
pub fn stop_local_worker(
    window: WebviewWindow,
    state: State<'_, LocalWorker>,
) -> Result<(), String> {
    local_only(&window)?;
    if let Some(mut child) = state.0.lock().map_err(|_| "Worker gesperrt")?.take() {
        let _ = child.kill();
        let _ = child.wait();
    }
    #[cfg(target_os = "macos")]
    if legacy_running() {
        let target = legacy_target();
        let disabled = Command::new("/bin/launchctl")
            .args(["disable", &target])
            .status()
            .map_err(|_| "Autostart konnte nicht deaktiviert werden")?;
        if !disabled.success() {
            return Err("Mac-Autostart konnte nicht deaktiviert werden".into());
        }
        let stopped = Command::new("/bin/launchctl")
            .args(["bootout", &target])
            .status()
            .map_err(|_| "Mac-Dienst konnte nicht gestoppt werden")?;
        if !stopped.success() {
            return Err("Mac-Dienst konnte nicht gestoppt werden".into());
        }
    }
    Ok(())
}

#[tauri::command]
pub async fn open_server_dashboard(window: WebviewWindow, address: String) -> Result<(), String> {
    local_only(&window)?;
    let url = server_url(&address)?;
    // Keep the server entirely outside Tauri: older frontends detect its global
    // IPC object even without capabilities and fail while bootstrapping SQL.
    #[cfg(target_os = "macos")]
    let mut command = Command::new("/usr/bin/open");
    #[cfg(windows)]
    let mut command = {
        let mut command = Command::new("rundll32.exe");
        command.arg("url.dll,FileProtocolHandler");
        command
    };
    #[cfg(not(any(target_os = "macos", windows)))]
    let mut command = Command::new("xdg-open");
    let result = command
        .arg(url.as_str())
        .status()
        .map_err(|_| "Browser konnte nicht geöffnet werden")?;
    if result.success() {
        Ok(())
    } else {
        Err("Browser konnte nicht geöffnet werden".into())
    }
}

impl Drop for LocalWorker {
    fn drop(&mut self) {
        if let Ok(child) = self.0.get_mut() {
            if let Some(mut worker) = child.take() {
                let _ = worker.kill();
                let _ = worker.wait();
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn limits_remote_urls() {
        for value in [
            "file:///etc/passwd",
            "javascript:alert(1)",
            "http://example.com",
            "https://user:pw@example.com",
            "https://example.com/?token=1",
        ] {
            assert!(server_url(value).is_err());
        }
        assert!(server_url("http://192.168.178.169:8088").is_ok());
        assert!(server_url("https://scanner.example.com").is_ok());
    }
    #[test]
    fn text_mode_never_claims_images_or_extra_models() {
        let config = WorkerConfig {
            vision_model: "vision-model".into(),
            ..Default::default()
        };
        let env = worker_env(&config);
        assert_eq!(env["DEAL_SCANNER_OLLAMA_VISION_MODEL"], "");
        assert_eq!(env["DEAL_SCANNER_TESSERACT_COMMAND"], "disabled");
        assert_eq!(env["DEAL_SCANNER_OLLAMA_REASONING_MODEL"], "");
    }

    #[test]
    fn image_mode_passes_only_the_selected_vision_model() {
        let config = WorkerConfig {
            images: true,
            vision_model: "installed-vision-model".into(),
            ..Default::default()
        };
        assert_eq!(
            worker_env(&config)["DEAL_SCANNER_OLLAMA_VISION_MODEL"],
            "installed-vision-model"
        );
    }

    #[cfg(unix)]
    #[test]
    fn shutdown_reaps_the_owned_process() {
        let child = Command::new("/bin/sleep").arg("30").spawn().unwrap();
        let worker = LocalWorker(Mutex::new(Some(child)));
        worker.shutdown();
        assert!(worker.0.lock().unwrap().is_none());
        worker.shutdown();
    }
}
