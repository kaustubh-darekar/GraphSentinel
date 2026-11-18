// MERGE each tool and its server, then reset its risk labels from policy.yaml.
UNWIND $rows AS r
MERGE (s:Server {name: r.server})
MERGE (t:Tool {name: r.name})
MERGE (t)-[:PART_OF]->(s)
REMOVE t:Outside, t:Private, t:SendsOut
FOREACH (_ IN CASE WHEN r.outside THEN [1] ELSE [] END | SET t:Outside)
FOREACH (_ IN CASE WHEN r.private THEN [1] ELSE [] END | SET t:Private)
FOREACH (_ IN CASE WHEN r.sends_out THEN [1] ELSE [] END | SET t:SendsOut)
