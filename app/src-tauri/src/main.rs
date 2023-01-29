#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]
use notify::Watcher;
use std::{io::Write, sync::atomic::AtomicBool};
use tauri::Manager;

const PREFERENCES_FILE_NAME: &str = "preferences.json";

struct State {
    watcher: Option<notify::RecommendedWatcher>,
    path: Option<std::path::PathBuf>,
}

impl State {
    fn watch(&mut self, path: std::path::PathBuf) {
        if let Some(watcher) = self.watcher.as_mut() {
            if let Err(error) = watcher.watch(&path, notify::RecursiveMode::NonRecursive) {
                eprintln!("watch error {error:?}");
            }
        }
        self.path.replace(path);
    }

    fn unwatch(&mut self) {
        if let Some(path) = self.path.as_mut() {
            if let Some(watcher) = self.watcher.as_mut() {
                if let Err(error) = watcher.unwatch(path) {
                    eprintln!("watch error {error:?}");
                }
            }
            self.path.take();
        }
    }
}

enum Action {
    Context {
        running: std::sync::Arc<AtomicBool>,
        handle: tauri::async_runtime::JoinHandle<()>,
    },
    Cancelling,
    None,
}

impl Action {
    fn cancel(&mut self) -> Action {
        match self {
            Action::Context {
                running: _,
                handle: _,
            } => std::mem::replace(self, Action::Cancelling),
            Action::Cancelling => Action::Cancelling,
            Action::None => Action::None,
        }
    }
}

struct SharedState {
    state: std::sync::Mutex<State>,
    action: std::sync::Mutex<Action>,
}

#[derive(Debug, Clone, serde::Serialize)]
enum CreateConfigurationError {
    Create(String),
}

#[tauri::command]
async fn create_configuration(
    content: String,
) -> Result<Option<std::path::PathBuf>, CreateConfigurationError> {
    if let Some(path) = tauri::api::dialog::blocking::FileDialogBuilder::new()
        .set_title("Create configuration")
        .set_file_name("undr.toml")
        .add_filter("configuration", &["toml"])
        .save_file()
    {
        std::fs::write(&path, content)
            .map_err(|error| CreateConfigurationError::Create(format!("{error:?}")))?;
        Ok(Some(path))
    } else {
        Ok(None)
    }
}

#[derive(Debug, Clone, serde::Serialize)]
#[serde(tag = "type", content = "payload")]
enum ConfigurationOrError {
    #[serde(rename = "configuration")]
    Configuration((undr::Configuration, std::path::PathBuf)),
    #[serde(rename = "error")]
    Error(String),
}

impl From<Result<(undr::Configuration, std::path::PathBuf), undr::ConfigurationError>>
    for ConfigurationOrError
{
    fn from(
        value: Result<(undr::Configuration, std::path::PathBuf), undr::ConfigurationError>,
    ) -> Self {
        match value {
            Ok(configuration) => ConfigurationOrError::Configuration(configuration),
            Err(error) => ConfigurationOrError::Error(format!("{error:?}")),
        }
    }
}

#[derive(Debug, Clone, serde::Serialize)]
struct ConfigurationPayload {
    path: std::path::PathBuf,
    configuration_or_error: ConfigurationOrError,
}

impl ConfigurationPayload {
    fn from_path(path: &std::path::PathBuf) -> Self {
        ConfigurationPayload {
            path: path.clone(),
            configuration_or_error: undr::Configuration::from_path(path).into(),
        }
    }
}

fn emit_configuration(
    app_handle: &tauri::AppHandle,
    configuration_payload: Option<ConfigurationPayload>,
) {
    if let Err(emit_error) = app_handle.emit_to("main", "configuration", configuration_payload) {
        eprintln!("emit_to('main', 'configuration', payload) failed with error {emit_error:?}");
    }
}

#[derive(Debug, Clone, serde::Serialize)]
enum ActionType {
    #[serde(rename = "calc_size")]
    CalcSize,

    #[serde(rename = "cite")]
    Cite,

    #[serde(rename = "install")]
    Install,
}

#[derive(Debug, Clone, serde::Serialize)]
#[serde(tag = "type", content = "payload")]
enum ActionPayload {
    #[serde(rename = "start")]
    Start(ActionType),

    #[serde(rename = "message")]
    Message(undr::Message),

    #[serde(rename = "error")]
    Error(String),

    #[serde(rename = "end")]
    End,
}

fn emit_action(app_handle: &tauri::AppHandle, action_payload: ActionPayload) {
    if let Err(emit_error) = app_handle.emit_to("main", "action", action_payload) {
        eprintln!("emit_to('main', 'action', payload) failed with error {emit_error:?}");
    }
}

