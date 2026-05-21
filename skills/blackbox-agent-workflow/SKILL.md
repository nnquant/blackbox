---
name: blackbox-agent-workflow
description: Operate the Blackbox quant research system through bbox CLI, Python SDK, offline spool sync, and WebUI verification. Use when Codex needs to run or guide AI-agent research workflows for Blackbox, including baseline search, branch creation from a run, run logging, artifacts, compare, notes, sweep attachment, offline sync from ~/.blackbox, idempotent retry handling, or checking that backend/SDK/CLI results are visible in the WebUI.
---

# Blackbox Agent Workflow

Use this skill to execute or explain reliable Blackbox agent workflows. Prefer current repository state over memory, and verify command names against `packages/cli/blackbox_cli/main.py` when changing implementation.

## Core Rules

- Use `bbox` as the CLI entrypoint.
- Use `import blackbox as bb` for SDK examples.
- Expect API/CLI envelopes shaped as `{"ok": true, "data": ..., "error": null}`.
- Use JSON output for automation; add `--select` to reduce context.
- Use `~/.blackbox` as the default local data/spool directory unless the user specifies another path.
- Pass `created_by_type` and `created_by_id` when an agent identity is available; WebUI displays these in Creator fields.
- Preserve idempotency keys and `client_event_id` values across retries for the same logical write.
- After writing data, verify in WebUI when a local browser target is available.

## Workflow

1. Search for baseline runs with `bbox search runs`.
2. Fork or update a branch with `bbox branch create --from-run`.
3. Start the new run with `bbox run start --idempotency-key`.
4. Log events, metrics, series, structured dataset snapshots, artifacts, and notes. Prefer `bbox dataset register` over hand-written data snapshot JSON.
5. Finish, fail, or cancel the run.
6. Compare candidate runs with `bbox compare runs` or `bbox batch compare`.
7. Write a decision note with `--author-type agent`.
8. Verify Dashboard, Search, Compare, Sweep, Branch, and Run Detail in WebUI.

For exact command examples, offline sync, retry policy, and WebUI verification checklist, read `references/agent-workflow.md`.

## Error Handling

On CLI failure, parse stderr as the standard envelope. Retry only when the error is likely transient (`NETWORK_ERROR`, transient `STORAGE_ERROR`, transport failures), and reuse the original idempotency key or `client_event_id`.

Do not retry unchanged requests on `VALIDATION_ERROR` or `STATE_ERROR`. Refresh IDs on `NOT_FOUND`. For batch commands, retry only failed items.

## Implementation Notes

- When adding new Blackbox capabilities, update this skill only with stable operational rules. Keep long command examples in `references/agent-workflow.md`.
- If a workflow changes in code, update the reference and run the skill validator.
