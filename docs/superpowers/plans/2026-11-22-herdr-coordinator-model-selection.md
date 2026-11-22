# Herdr Coordinator Model Selection

## Intent
Use a capable model (Fable-5.2 or Opus-5.5) as coordinator with faster models (Sonnet/Haiku) as helpers, leveraging Claude's token savings and contextual understanding.

## Goals
- Coordinator understands full project architecture.
- Helpers execute tasks quickly.
- History survives coordinator crash (persisted in Claude Code, not memory).
- Expandable to multiple coordinator tiers ("frontier agents").

## Constraints
- Coordinator crash = helpers survive (they report to their pane, not to coordinator's memory).
- Coordinator state = conversation history (claude.ai retains).
- No single point of failure: helpers do their work independently.

## Architecture

### Coordinator Tier (Fable/Opus)
- Full conversation history.
- Orchestrates tasks.
- Persists to claude.ai/chat history.

### Helper Tier (Sonnet/Haiku)
- Fast, cheap execution.
- Self-contained contracts.
- Report back via `<from:>` tags.

### Recovery (Coordinator death)
1. Helper continues working in its pane.
2. User can open `/claude` in browser, copy the thread context.
3. New coordinator spawned with same context.

## Implementation Steps

1. Update `coordinating-agents-in-herdr` skill to explicitly recommend Fable/Opus.
2. Add routing: `"coordinator": "claude-fable-5-2"`.
3. Document recovery procedure.
4. Test failure scenario (kill coordinator, validate helper survives).