// The data a call returned to the agent.
MATCH (c:Call {id: $callId})
CREATE (c)-[:PRODUCED]->(d:Data {
  id: $id, session: c.session, preview: $preview, chars: $chars, fp: $fp
})
RETURN d.id AS id
