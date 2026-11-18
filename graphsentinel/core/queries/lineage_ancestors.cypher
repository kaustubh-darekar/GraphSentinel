// Every earlier call in the session whose data reaches this call (any number of hops).
MATCH (c:Call {id: $callId})
MATCH (src:Call {session: c.session})
WHERE src <> c
MATCH p = shortestPath((src)-[:PRODUCED|FED_INTO*1..40]->(c))
RETURN collect(src.id) AS ids
