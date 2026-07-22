mod extension_loopback;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(extension_loopback::LoopbackController::default())
        .invoke_handler(tauri::generate_handler![
            extension_loopback::start_extension_loopback,
            extension_loopback::stop_extension_loopback,
        ])
        .plugin(tauri_plugin_log::Builder::new().build())
        .plugin(tauri_plugin_notification::init())
        .plugin(
            tauri_plugin_sql::Builder::default()
                .add_migrations("sqlite:deal-scanner-cache.db", vec![])
                .build(),
        )
        .setup(|app| {
            use tauri::Manager;
            let salt_path = app
                .path()
                .app_local_data_dir()
                .expect("could not resolve app local data path")
                .join("stronghold-salt.txt");
            app.handle()
                .plugin(tauri_plugin_stronghold::Builder::with_argon2(&salt_path).build())?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Deal Scanner");
}
