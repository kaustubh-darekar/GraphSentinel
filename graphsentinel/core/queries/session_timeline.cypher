// Messages and calls of a session, for rebuilding the chat.
MATCH (s:Session {id: $session})
OPTIONAL MATCH (s)-[:HAS_MESSAGE]->(m:Message)
WITH s, collect({kind: 'message', role: m.role, text: m.text, at: m.at}) AS msgs
OPTIONAL MATCH (s)-[:HAS_STEP]->(c:Call)
OPTIONAL MATCH (c)-[:PRODUCED]->(d:Data)
WITH s, msgs, c, head(collect(d)) AS out
WITH s, msgs, collect(CASE WHEN c IS NULL THEN NULL ELSE {
  kind: 'call', id: c.id, step: c.step, tool: c.tool, label: c.label, args_json: c.args_json,
  at: c.at, decision: c.decision, reason: c.reason, resolution: c.resolution, path: c.path,
  output: out.preview, output_chars: out.chars
} END) AS calls
RETURN s {.id, .title, .mode, .lineage, .scenario, .started_at} AS session, msgs, calls
