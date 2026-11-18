// Data that flowed between the given calls.
UNWIND $callIds AS cid
MATCH (a:Call {id: cid})-[:PRODUCED]->(d:Data)-[f:FED_INTO]->(b:Call)
WHERE b.id IN $callIds
RETURN a.id AS from_call, d.id AS data, d.preview AS preview, d.chars AS chars,
       f.how AS how, f.score AS score, b.id AS to_call
