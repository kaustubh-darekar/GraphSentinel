// What is needed to run a refused call later ("Allow once").
MATCH (c:Call {id: $callId})
RETURN c.step AS step, c.tool AS tool, c.args_json AS args_json,
       EXISTS { (c)-[:PRODUCED]->(:Data) } AS ran
