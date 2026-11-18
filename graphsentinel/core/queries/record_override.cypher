// A human "Allow once" on a blocked call.
MATCH (c:Call {id: $callId})
CREATE (o:Override {by: $by, at: $at, note: $note})-[:OVERRIDES]->(c)
