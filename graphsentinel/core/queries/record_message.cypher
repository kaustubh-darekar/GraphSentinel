// A chat message in the session (role: 'user' | 'agent').
MATCH (s:Session {id: $session})
CREATE (s)-[:HAS_MESSAGE]->(m:Message {role: $role, text: $text, at: $at})
RETURN m.at AS at
