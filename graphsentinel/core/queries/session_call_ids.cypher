// Call ids of a session in step order.
MATCH (s:Session {id: $session})-[:HAS_STEP]->(c:Call)
WITH c ORDER BY c.step
RETURN collect(c.id) AS ids
