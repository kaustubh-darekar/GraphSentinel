// A new session, optionally started by a user message.
CREATE (s:Session {id: $id, title: $title, mode: $mode, lineage: $lineage,
                   scenario: $scenario, started_at: $at})
FOREACH (_ IN CASE WHEN $message IS NULL THEN [] ELSE [1] END |
  MERGE (u:User {name: $user})
  CREATE (u)-[:ASKED]->(m:Message {role: 'user', text: $message, at: $at})-[:STARTED]->(s)
  CREATE (s)-[:HAS_MESSAGE]->(m)
)
RETURN s.id AS id
