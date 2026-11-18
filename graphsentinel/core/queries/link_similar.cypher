// Paraphrase lineage: Data whose meaning matches what the call is sending.
MATCH (c:Call {id: $callId})
UNWIND $rows AS r
MATCH (d:Data {id: r.id})
WHERE NOT (c)-[:PRODUCED]->(d) AND NOT (d)-[:FED_INTO]->(c)
MERGE (d)-[f:FED_INTO {how: 'similar'}]->(c)
SET f.score = r.score
RETURN d.id AS id, f.score AS score
