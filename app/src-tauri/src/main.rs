#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

const SETTINGS_FILE_NAME: &str = "settings.json";

#[derive(Debug, thiserror::Error, serde::Serialize)]
enum PreferencesError {
    #[error("loading the config directory failed")]
    Directory(),

    #[error("reading failed")]
    File(String),

    #[error("deserialize error")]
    Serialize(String),
}

#[tauri::command]
fn load_preferences(app_handle: tauri::AppHandle) -> Result<serde_json::Value, PreferencesError> {
    serde_json::from_reader(std::io::BufReader::new(
        std::fs::File::open(
            app_handle
                .path_resolver()
                .app_config_dir()
                .ok_or(PreferencesError::Directory())?
                .join(SETTINGS_FILE_NAME),
        )
        .map_err(|error| PreferencesError::File(format!("{:?}", error)))?,
    ))
    .map_err(|error| PreferencesError::Serialize(format!("{:?}", error)))
}

#[tauri::command]
fn store_preferences(
    app_handle: tauri::AppHandle,
    preferences: serde_json::Value,
) -> Result<serde_json::Value, PreferencesError> {
    serde_json::to_writer(
        std::io::BufWriter::new(
            std::fs::File::create(
                app_handle
                    .path_resolver()
                    .app_config_dir()
                    .ok_or(PreferencesError::Directory())?
                    .join(SETTINGS_FILE_NAME),
            )
            .map_err(|error| PreferencesError::File(format!("{:?}", error)))?,
        ),
        &preferences,
    )
    .map_err(|error| PreferencesError::Serialize(format!("{:?}", error)))?;
    load_preferences(app_handle)
}

fn main() {
    tauri::Builder::default()
        .setup(|app| {
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
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![load_preferences])
        .invoke_handler(tauri::generate_handler![store_preferences])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
