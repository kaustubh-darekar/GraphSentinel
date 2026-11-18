// What the guard needs to know about the call itself.
MATCH (c:Call {id: $callId})-[:USED]->(t:Tool)
OPTIONAL MATCH (c)-[:SENT_TO]->(dst:Destination)
WITH c, t, collect(DISTINCT {address: dst.address, trusted: dst.trusted}) AS dests
OPTIONAL MATCH (o:Override)-[:OVERRIDES]->(c)
RETURN t:SendsOut AS sends_out, dests, collect(o.by) AS overrides