#[tauri::command]
fn load_configuration(app_handle: tauri::AppHandle, path: Option<std::path::PathBuf>) {
    let mut state = app_handle
        .state::<SharedState>()
        .inner()
        .state
        .lock()
        .unwrap();
    state.unwatch();
    if let Some(path) = path {
        emit_configuration(&app_handle, Some(ConfigurationPayload::from_path(&path)));
        state.watch(path);
    } else {
        emit_configuration(&app_handle, None);
    }
}

#[derive(Debug, Clone, serde::Serialize)]
enum SaveConfigurationError {
    Seriliaze(String),
    Write(String),
}

#[tauri::command]
fn save_configuration(
    app_handle: tauri::AppHandle,
    path: std::path::PathBuf,
    configuration: (undr::Configuration, std::path::PathBuf),
) -> Result<(), SaveConfigurationError> {
    let (mut configuration, datasets_directory) = configuration;
    configuration.directory = datasets_directory; // un-resolve the datasets directory path
    let mut state = app_handle
        .state::<SharedState>()
        .inner()
        .state
        .lock()
        .unwrap();
    state.unwatch();
    std::fs::write(
        &path,
        toml::ser::to_string_pretty(&configuration)
            .map_err(|error| SaveConfigurationError::Seriliaze(format!("{error:?}")))?,
    )
    .map_err(|error| SaveConfigurationError::Write(format!("{error:?}")))?;
    emit_configuration(&app_handle, Some(ConfigurationPayload::from_path(&path)));
    state.watch(path);
    Ok(())
}

#[tauri::command]
fn show_main_window(window: tauri::Window) {
    window.get_window("main").unwrap().show().unwrap();
}

#[derive(Debug, Clone, serde::Serialize)]
enum PreferencesError {
    Directory(String),
    File(String),
    Serialize(String),
}

#[tauri::command]
fn load_preferences(
    app_handle: tauri::AppHandle,
) -> Result<(serde_json::Value, usize), PreferencesError> {
    Ok((
        serde_json::from_reader(std::io::BufReader::new(
            std::fs::File::open(
                app_handle
                    .path_resolver()
                    .app_config_dir()
                    .ok_or_else(|| {
                        PreferencesError::Directory(
                            "tauri::api::path::app_config_dir returned None".to_owned(),
                        )
                    })?
                    .join(PREFERENCES_FILE_NAME),
            )
            .map_err(|error| PreferencesError::File(format!("{error:?}")))?,
        ))
        .map_err(|error| PreferencesError::Serialize(format!("{error:?}")))?,
        std::thread::available_parallelism()
            .unwrap_or(std::num::NonZeroUsize::new(1).unwrap())
            .get()
            * 2,
    ))
}

#[tauri::command]
fn store_preferences(
    app_handle: tauri::AppHandle,
    preferences: serde_json::Value,
) -> Result<(serde_json::Value, usize), PreferencesError> {
    serde_json::to_writer(
        std::io::BufWriter::new(
            std::fs::File::create(
                app_handle
                    .path_resolver()
                    .app_config_dir()
                    .ok_or_else(|| {
                        PreferencesError::Directory(
                            "tauri::api::path::app_config_dir returned None".to_owned(),
                        )
                    })?
                    .join(PREFERENCES_FILE_NAME),
            )
            .map_err(|error| PreferencesError::File(format!("{error:?}")))?,
        ),
        &preferences,
    )
    .map_err(|error| PreferencesError::Serialize(format!("{error:?}")))?;
    load_preferences(app_handle)
}

#[derive(Debug, Clone, serde::Serialize)]
enum RevealInOsError {
    Command(String),
}

// see https://github.com/tauri-apps/tauri/issues/4062
#[tauri::command]
fn reveal_in_os(path: std::path::PathBuf) -> Result<(), RevealInOsError> {
    #[cfg(target_os = "linux")]
    {
        if path.as_os_str().to_string_lossy().contains(",") {
            // see https://gitlab.freedesktop.org/dbus/dbus/-/issues/76
            let new_path = match std::fs::metadata(&path).unwrap().is_dir() {
                true => path,
                false => {
                    let mut path2 = std::path::PathBuf::from(path);
                    path2.pop();
                    path2
                }
            };
            std::process::Command::new("xdg-open")
                .arg(&new_path)
                .spawn()
                .map_err(|error| RevealInOsError::Command(format!("{error:?}")))?;
        } else {
            std::process::Command::new("dbus-send")
                .args([
                    "--session",
                    "--dest=org.freedesktop.FileManager1",
                    "--type=method_call",
                    "/org/freedesktop/FileManager1",
                    "org.freedesktop.FileManager1.ShowItems",
                    format!("array:string:\"file://{}\"", path.display()).as_str(),
                    "string:\"\"",
                ])
                .spawn()
                .map_err(|error| RevealInOsError::Command(format!("{error:?}")))?;
        }
    }

    #[cfg(target_os = "macos")]
    {
        std::process::Command::new("open")
            .args([&std::ffi::OsString::from("-R"), path.as_os_str()])
            .spawn()
            .map_err(|error| RevealInOsError::Command(format!("{error:?}")))?;
    }

    #[cfg(target_os = "windows")]
    {
        std::process::Command::new("explorer")
            .args([&std::ffi::OsString::from("/select,"), path.as_os_str()])
            .spawn()
            .map_err(|error| RevealInOsError::Command(format!("{error:?}")))?;
    }

    Ok(())
}

