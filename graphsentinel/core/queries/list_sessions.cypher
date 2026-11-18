// Sessions, newest first, with step counts and the worst decision seen.
MATCH (s:Session)
OPTIONAL MATCH (s)-[:HAS_STEP]->(c:Call)
WITH s, count(c) AS steps,
     sum(CASE WHEN c.decision = 'block' THEN 1 ELSE 0 END) AS blocks,
     sum(CASE WHEN c.decision = 'ask' THEN 1 ELSE 0 END) AS asks
RETURN s.id AS id, s.title AS title, s.mode AS mode, s.lineage AS lineage,
       s.scenario AS scenario, s.started_at AS started_at, steps, blocks, asks
ORDER BY started_at DESC
