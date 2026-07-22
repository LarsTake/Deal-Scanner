---
type: "query"
date: "2026-07-22T19:21:50.341663+00:00"
question: "Which explicit requirements in the improved Deal Scanner plan remain unimplemented rather than merely unverified externally? Focus on Tauri loopback, token storage, SQLite offline cache, platform build workflows, storage signed URLs, SSRF, CSP, notification channels, and image OCR."
contributor: "graphify"
source_nodes: ["Notification", "image_content", "DealScannerError", "EbayProvider", "ImageAccess"]
---

# Q: Which explicit requirements in the improved Deal Scanner plan remain unimplemented rather than merely unverified externally? Focus on Tauri loopback, token storage, SQLite offline cache, platform build workflows, storage signed URLs, SSRF, CSP, notification channels, and image OCR.

## Answer

The graph directly evidences image import, owned-image access, local image resolution, eBay provider behavior, generated contracts, and notification wire types. It does not contain sufficient direct evidence to prove Tauri loopback, secure token storage, SQLite offline cache, cross-platform build execution, SSRF/CSP controls, notification adapter execution, or OCR execution; those areas require source and runtime inspection.

## Source Nodes

- Notification
- image_content
- DealScannerError
- EbayProvider
- ImageAccess