mod extension_loopback;
mod file_access;
mod local_worker;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(local_worker::LocalWorker::default())
        .manage(extension_loopback::LoopbackController::default())
        .invoke_handler(tauri::generate_handler![
            extension_loopback::start_extension_loopback,
            extension_loopback::stop_extension_loopback,
            file_access::select_csv_file,
            local_worker::local_worker_status,
            local_worker::select_worker_executable,
            local_worker::save_local_worker,
            local_worker::start_local_worker,
            local_worker::stop_local_worker,
            local_worker::open_server_dashboard,
            local_worker::research_local,
            local_worker::server_connection,
            local_worker::save_server_connection,
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
        .build(tauri::generate_context!())
        .expect("error while building Deal Scanner")
        .run(|app, event| {
            if let tauri::RunEvent::Exit = event {
                use tauri::Manager;
                app.state::<local_worker::LocalWorker>().shutdown();
            }
        });
}
