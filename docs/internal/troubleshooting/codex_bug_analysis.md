# Bug Analysis: Event Log Flooding With `_main__BookHook`

## Summary
- **Issue**: The dashboard Event Log shows a rapidly growing list of `_main__BookHook` entries with identical timestamps and correlation IDs, creating the impression of an infinite loop.
- **Impact**: UI becomes noisy/unusable during any streaming LLM run (e.g., `book_idea_agent`), and downstream tooling that reads `events` interprets each token as a new artifact publication.
- **Status**: Regression introduced in commit `e5107b6` (Oct 6 2025) while adding streaming output visualization.

## Reproduction (Oct 6 2025)
1. `uv run python examples/showcase/04b_dashboard_edge_cases.py` to start the orchestrator with the dashboard.
2. Open the dashboard, publish an `Idea`, and watch the Event Log module.
3. As soon as `book_idea_agent` streams tokens, the log floods with dozens of `_main__BookHook` rows sharing the same timestamp (matches screenshot).

## What I Observed
- Every row in the screenshot maps to the same correlation ID (`896961af-0c14-4c7e-b8f9-de4a4700979a`) and agent (`book_idea_agent`).
- Backend metrics show only a single agent execution; the dashboard websocket traffic, however, emits many `message` updates for the same artifact ID while streaming.

## Root Cause
1. **Streaming handler now mutates the message store on every token.**
   - `frontend/src/services/websocket.ts:209-266` (commit `e5107b6`) appends each `StreamingOutputEvent` token to the dashboard store by calling `this.store.addMessage(updatedMessage)`.
   - Earlier baseline (`HEAD~7`, commit `c823096`) only nudged `lastActive` and never touched the message list, so the Event Log saw a single `message_published` per artifact.
2. **`addMessage` always prepends into the event log.**
   - `frontend/src/store/graphStore.ts:128-134` unconditionally pushes the (possibly existing) message into both `messages` and `events`.
   - Because streaming updates reuse ID `streaming_${agent}_${correlation}`, each token reuses the same ID but still lands in `events`, so the Event Log renders one row per token.
3. **Timestamps come from `Date.now()`, not the backend event timestamp.**
   - `websocket.ts:240` overwrites `timestamp` on every token. Tokens arriving within the same second collapse to identical UI timestamps, reinforcing the “infinite loop” perception.

## Why It Regressed
- Streaming visualization was added in `e5107b6` (Oct 6). That commit changed the `streaming_output` handler to build temporary messages so the Blackboard view and Live Output tab could highlight in-flight artifacts. The existing store contract wasn’t updated to distinguish between “new artifact” vs “incremental update”, so the Event Log (which reuses the `events` array) now logs every incremental change.

## Suggested Fixes
1. **Teach the store to distinguish updates from new entries.** Options:
   - Add a dedicated `updateMessage` helper that updates `messages` without touching `events`, and have the streaming handler use it when `existingMessage` is truthy.
   - Or, inside `addMessage`, detect when `state.messages` already has the same `id` and skip prepending to `events` (or only do so when `message.isStreaming` is false).
2. **Preserve backend timestamps.** Use `StreamingOutputEvent.timestamp` (already provided by the backend) instead of `Date.now()` so rows reflect actual ordering even if multiple tokens are rendered.
3. **Regression test.** Extend `frontend/src/components/modules/EventLogModule.test.tsx` or add a new store test that feeds two streaming tokens plus a final `message_published` and asserts that only the final artifact row appears in `events`.

## Possible Complete Fix
1. Modify `addMessage` in `frontend/src/store/graphStore.ts` so that when a message ID already exists, it replaces the stored value but does **not** prepend the entry into `events`. That keeps the live graph updated while preventing duplicate Event Log rows for streaming tokens.
2. Update the streaming handler in `frontend/src/services/websocket.ts` to call a new helper (e.g., `useGraphStore.getState().updateMessage`) when it detects `existingMessage`. This helper should merge the updated fields (including streaming text) and keep the original timestamp unless the server explicitly provides a newer one.
3. When the `message_published` event arrives with the final artifact, the existing `addMessage` call still executes, creating the single Event Log row that represents the finished artifact.

## Fix Implemented (Oct 6 2025)
- `frontend/src/store/graphStore.ts`: added `updateMessage` and taught `addMessage` to skip Event Log inserts for streaming artifacts while updating existing entries in-place.
- `frontend/src/services/websocket.ts`: the streaming handler now uses `updateMessage` for incremental tokens and preserves backend-provided timestamps via `toEpochMs`; the `message_published` handler also respects the server timestamp.
- `frontend/src/store/graphStore.test.ts`: expanded coverage to confirm streaming messages no longer spam the Event Log and that `updateMessage` keeps events in sync.

## Next Steps
- Run the full `04b_dashboard_edge_cases` example and confirm the Event Log now records a single `_main__BookHook` row per correlation ID while streaming output still renders in the Live Output tab.
- Consider a follow-up UX tweak: show streaming progress in the Event Log via an inline badge instead of duplicate rows.
