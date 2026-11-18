/** Ready-made read-only queries for the Cypher console. `$session` is the open session. */
export interface Preset {
  title: string;
  query: string;
  needsSession?: boolean;
}

export const PRESETS: Preset[] = [
  {
    title: "Why was this call blocked?",
    needsSession: true,
    query: `// Every Outside or Private source behind each blocked call, with the path it took
MATCH (c:Call {session: $session, decision: 'block'})
MATCH (src:Call {session: $session})-[:USED]->(t:Tool)
WHERE src <> c AND (t:Outside OR t:Private)
MATCH p = shortestPath((src)-[:PRODUCED|FED_INTO*1..40]->(c))
RETURN c.step AS blocked_step, src.step AS from_step, src.tool AS source,
       [l IN labels(t) WHERE l <> 'Tool'] AS tags,
       [n IN nodes(p) | coalesce(n.tool, left(n.preview, 40))] AS path`,
  },
  {
    title: "Lineage with a quantified path pattern",
    needsSession: true,
    query: `// Multi-hop lineage of each Sends out call, written as one quantified path pattern
MATCH (c:Call {session: $session})-[:USED]->(:SendsOut)
MATCH (src:Call)((:Call)-[:PRODUCED]->(:Data)-[:FED_INTO]->(:Call)){1,6}(c)
MATCH (src)-[:USED]->(t:Tool)
RETURN c.step AS send_step, c.tool AS send,
       collect(DISTINCT CASE WHEN t:Outside THEN src.tool END) AS outside,
       collect(DISTINCT CASE WHEN t:Private THEN src.tool END) AS private`,
  },
  {
    title: "All sends out today",
    query: `// Every Sends out call today, where it went, and what the guard decided
MATCH (c:Call)-[:USED]->(:SendsOut)
WHERE c.at >= toString(date())
OPTIONAL MATCH (c)-[:SENT_TO]->(d:Destination)
RETURN c.at AS at, c.tool AS tool, d.address AS destination, d.trusted AS trusted,
       c.decision AS decision, c.resolution AS resolution
ORDER BY at DESC`,
  },
  {
    title: "Paraphrase matches (vector search)",
    query: `// Data linked to a send by meaning (vector similarity), not by copied text
MATCH (d:Data)-[f:FED_INTO {how: 'similar'}]->(c:Call)
MATCH (src:Call)-[:PRODUCED]->(d)
RETURN c.session AS session, c.step AS send_step, src.tool AS source,
       round(f.score, 3) AS score, left(d.preview, 60) AS data`,
  },
  {
    title: "Tools and their risk tags",
    query: `MATCH (t:Tool)-[:PART_OF]->(s:Server)
RETURN s.name AS server, t.name AS tool, [l IN labels(t) WHERE l <> 'Tool'] AS tags
ORDER BY server, tool`,
  },
  {
    title: "Human overrides",
    query: `MATCH (o:Override)-[:OVERRIDES]->(c:Call)
RETURN o.at AS at, o.by AS by, c.tool AS tool, c.label AS label, c.reason AS reason
ORDER BY at DESC`,
  },
  {
    title: "Graph size",
    query: `MATCH (n) RETURN labels(n)[0] AS label, count(*) AS nodes ORDER BY nodes DESC`,
  },
];
