# Design: Persistent Contract & Agent Occupancy

## Intent
Persist assistant contracts as JSON audit logs for recovery. Track agent occupancy via ephemeral cache — NOT a persistent JSON registry (race conditions).

## Storage Location
Contratos: `.claude/herdr/contracts/<session-id>.json` (estruturado, auditável).
Occupancy: `<tmpdir>/herdr-occupancy.json` (cache de 30s, invalidado ao ler `herdr` commands).

## Schema: Contrato Persistido
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "pane_id": "wP:pN",
  "project": "my-project",
  "role": "reviewer-1",
  "created_at": "2026-11-22T15:30:00Z",
  "status": "active",
  "contract": { "role", "context", "task", "limits", "format", "return" }
}
```

## Schema: Occupancy (Cache Temporal)
Chave: `pane_id → {role, status, session_id, updated_at}`. TTL: 30s.

## Implementation (Skill Update)
- **Flow Step 3**: Salvar contrato em `.claude/herdr/contracts/<session_id>.json`.
- **Flow Step 9**: Se `resume` falhar, ler contrato JSON para recriar helper sem prompts do usuário.
- **"Where am I"**: Sempre consultar `herdr pane list`, `herdr agent list` como fonte primária. Usar `<tmpdir>/herdr-occupancy.json` apenas como cache rápido.

## Anti-Pattern Investigado
**Não usar `.claude/herdr-registry.json` como mapa de ocupação.**  
- Corrida de condições (concorrência).
- JSON não atômico → dados corrompidos.
- Herdr já sincroniza `~/.config/herdr/session.json` a cada 5s.
- A skill já usa `<tmpdir>/herdr-helpers.md` para persistência robusta de session-id.

Fonte: Análise do investigador (`cavecrew-investigator`) sobre concorrência e consistência.

## Status
Done. Skills atualizadas com persistência de contrato e política de roteamento.