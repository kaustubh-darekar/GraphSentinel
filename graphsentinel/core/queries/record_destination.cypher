// Where a Sends out call is going, and whether that address is trusted.
MATCH (c:Call {id: $callId})
UNWIND $dests AS dst
MERGE (d:Destination {address: dst.address})
SET d.trusted = dst.trusted
MERGE (c)-[:SENT_TO]->(d)
