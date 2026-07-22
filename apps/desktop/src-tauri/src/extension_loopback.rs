use std::{
    sync::Arc,
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};

use axum::{
    body::{Body, Bytes},
    extract::{Path, State},
    http::{header::CONTENT_TYPE, HeaderMap, HeaderName, Method, Response, StatusCode},
    response::IntoResponse,
    routing::post,
    Router,
};
use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine};
use serde::{Deserialize, Serialize};
use serde_json::json;
use sha2::{Digest, Sha256};
use subtle::ConstantTimeEq;
use tauri::State as TauriState;
use tokio::{
    net::TcpListener,
    sync::{oneshot, Mutex},
};
use tower_http::cors::{Any, CorsLayer};
use url::Url;

const MIN_TTL_SECONDS: u64 = 60;
const MAX_TTL_SECONDS: u64 = 15 * 60;
const MAX_REQUEST_BYTES: usize = 2 * 1024 * 1024;

#[derive(Default)]
pub struct LoopbackController {
    active: Mutex<Option<ActiveLoopback>>,
}

struct ActiveLoopback {
    shutdown: oneshot::Sender<()>,
}

struct ProxyState {
    upstream_base: String,
    bearer_token: Option<String>,
    development_user_id: Option<String>,
    pairing_hash: [u8; 32],
    expires_at: Instant,
    client: reqwest::Client,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct StartLoopbackRequest {
    api_url: String,
    bearer_token: Option<String>,
    development_user_id: Option<String>,
    ttl_seconds: Option<u64>,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LoopbackPairing {
    api_url: String,
    pairing_token: String,
    expires_at_unix: u64,
}

#[tauri::command]
pub async fn start_extension_loopback(
    controller: TauriState<'_, LoopbackController>,
    request: StartLoopbackRequest,
) -> Result<LoopbackPairing, String> {
    let (upstream_base, is_loopback) = validate_upstream(&request.api_url)?;
    let bearer_token = request
        .bearer_token
        .filter(|value| !value.trim().is_empty());
    let development_user_id = request
        .development_user_id
        .filter(|value| !value.trim().is_empty());
    if bearer_token.is_none() && (!is_loopback || development_user_id.is_none()) {
        return Err(
            "Für eine entfernte API ist eine angemeldete Supabase-Sitzung erforderlich.".into(),
        );
    }

    let ttl_seconds = request
        .ttl_seconds
        .unwrap_or(5 * 60)
        .clamp(MIN_TTL_SECONDS, MAX_TTL_SECONDS);
    let mut token_bytes = [0_u8; 32];
    getrandom::fill(&mut token_bytes)
        .map_err(|error| format!("Pairing-Token konnte nicht erzeugt werden: {error}"))?;
    let pairing_token = URL_SAFE_NO_PAD.encode(token_bytes);
    let pairing_hash: [u8; 32] = Sha256::digest(pairing_token.as_bytes()).into();

    let client = reqwest::Client::builder()
        .redirect(reqwest::redirect::Policy::none())
        .timeout(Duration::from_secs(30))
        .build()
        .map_err(|error| format!("HTTP-Client konnte nicht erstellt werden: {error}"))?;
    let proxy_state = Arc::new(ProxyState {
        upstream_base,
        bearer_token,
        development_user_id,
        pairing_hash,
        expires_at: Instant::now() + Duration::from_secs(ttl_seconds),
        client,
    });

    let listener = TcpListener::bind(("127.0.0.1", 0))
        .await
        .map_err(|error| format!("Loopback-Port konnte nicht geöffnet werden: {error}"))?;
    let address = listener
        .local_addr()
        .map_err(|error| format!("Loopback-Adresse konnte nicht gelesen werden: {error}"))?;
    let app = Router::new()
        .route("/api/v1/imports/browser", post(proxy_browser_import))
        .route(
            "/api/v1/listings/{listing_id}/images",
            post(proxy_image_import),
        )
        .layer(axum::extract::DefaultBodyLimit::max(MAX_REQUEST_BYTES))
        .layer(
            CorsLayer::new()
                .allow_origin(Any)
                .allow_methods([Method::POST, Method::OPTIONS])
                .allow_headers([
                    CONTENT_TYPE,
                    HeaderName::from_static("idempotency-key"),
                    HeaderName::from_static("x-extension-pairing"),
                ]),
        )
        .with_state(proxy_state);
    let (shutdown, shutdown_rx) = oneshot::channel();
    tauri::async_runtime::spawn(async move {
        let server = axum::serve(listener, app).with_graceful_shutdown(async move {
            tokio::select! {
                _ = shutdown_rx => {},
                _ = tokio::time::sleep(Duration::from_secs(ttl_seconds)) => {},
            }
        });
        if let Err(error) = server.await {
            log::error!("extension loopback stopped unexpectedly: {error}");
        }
    });

    let mut active = controller.active.lock().await;
    if let Some(previous) = active.take() {
        let _ = previous.shutdown.send(());
    }
    *active = Some(ActiveLoopback { shutdown });

    let expires_at_unix = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
        + ttl_seconds;
    Ok(LoopbackPairing {
        api_url: format!("http://{address}"),
        pairing_token,
        expires_at_unix,
    })
}

#[tauri::command]
pub async fn stop_extension_loopback(
    controller: TauriState<'_, LoopbackController>,
) -> Result<bool, String> {
    let mut active = controller.active.lock().await;
    Ok(active
        .take()
        .is_some_and(|entry| entry.shutdown.send(()).is_ok()))
}

async fn proxy_browser_import(
    State(state): State<Arc<ProxyState>>,
    headers: HeaderMap,
    body: Bytes,
) -> Response<Body> {
    forward(&state, &headers, "/api/v1/imports/browser", body, true).await
}

async fn proxy_image_import(
    State(state): State<Arc<ProxyState>>,
    Path(listing_id): Path<String>,
    headers: HeaderMap,
    body: Bytes,
) -> Response<Body> {
    if !is_uuid_like(&listing_id) {
        return problem(StatusCode::BAD_REQUEST, "Ungültige Listing-ID");
    }
    forward(
        &state,
        &headers,
        &format!("/api/v1/listings/{listing_id}/images"),
        body,
        false,
    )
    .await
}

async fn forward(
    state: &ProxyState,
    headers: &HeaderMap,
    path: &str,
    body: Bytes,
    forward_idempotency_key: bool,
) -> Response<Body> {
    if state.expires_at <= Instant::now() || !valid_pairing(headers, &state.pairing_hash) {
        return problem(
            StatusCode::UNAUTHORIZED,
            "Pairing ist ungültig oder abgelaufen",
        );
    }
    let mut request = state
        .client
        .post(format!("{}{path}", state.upstream_base))
        .header(CONTENT_TYPE, "application/json")
        .body(body);
    if let Some(token) = &state.bearer_token {
        request = request.bearer_auth(token);
    } else if let Some(user_id) = &state.development_user_id {
        request = request.header("X-Development-User", user_id);
    }
    if forward_idempotency_key {
        if let Some(value) = headers.get("idempotency-key") {
            request = request.header("Idempotency-Key", value.as_bytes());
        }
    }
    let upstream = match request.send().await {
        Ok(response) => response,
        Err(error) => {
            return problem(
                StatusCode::BAD_GATEWAY,
                &format!("API nicht erreichbar: {error}"),
            )
        }
    };
    let status = upstream.status();
    let content_type = upstream.headers().get(CONTENT_TYPE).cloned();
    let response_body = match upstream.bytes().await {
        Ok(bytes) => bytes,
        Err(error) => {
            return problem(
                StatusCode::BAD_GATEWAY,
                &format!("API-Antwort unlesbar: {error}"),
            )
        }
    };
    let mut builder = Response::builder().status(status);
    if let Some(value) = content_type {
        builder = builder.header(CONTENT_TYPE, value);
    }
    builder
        .body(Body::from(response_body))
        .unwrap_or_else(|_| problem(StatusCode::BAD_GATEWAY, "API-Antwort ungültig"))
}

fn valid_pairing(headers: &HeaderMap, expected_hash: &[u8; 32]) -> bool {
    let Some(token) = headers
        .get("x-extension-pairing")
        .and_then(|value| value.to_str().ok())
    else {
        return false;
    };
    let candidate: [u8; 32] = Sha256::digest(token.as_bytes()).into();
    expected_hash.ct_eq(&candidate).into()
}

fn validate_upstream(value: &str) -> Result<(String, bool), String> {
    let url = Url::parse(value).map_err(|_| "Die API-URL ist ungültig.".to_string())?;
    let loopback = matches!(url.host_str(), Some("127.0.0.1" | "localhost" | "::1"));
    if url.scheme() != "https" && !(url.scheme() == "http" && loopback) {
        return Err("Die API muss HTTPS verwenden; HTTP ist nur für Loopback erlaubt.".into());
    }
    if !url.username().is_empty()
        || url.password().is_some()
        || url.query().is_some()
        || url.fragment().is_some()
    {
        return Err("API-URL darf keine Zugangsdaten, Query oder Fragment enthalten.".into());
    }
    Ok((value.trim_end_matches('/').to_string(), loopback))
}

fn is_uuid_like(value: &str) -> bool {
    value.len() == 36
        && value.bytes().enumerate().all(|(index, byte)| {
            if matches!(index, 8 | 13 | 18 | 23) {
                byte == b'-'
            } else {
                byte.is_ascii_hexdigit()
            }
        })
}

fn problem(status: StatusCode, detail: &str) -> Response<Body> {
    (
        status,
        [(CONTENT_TYPE, "application/problem+json")],
        json!({
            "type": "about:blank",
            "title": status.canonical_reason().unwrap_or("Loopback-Fehler"),
            "status": status.as_u16(),
            "detail": detail,
        })
        .to_string(),
    )
        .into_response()
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::{body::to_bytes, http::HeaderValue};

    #[test]
    fn upstream_rejects_insecure_remote_and_credentials() {
        assert!(validate_upstream("http://example.com").is_err());
        assert!(validate_upstream("https://user:secret@example.com").is_err());
        assert!(validate_upstream("http://127.0.0.1:8000").is_ok());
        assert!(validate_upstream("https://api.example.com").is_ok());
    }

    #[test]
    fn pairing_comparison_uses_hash() {
        let expected: [u8; 32] = Sha256::digest(b"correct-token").into();
        let mut headers = HeaderMap::new();
        headers.insert(
            "x-extension-pairing",
            HeaderValue::from_static("correct-token"),
        );
        assert!(valid_pairing(&headers, &expected));
        headers.insert(
            "x-extension-pairing",
            HeaderValue::from_static("wrong-token"),
        );
        assert!(!valid_pairing(&headers, &expected));
    }

    #[test]
    fn listing_path_accepts_only_uuid_shape() {
        assert!(is_uuid_like("00000000-0000-4000-8000-000000000001"));
        assert!(!is_uuid_like("../../workers"));
    }

    #[tokio::test]
    async fn forward_preserves_auth_idempotency_status_and_body() {
        let upstream = Router::new().route(
            "/api/v1/imports/browser",
            post(|headers: HeaderMap, body: Bytes| async move {
                assert_eq!(
                    headers
                        .get("authorization")
                        .and_then(|value| value.to_str().ok()),
                    Some("Bearer user-jwt")
                );
                assert_eq!(
                    headers
                        .get("idempotency-key")
                        .and_then(|value| value.to_str().ok()),
                    Some("snapshot-1")
                );
                (StatusCode::CREATED, body)
            }),
        );
        let listener = TcpListener::bind(("127.0.0.1", 0)).await.unwrap();
        let address = listener.local_addr().unwrap();
        let server = tokio::spawn(async move { axum::serve(listener, upstream).await.unwrap() });
        let token = "pairing-token";
        let state = ProxyState {
            upstream_base: format!("http://{address}"),
            bearer_token: Some("user-jwt".into()),
            development_user_id: None,
            pairing_hash: Sha256::digest(token.as_bytes()).into(),
            expires_at: Instant::now() + Duration::from_secs(60),
            client: reqwest::Client::builder()
                .redirect(reqwest::redirect::Policy::none())
                .build()
                .unwrap(),
        };
        let mut headers = HeaderMap::new();
        headers.insert("x-extension-pairing", HeaderValue::from_static(token));
        headers.insert("idempotency-key", HeaderValue::from_static("snapshot-1"));

        let response = forward(
            &state,
            &headers,
            "/api/v1/imports/browser",
            Bytes::from_static(br#"{"externalId":"123"}"#),
            true,
        )
        .await;

        assert_eq!(response.status(), StatusCode::CREATED);
        assert_eq!(
            to_bytes(response.into_body(), 1024).await.unwrap(),
            Bytes::from_static(br#"{"externalId":"123"}"#)
        );
        server.abort();
    }
}