#[derive(Debug, Clone, serde::Serialize)]
enum ActionError {
    Active(String),
}

#[tauri::command]
fn calc_size(
    app_handle: tauri::AppHandle,
    mut configuration: undr::Configuration,
    file_permits: usize,
    download_index_permits: usize,
) -> Result<(), ActionError> {
    let mut action = app_handle
        .state::<SharedState>()
        .inner()
        .action
        .lock()
        .unwrap();
    match &*action {
        Action::None => {
            let app_handle = app_handle.clone();
            let running = std::sync::Arc::new(std::sync::atomic::AtomicBool::new(true));
            *action = Action::Context {
                running: running.clone(),
                handle: tauri::async_runtime::spawn(async move {
                    emit_action(&app_handle, ActionPayload::Start(ActionType::CalcSize));
                    for dataset in configuration
                        .datasets
                        .iter_mut()
                        .filter(|dataset| dataset.mode != undr::Mode::Disabled)
                    {
                        dataset.mode = undr::Mode::Remote;
                    }
                    match configuration
                        .install(
                            running,
                            |message| {
                                emit_action(&app_handle, ActionPayload::Message(message));
                            },
                            undr::Force(false),
                            undr::Keep(false),
                            undr::DispatchDois(false),
                            undr::CalculateSize(true),
                            undr::FilePermits(file_permits),
                            undr::DownloadIndexPermits(download_index_permits),
                            undr::DownloadPermits(1),
                            undr::DecodePermits(1),
                        )
                        .await
                    {
                        Ok(_) => {
                            emit_action(&app_handle, ActionPayload::End);
                        }
                        Err(error) => {
                            emit_action(&app_handle, ActionPayload::Error(format!("{error:?}")));
                        }
                    }
                    let mut action = app_handle
                        .state::<SharedState>()
                        .inner()
                        .action
                        .lock()
                        .unwrap();
                    if let Action::Context {
                        running: _,
                        handle: _,
                    } = &*action
                    {
                        *action = Action::None;
                    }
                }),
            };
            Ok(())
        }
        _ => Err(ActionError::Active(
            "there is already an active action (calc. size, cite, or install)".to_owned(),
        )),
    }
}

#[tauri::command]
#[allow(clippy::too_many_arguments)]
fn cite(
    app_handle: tauri::AppHandle,
    configuration: undr::Configuration,
    force: bool,
    file_permits: usize,
    download_index_permits: usize,
    download_doi_permits: usize,
    doi_timeout: f64,
    output_path: std::path::PathBuf,
) -> Result<(), ActionError> {
    let mut action = app_handle
        .state::<SharedState>()
        .inner()
        .action
        .lock()
        .unwrap();
    match &*action {
        Action::None => {
            let app_handle = app_handle.clone();
            let running = std::sync::Arc::new(std::sync::atomic::AtomicBool::new(true));
            *action = Action::Context {
                running: running.clone(),
                handle: tauri::async_runtime::spawn(async move {
                    emit_action(&app_handle, ActionPayload::Start(ActionType::Cite));
                    match configuration
                        .bibtex(
                            running,
                            |message| {
                                emit_action(&app_handle, ActionPayload::Message(message));
                            },
                            undr::Force(force),
                            undr::FilePermits(file_permits),
                            undr::DownloadIndexPermits(download_index_permits),
                            undr::DownloadDoiPermits(download_doi_permits),
                            Some(doi_timeout),
                            output_path,
                            undr::Pretty(true),
                        )
                        .await
                    {
                        Ok(_) => {
                            emit_action(&app_handle, ActionPayload::End);
                        }
                        Err(error) => {
                            emit_action(&app_handle, ActionPayload::Error(format!("{error:?}")));
                        }
                    }
                    let mut action = app_handle
                        .state::<SharedState>()
                        .inner()
                        .action
                        .lock()
                        .unwrap();
                    if let Action::Context {
                        running: _,
                        handle: _,
                    } = &*action
                    {
                        *action = Action::None;
                    }
                }),
            };
            Ok(())
        }
        _ => Err(ActionError::Active(
            "there is already an active action (calc. size, cite, or install)".to_owned(),
        )),
    }
}

