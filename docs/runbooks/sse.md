# AI-run SSE operations

FabricAssist exposes authenticated, replayable progress at
`GET /api/v1/runs/{run_id}/events`. The API process streams only PostgreSQL
committed events; Valkey loss must never lose a completed run.

## Deploy validation

Before enabling SSE as the default client path on a hosting tier, authenticate a
test user, start a mock-provider run, and verify with `curl -N` that events are
unbuffered, ordered, include heartbeats, reconnect from `Last-Event-ID`, and
close after a terminal event. Repeat from Expo web, Android, and iOS. Record the
proxy idle timeout and keep REST status polling enabled as fallback.

## Recovery

If a client reconnects after an event-retention window or server restart, fetch
`GET /api/v1/runs/{run_id}` and refresh the canonical GraphQL scan/messages
query. Do not reconstruct a final answer from temporary `message.delta` UI
state. Never put event history in Valkey or log event content, tokens, image
bytes, or authorization headers.
