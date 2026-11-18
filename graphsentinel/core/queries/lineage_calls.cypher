// Call nodes for the UI, with their tool tags and destinations.
UNWIND $callIds AS cid
MATCH (c:Call {id: cid})-[:USED]->(t:Tool)
OPTIONAL MATCH (c)-[:SENT_TO]->(dst:Destination)
WITH c, t, collect(dst) AS dsts
RETURN c.id AS id, c.step AS step, c.tool AS tool, c.label AS label,
       c.decision AS decision, c.reason AS reason, c.resolution AS resolution, c.path AS path,
       t:Outside AS outside, t:Private AS private, t:SendsOut AS sends_out,
       [d IN dsts | {address: d.address, trusted: d.trusted}] AS destinations
ORDER BY c.step
