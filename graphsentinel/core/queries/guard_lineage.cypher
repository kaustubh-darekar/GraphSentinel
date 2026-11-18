// Lineage sources of a call: every Outside or Private call in the same session whose
// data reaches it through (:Call)-[:PRODUCED]->(:Data)-[:FED_INTO]->(:Call) hops
// (up to 20 hops = 40 relationships), with one concrete chain per source.
//
// Uses shortestPath (a BFS) rather than a path-enumerating quantified pattern:
// strict mode links every earlier Data to every later Call, so the number of
// distinct paths grows exponentially with session length, while BFS stays linear.
MATCH (c:Call {id: $callId})
MATCH (src:Call {session: c.session})-[:USED]->(t:Tool)
WHERE src <> c AND (t:Outside OR t:Private)
MATCH p = shortestPath((src)-[:PRODUCED|FED_INTO*1..40]->(c))
RETURN src.id AS src, src.step AS step, src.label AS label, src.tool AS tool,
       t:Outside AS outside, t:Private AS private, [n IN nodes(p) | n.id] AS path
ORDER BY step
