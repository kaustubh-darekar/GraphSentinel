// Delete every session (and its calls, data, messages, overrides) except the ids in $keep.
MATCH (s:Session)
WHERE NOT s.id IN $keep
OPTIONAL MATCH (s)-[:HAS_STEP]->(c:Call)
OPTIONAL MATCH (c)-[:PRODUCED]->(d:Data)
OPTIONAL MATCH (o:Override)-[:OVERRIDES]->(c)
OPTIONAL MATCH (s)-[:HAS_MESSAGE]->(m:Message)
WITH collect(DISTINCT s) + collect(DISTINCT c) + collect(DISTINCT d) + collect(DISTINCT o) + collect(DISTINCT m) AS doomed,
     count(DISTINCT s) AS sessions
FOREACH (n IN doomed | DETACH DELETE n)
RETURN sessions
