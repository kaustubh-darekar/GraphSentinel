// After clearing: destinations no call sends to, and users who asked nothing.
OPTIONAL MATCH (d:Destination) WHERE NOT ()-[:SENT_TO]->(d)
OPTIONAL MATCH (u:User) WHERE NOT (u)-[:ASKED]->()
WITH collect(DISTINCT d) + collect(DISTINCT u) AS orphans
FOREACH (n IN orphans | DETACH DELETE n)
