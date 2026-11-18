// strict lineage: every Data already in the session's context feeds the call.
MATCH (c:Call {id: $callId})
MATCH (d:Data {session: c.session})
WHERE NOT (c)-[:PRODUCED]->(d)
MERGE (d)-[:FED_INTO {how: 'context'}]->(c)
RETURN d.id AS id
