use std::fs;
use std::io::{Read, Write};
use std::net::TcpListener;
use std::os::windows::process::CommandExt;
use std::path::PathBuf;
use std::process::Command;
use std::thread;

use tauri::menu::{MenuBuilder, MenuItemBuilder};
use tauri::tray::TrayIconBuilder;
use tauri::Manager;

const AUTOSTART_KEY: &str = "AISignalLight";
const AUTOSTART_PATH: &str = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run";

const PRIORITY: &[( &str, u8)] = &[
    ("blocked", 4),
    ("waiting", 3),
    ("working", 2),
    ("idle", 1),
];

// ── State JSON helpers ──

fn utc_now_iso() -> String {
    let dur = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default();
    let total_secs = dur.as_secs() as i64;
    let days = total_secs / 86400;
    let time_secs = total_secs % 86400;

    // Howard Hinnant date algorithm
    let z = days + 719468;
    let era = (if z >= 0 { z } else { z - 146096 }) / 146097;
    let doe = (z - era * 146097) as u32;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let y = yoe as i64 + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if m <= 2 { y + 1 } else { y };

    let h = time_secs / 3600;
    let min = (time_secs % 3600) / 60;
    let s = time_secs % 60;

    format!("{:04}-{:02}-{:02}T{:02}:{:02}:{:02}Z", y, m, d, h, min, s)
}

fn read_state_doc() -> serde_json::Value {
    let path = state_dir().join("state.json");
    let data = fs::read_to_string(&path).unwrap_or_default();
    serde_json::from_str(&data).unwrap_or(serde_json::json!({"sources": {}}))
}

fn write_state_doc(doc: serde_json::Value) {
    let dir = state_dir();
    let _ = fs::create_dir_all(&dir);
    let tmp = dir.join("state.tmp");
    let payload = serde_json::to_string_pretty(&doc).unwrap_or_default();
    let _ = fs::write(&tmp, payload);
    let _ = fs::rename(&tmp, dir.join("state.json"));
}

fn calc_effective(sources: &serde_json::Value) -> (String, String) {
    let mut best: (&str, &str, u8, &str) = ("idle", "none", 0, "");
    let obj = sources.as_object();
    if obj.is_none() {
        return ("idle".into(), "none".into());
    }
    let mut has_active = false;
    for (src, entry) in obj.unwrap() {
        let state = entry.get("state").and_then(|v| v.as_str()).unwrap_or("idle");
        let updated = entry.get("updated_at").and_then(|v| v.as_str()).unwrap_or("");
        if state != "idle" {
            has_active = true;
        }
        let rank = PRIORITY.iter().find(|(s, _)| *s == state).map(|(_, r)| *r).unwrap_or(0);
        if rank > best.2 || (rank == best.2 && updated > best.3) {
            best = (state, src, rank, updated);
        }
    }
    if !has_active {
        return ("idle".into(), "none".into());
    }
    (best.0.into(), best.1.into())
}

fn direct_write_state(state: &str, source: &str) {
    let mut doc = read_state_doc();
    let now = utc_now_iso();

    if doc.get("sources").and_then(|v| v.as_object()).is_none() {
        doc["sources"] = serde_json::json!({});
    }
    doc["sources"][source] = serde_json::json!({"state": state, "updated_at": now});

    let (effective, src) = calc_effective(&doc["sources"]);
    doc["state"] = effective.into();
    doc["source"] = src.into();
    doc["updated_at"] = now.into();

    write_state_doc(doc);
}

fn direct_reset_all() {
    let mut doc = read_state_doc();
    let now = utc_now_iso();

    if doc.get("sources").and_then(|v| v.as_object()).is_none() {
        doc["sources"] = serde_json::json!({});
    }
    let keys: Vec<String> = doc["sources"].as_object().unwrap().keys().cloned().collect();
    for key in keys {
        doc["sources"][&key] = serde_json::json!({"state": "idle", "updated_at": now});
    }

    doc["state"] = "idle".into();
    doc["source"] = "none".into();
    doc["updated_at"] = now.into();

    write_state_doc(doc);
}

// ── HTTP Bridge ──

