# Proposal: OpenClaw HTTP Transport Migration

**Change:** `openclaw-http-transport`
**Parent:** `openclaw-phase1-tdd` (Phase 1 spawn implementation)
**Status:** Planning
**Date:** 2026-02-16

## Problem

The Phase 1 OpenClaw integration uses `POST /api/sessions/spawn` — a gateway-internal endpoint that is not exposed via OpenClaw's public HTTP API:

- `POST /api/sessions/spawn` → `405 Method Not Allowed`
- The endpoint is undocumented and not part of OpenClaw's supported API surface
- Fails both locally and remotely — returns 405 regardless of network path

The original Phase 1 tests used mocked HTTP (respx), so the contract mismatch was never caught against a live gateway.

## Proposed Solution

Migrate `OpenClawEngine` from the internal `/api/sessions/spawn` endpoint to OpenClaw's **documented `/v1/responses` HTTP API** (OpenResponses-compatible).

### Why `/v1/responses` over `/v1/chat/completions`?

1. **Richer input model** — supports items (messages, images, files), instructions, and tools
2. **Better error semantics** — structured error objects with types
3. **Future-proof** — OpenResponses is OpenClaw's primary API direction
4. **Session support** — `user` field enables stable session routing (useful for Phase 2)

### Why not keep `/api/sessions/spawn`?

1. Not documented, not supported, not guaranteed stable
2. Doesn't work through reverse proxies / Tailscale Serve
3. Couples Flock to OpenClaw internals rather than public API

## Scope

### In Scope
- Migrate `OpenClawEngine.evaluate()` to use `/v1/responses`
- Adapt request payload construction (spawn format → OpenResponses format)
- Adapt response parsing (spawn result → OpenResponses output items)
- Update all existing tests to match new transport
- Update documentation and examples
- Ensure retry/repair logic still works
- Gateway config requirement: document that `responses` endpoint must be enabled

### Out of Scope
- Streaming support (SSE) — defer to Phase 2
- Client tool support (function calls) — defer to Phase 2
- Session mode (persistent sessions via `user` field) — defer to Phase 2
- Multi-output types — already out of scope per Phase 1 decisions
- `/v1/chat/completions` alternative transport — single transport path for simplicity

## Impact

- **Breaking:** Yes — users must enable `gateway.http.endpoints.responses.enabled: true` in their OpenClaw config. This is a one-line config change.
- **API change:** None — `flock.openclaw_agent()` API is unchanged. The transport is an internal detail.
- **Test impact:** Transport-level tests need updating (mock responses change shape). Config and builder tests unchanged.

## Rollback

Revert the engine changes. The `/api/sessions/spawn` path can be restored as a fallback if needed, but given it's undocumented, we should move forward cleanly.
