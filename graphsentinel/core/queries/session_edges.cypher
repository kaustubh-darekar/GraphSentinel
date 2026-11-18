// All data produced by the given calls, and where each item flowed (to_call may be null).
UNWIND $callIds AS cid
MATCH (a:Call {id: cid})-[:PRODUCED]->(d:Data)
OPTIONAL MATCH (d)-[f:FED_INTO]->(b:Call)
RETURN a.id AS from_call, d.id AS data, d.preview AS preview, d.chars AS chars,
       f.how AS how, f.score AS score, b.id AS to_call