fn start_bridge_server() {
    thread::spawn(|| {
        if let Ok(listener) = TcpListener::bind("127.0.0.1:57422") {
            for stream in listener.incoming() {
                if let Ok(mut stream) = stream {
                    let mut buffer = [0; 4096];
                    if let Ok(size) = stream.read(&mut buffer) {
                        let request = String::from_utf8_lossy(&buffer[..size]);
                        if request.starts_with("POST /state") {
                            if let Some(body_idx) = request.find("\r\n\r\n") {
                                let body = &request[body_idx + 4..];
                                if let Ok(json) =
                                    serde_json::from_str::<serde_json::Value>(body)
                                {
                                    if let (Some(state), Some(source)) = (
                                        json.get("state").and_then(|v| v.as_str()),
                                        json.get("source").and_then(|v| v.as_str()),
                                    ) {
                                        direct_write_state(state, source);
                                    }
                                }
                            }
                            let response = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nAccess-Control-Allow-Origin: *\r\n\r\n{\"ok\":true}";
                            let _ = stream.write_all(response.as_bytes());
                        } else if request.starts_with("OPTIONS") {
                            let response = "HTTP/1.1 200 OK\r\nAccess-Control-Allow-Origin: *\r\nAccess-Control-Allow-Methods: POST, GET, OPTIONS\r\nAccess-Control-Allow-Headers: Content-Type\r\n\r\n";
                            let _ = stream.write_all(response.as_bytes());
                        } else {
                            let response = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nAccess-Control-Allow-Origin: *\r\n\r\n{\"ok\":true}";
                            let _ = stream.write_all(response.as_bytes());
                        }
                    }
                }
            }
        }
    });
}

fn state_dir() -> PathBuf {
    if let Ok(home) = std::env::var("AISIGNALLIGHT_HOME") {
        return PathBuf::from(home);
    }
    // legacy env var
    if let Ok(home) = std::env::var("AI_TRAFFIC_LIGHT_WIN_HOME") {
        return PathBuf::from(home);
    }
    let local =
        std::env::var("LOCALAPPDATA").unwrap_or_else(|_| std::env::var("APPDATA").unwrap_or_default());
    // try new name first, fallback to legacy
    let new_dir = PathBuf::from(&local).join("AISignalLight");
    let legacy_dir = PathBuf::from(&local).join("AI Traffic Light Win");
    if new_dir.exists() || !legacy_dir.exists() {
        new_dir
    } else {
        legacy_dir
    }
}

// ── Position memory ──

fn load_position() -> Option<(f64, f64)> {
    let path = state_dir().join("position.json");
    let data = fs::read_to_string(&path).ok()?;
    let json: serde_json::Value = serde_json::from_str(&data).ok()?;
    let x = json.get("x")?.as_f64()?;
    let y = json.get("y")?.as_f64()?;
    Some((x, y))
}

#[tauri::command]
fn save_position(x: f64, y: f64) {
    let dir = state_dir();
    let _ = fs::create_dir_all(&dir);
    let payload = serde_json::json!({"x": x, "y": y});
    let tmp = dir.join("position.tmp");
    let _ = fs::write(&tmp, payload.to_string());
    let _ = fs::rename(&tmp, dir.join("position.json"));
}

// ── Auto-start ──

fn is_autostart_enabled() -> bool {
    let output = std::process::Command::new("reg")
        .args(&["query", AUTOSTART_PATH, "/v", AUTOSTART_KEY])
        .creation_flags(0x08000000)
        .output();
    output.map(|o| o.status.success()).unwrap_or(false)
}

fn enable_autostart() {
    if let Ok(exe) = std::env::current_exe() {
        let _ = Command::new("reg")
            .args(&[
                "add", AUTOSTART_PATH, "/v", AUTOSTART_KEY,
                "/t", "REG_SZ", "/d", &exe.to_string_lossy(), "/f",
            ])
            .creation_flags(0x08000000)
            .output();
    }
}

fn disable_autostart() {
    let _ = Command::new("reg")
        .args(&["delete", AUTOSTART_PATH, "/v", AUTOSTART_KEY, "/f"])
        .creation_flags(0x08000000)
        .output();
}

#[tauri::command]
fn toggle_autostart() -> bool {
    if is_autostart_enabled() {
        disable_autostart();
        false
    } else {
        enable_autostart();
        true
    }
}

// ── Tauri commands ──

#[tauri::command]
fn read_state() -> String {
    let path = state_dir().join("state.json");
    fs::read_to_string(&path).unwrap_or_else(|_| r#"{"state":"idle","sources":{}}"#.to_string())
}

#[tauri::command]
fn reset_all_states() {
    direct_reset_all();
}

#[tauri::command]
fn open_folder() {
    let _ = std::process::Command::new("explorer")
        .arg(state_dir())
        .spawn();
}

#[tauri::command]
fn show_context_menu(app: tauri::AppHandle, window: tauri::Window) {
    let menu = MenuBuilder::new(&app)
        .item(&MenuItemBuilder::with_id("widget_reset", "Reset to Idle").build(&app).unwrap())
        .separator()
        .item(&MenuItemBuilder::with_id("widget_restart", "Restart").build(&app).unwrap())
        .item(&MenuItemBuilder::with_id("widget_folder", "Open Folder").build(&app).unwrap())
        .separator()
        .item(&MenuItemBuilder::with_id("widget_quit", "Quit").build(&app).unwrap())
        .build()
        .unwrap();
    let _ = window.popup_menu(&menu);
}

#[tauri::command]
fn update_tray_icon(app: tauri::AppHandle, state: String) {
    if let Some(tray) = app.tray_by_id("main-tray") {
        let _ = tray.set_icon(Some(make_icon_for(&state)));
    }
}

#[tauri::command]
fn focus_source() {
    let path = state_dir().join("state.json");
    let data = fs::read_to_string(&path).unwrap_or_default();
    let source = if let Ok(json) = serde_json::from_str::<serde_json::Value>(&data) {
        json.get("source").and_then(|v| v.as_str()).unwrap_or("").to_string()
    } else {
        String::new()
    };

    if source.is_empty() || source == "none" {
        return;
    }

    let keyword = match source.as_str() {
        "antigravity" => "Gemini",
        "cursor" => "Cursor",
        "claude" => "Claude",
        "codex" => "Codex",
        "codexpp" => "Codex++",
        _ => return,
    };
    let fallback = match source.as_str() {
        "cursor" => "Cursor",
        _ => "Code",
    };

    let ps = format!(
        "$k='{0}';$f='{1}';$p=Get-Process|Where-Object{{$_.MainWindowTitle -like \"*$k*\"}}|Select -First 1;if(-not$p){{$p=Get-Process -Name $f -ErrorAction SilentlyContinue|Where-Object{{$_.MainWindowTitle}}|Select -First 1}};if($p){{Add-Type -Name W -Namespace N -MemberDefinition '[DllImport(\"user32.dll\")]public static extern bool SetForegroundWindow(IntPtr h);[DllImport(\"user32.dll\")]public static extern bool ShowWindow(IntPtr h,int c);';[N.W]::ShowWindow($p.MainWindowHandle,9)|Out-Null;[N.W]::SetForegroundWindow($p.MainWindowHandle)|Out-Null}}",
        keyword, fallback
    );
    let _ = Command::new("powershell")
        .args(&["-NoProfile", "-WindowStyle", "Hidden", "-Command", &ps])
        .creation_flags(0x08000000)
        .spawn();
}

fn restart_widget() {
    if let Ok(exe) = std::env::current_exe() {
        let _ = std::process::Command::new(exe).spawn();
    }
    std::process::exit(0);
}

// ── Tray icon ──

fn make_icon_for(state: &str) -> tauri::image::Image<'static> {
    let (r, g, b) = match state {
        "working" => (48, 209, 88),
        "waiting" => (255, 214, 10),
        "blocked" => (255, 69, 58),
        "idle" => (10, 132, 255),
        _ => (80, 80, 80),
    };
    make_tray_icon(r, g, b, state != "idle_off")
}

fn make_tray_icon(r: u8, g: u8, b: u8, active: bool) -> tauri::image::Image<'static> {
    let size = 32u32;
    let mut rgba = vec![0u8; (size * size * 4) as usize];
    let cx: i32 = 16;
    let cy: i32 = 16;
    let rad: i32 = 13;

    let (cr, cg, cb, ecr, ecg, ecb, ea) = if active {
        let inner_r = ((r as f32 * 0.7) as u8).min(r);
        let inner_g = ((g as f32 * 0.7) as u8).min(g);
        let inner_b = ((b as f32 * 0.7) as u8).min(b);
        (inner_r, inner_g, inner_b, r / 2, g / 2, b / 2, 160u8)
    } else {
        (30, 30, 30, 20, 20, 20, 80u8)
    };

    for y in 0..size {
        for x in 0..size {
            let dx = x as i32 - cx;
            let dy = y as i32 - cy;
            let dist2 = dx * dx + dy * dy;
            let i = ((y * size + x) * 4) as usize;
            if dist2 <= rad * rad {
                let t = 1.0 - (dist2 as f32 / (rad * rad) as f32);
                rgba[i] = ((1.0 - t) * cr as f32 + t * r as f32) as u8;
                rgba[i + 1] = ((1.0 - t) * cg as f32 + t * g as f32) as u8;
                rgba[i + 2] = ((1.0 - t) * cb as f32 + t * b as f32) as u8;
                rgba[i + 3] = 255;
            } else if dist2 <= (rad + 1) * (rad + 1) {
                rgba[i] = ecr;
                rgba[i + 1] = ecg;
                rgba[i + 2] = ecb;
                rgba[i + 3] = ea;
            }
        }
    }
    tauri::image::Image::new_owned(rgba, size, size)
}

// ── App ──

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    start_bridge_server();
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            if let Some(window) = app.get_webview_window("main") {
                if let Some((x, y)) = load_position() {
                    let _ = window.set_position(tauri::Position::Physical(
                        tauri::PhysicalPosition::new(x as i32, y as i32),
                    ));
                } else if let Ok(Some(monitor)) = window.primary_monitor() {
                    let screen = monitor.size();
                    let win = window.outer_size().unwrap();
                    let x = (screen.width as i32).saturating_sub(win.width as i32 + 40);
                    let y = (screen.height as i32).saturating_sub(win.height as i32 + 100);
                    let _ = window.set_position(tauri::Position::Physical(
                        tauri::PhysicalPosition::new(x.max(0), y.max(0)),
                    ));
                }
            }

            let tray_menu = MenuBuilder::new(app)
                .item(&MenuItemBuilder::with_id("tray_reset", "Reset to Idle").build(app)?)
                .separator()
                .item(&MenuItemBuilder::with_id("tray_autostart", if is_autostart_enabled() { "Auto Start: ON" } else { "Auto Start: OFF" }).build(app)?)
                .separator()
                .item(&MenuItemBuilder::with_id("tray_restart", "Restart").build(app)?)
                .item(&MenuItemBuilder::with_id("tray_folder", "Open Folder").build(app)?)
                .separator()
                .item(&MenuItemBuilder::with_id("tray_quit", "Quit").build(app)?)
                .build()?;

            TrayIconBuilder::with_id("main-tray")
                .icon(make_icon_for("idle_off"))
                .tooltip("AISignalLight")
                .menu(&tray_menu)
                .on_menu_event(|_app, event| match event.id().as_ref() {
                    "tray_reset" => direct_reset_all(),
                    "tray_autostart" => { toggle_autostart(); restart_widget(); }
                    "tray_restart" => restart_widget(),
                    "tray_folder" => open_folder(),
                    "tray_quit" => std::process::exit(0),
                    _ => {}
                })
                .build(app)?;

            Ok(())
        })
        .on_menu_event(|_app, event| match event.id().as_ref() {
            "widget_reset" => direct_reset_all(),
            "widget_restart" => restart_widget(),
            "widget_folder" => open_folder(),
            "widget_quit" => std::process::exit(0),
            _ => {}
        })
        .invoke_handler(tauri::generate_handler![
            read_state,
            reset_all_states,
            open_folder,
            show_context_menu,
            update_tray_icon,
            focus_source,
            save_position,
            toggle_autostart
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
