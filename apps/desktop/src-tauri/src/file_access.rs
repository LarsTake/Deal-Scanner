use serde::Serialize;

const MAX_CSV_BYTES: usize = 2_000_000;

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SelectedTextFile {
    name: String,
    content: String,
}

#[tauri::command]
pub async fn select_csv_file() -> Result<Option<SelectedTextFile>, String> {
    let Some(handle) = rfd::AsyncFileDialog::new()
        .set_title("Marktdaten-CSV auswählen")
        .add_filter("CSV-Datei", &["csv"])
        .pick_file()
        .await
    else {
        return Ok(None);
    };
    let name = handle.file_name();
    if !name.to_ascii_lowercase().ends_with(".csv") {
        return Err("Es können ausschließlich CSV-Dateien geöffnet werden.".into());
    }
    let metadata = tokio::fs::metadata(handle.path())
        .await
        .map_err(|_| "Die CSV-Datei konnte nicht gelesen werden.".to_string())?;
    if metadata.len() > MAX_CSV_BYTES as u64 {
        return Err("Die CSV-Datei überschreitet das Limit von 2 MB.".into());
    }
    let bytes = handle.read().await;
    if bytes.len() > MAX_CSV_BYTES {
        return Err("Die CSV-Datei überschreitet das Limit von 2 MB.".into());
    }
    let content = String::from_utf8(bytes)
        .map_err(|_| "Die CSV-Datei muss UTF-8-kodiert sein.".to_string())?;
    Ok(Some(SelectedTextFile { name, content }))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn csv_limit_matches_server_contract() {
        assert_eq!(MAX_CSV_BYTES, 2_000_000);
    }
}
