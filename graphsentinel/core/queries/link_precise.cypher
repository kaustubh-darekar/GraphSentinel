// precise lineage: only Data whose shingle hashes overlap the call's arguments.
MATCH (c:Call {id: $callId})
MATCH (d:Data {session: c.session})
WHERE NOT (c)-[:PRODUCED]->(d) AND any(h IN d.fp WHERE h IN $hashes)
MERGE (d)-[:FED_INTO {how: 'content'}]->(c)
RETURN d.id AS id