#[tauri::command]
#[allow(clippy::too_many_arguments)]
fn install(
    app_handle: tauri::AppHandle,
    configuration: undr::Configuration,
    force: bool,
    keep: bool,
    file_permits: usize,
    download_index_permits: usize,
    download_permits: usize,
    decode_permits: usize,
) -> Result<(), ActionError> {
    let mut action = app_handle
        .state::<SharedState>()
        .inner()
        .action
        .lock()
        .unwrap();
    match &*action {
        Action::None => {
            let app_handle = app_handle.clone();
            let running = std::sync::Arc::new(std::sync::atomic::AtomicBool::new(true));
            *action = Action::Context {
                running: running.clone(),
                handle: tauri::async_runtime::spawn(async move {
                    emit_action(&app_handle, ActionPayload::Start(ActionType::Install));
                    match configuration
                        .install(
                            running,
                            |message| {
                                emit_action(&app_handle, ActionPayload::Message(message));
                            },
                            undr::Force(force),
                            undr::Keep(keep),
                            undr::DispatchDois(false),
                            undr::CalculateSize(false),
                            undr::FilePermits(file_permits),
                            undr::DownloadIndexPermits(download_index_permits),
                            undr::DownloadPermits(download_permits),
                            undr::DecodePermits(decode_permits),
                        )
                        .await
                    {
                        Ok(_) => {
                            emit_action(&app_handle, ActionPayload::End);
                        }
                        Err(error) => {
                            emit_action(&app_handle, ActionPayload::Error(format!("{error:?}")));
                        }
                    }
                    let mut action = app_handle
                        .state::<SharedState>()
                        .inner()
                        .action
                        .lock()
                        .unwrap();
                    if let Action::Context {
                        running: _,
                        handle: _,
                    } = &*action
                    {
                        *action = Action::None;
                    }
                }),
            };
            Ok(())
        }
        _ => Err(ActionError::Active(
            "there is already an active action (calc. size, cite, or install)".to_owned(),
        )),
    }
}

#[tauri::command]
fn cancel(app_handle: tauri::AppHandle) -> Result<(), ActionError> {
    let action = app_handle
        .state::<SharedState>()
        .inner()
        .action
        .lock()
        .unwrap()
        .cancel();
    match action {
        Action::Context { running, handle } => {
            tauri::async_runtime::block_on(async move {
                running.store(false, std::sync::atomic::Ordering::Release);
                handle.abort();
                _ = handle.await;
                *app_handle
                    .state::<SharedState>()
                    .inner()
                    .action
                    .lock()
                    .unwrap() = Action::None;
            });
            Ok(())
        }
        _ => Err(ActionError::Active("there is no active action".to_owned())),
    }
}

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            #[cfg(debug_assertions)]
            {
                app.get_window("main").unwrap().open_devtools();
            }
            let config_directory = app
                .path_resolver()
                .app_config_dir()
                .expect("failed to resolve the config directory");
            std::fs::create_dir_all(&config_directory).unwrap_or_else(|_| {
                panic!(
                    "failed to create the config directory \"{}\"",
                    config_directory.display()
                )
            });
            if let Ok(mut file) = std::fs::OpenOptions::new()
                .write(true)
                .create_new(true)
                .open(config_directory.join(PREFERENCES_FILE_NAME))
            {
                file.write_all(b"{}\n").unwrap_or_else(|_| {
                    panic!(
                        "writing to \"{}\" failed",
                        config_directory.join(PREFERENCES_FILE_NAME).display()
                    )
                });
            }
            let app_handle = app.handle();
            app.manage(SharedState {
                state: std::sync::Mutex::new(State {
                    watcher: notify::recommended_watcher(
                        move |result: notify::Result<notify::Event>| match result {
                            Ok(event) => match event.kind {
                                notify::EventKind::Any
                                | notify::EventKind::Access(_)
                                | notify::EventKind::Create(_)
                                | notify::EventKind::Modify(_) => {
                                    if event.paths.len() == 1 {
                                        emit_configuration(
                                            &app_handle,
                                            Some(ConfigurationPayload::from_path(&event.paths[0])),
                                        );
                                    }
                                }
                                notify::EventKind::Remove(_) | notify::EventKind::Other => {}
                            },
                            Err(error) => eprintln!("watch error {error:?}"),
                        },
                    )
                    .map_or_else(
                        |error| {
                            eprintln!("creating a watched failed with error {error:?}");
                            None
                        },
                        Some,
                    ),
                    path: None,
                }),
                action: std::sync::Mutex::new(Action::None),
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            create_configuration,
            load_configuration,
            save_configuration,
            show_main_window,
            load_preferences,
            store_preferences,
            reveal_in_os,
            calc_size,
            cite,
            install,
            cancel,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
