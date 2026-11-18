// Append a call as the next step of its session.
MATCH (s:Session {id: $session})
MERGE (t:Tool {name: $tool})
WITH s, t
OPTIONAL MATCH (s)-[:HAS_STEP]->(prev:Call)
WITH s, t, count(prev) AS n
CREATE (s)-[:HAS_STEP]->(c:Call {
  id: $id, session: $session, step: n + 1, tool: $tool, label: $label,
  args_json: $args_json, at: $at
})
CREATE (c)-[:USED]->(t)
RETURN c.step AS step
