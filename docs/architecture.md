# GraphSentinel architecture

How a tool call travels through GraphSentinel, and why each part is built the way it is.

```
agent (scripted, live LLM, or MCP client)
   │  tool call
   ▼
GuardedSession.call()                      graphsentinel/agent/guarded.py
   ├─ Recorder.record_call()   → (:Call)-[:USED]->(:Tool), (:Call)-[:SENT_TO]->(:Destination)
   ├─ Recorder.link_inputs()   → (:Data)-[:FED_INTO {how}]->(:Call)
   ├─ Recorder.link_similar()  → vector search, precise mode, Sends out calls only
   ├─ Guard.check()            → Allow / Ask / Block + path
   ├─ Allow → run the tool, Recorder.record_output() → (:Call)-[:PRODUCED]->(:Data)
   ├─ Ask   → wait for a human (UI or terminal), deny on timeout
   └─ Block → refuse; the agent gets the reason
   │
   └─ every step is published as an event → WebSocket → UI
```

## 1. Store

`GraphStore` (`core/store.py`) opens Relate in **directory** mode and owns the connection on a
single worker thread, because Relate connections are thread-affine. Every other thread submits
work through a queue and waits on a `Future`. The schema (`core/schema.cypher`) is idempotent
and runs at every start: unique ids, session indexes, and the `data_vec` vector index.

Directory mode was chosen because sessions must survive restarts and stay inspectable: the
committed `stores/demo/` opens directly with the `relate` CLI, and `relate clone` exports it to a
single `stores/demo.rl` file.

## 2. Policy

`policy.yaml` tags each tool as Outside, Private and/or Sends out, names the arguments that hold
destinations, and picks the argument used as a short label. At startup the tags become labels on
`:Tool` nodes, so the guard can ask the graph directly (`t:Outside`).

## 3. Recording and lineage

Each call is recorded before it runs. Then the data that could have influenced it is linked:

| Mode | Linked data | Edge |
|---|---|---|
| strict | everything already in the agent's context | `FED_INTO {how: 'context'}` |
| precise | data whose 8-word shingle hashes overlap the call's arguments | `FED_INTO {how: 'content'}` |
| precise, Sends out calls | data whose meaning matches a paragraph of the outgoing text | `FED_INTO {how: 'similar', score}` |

Strict mode is the safe default: an agent can be steered by anything it has read. Precise mode
trades that for fewer questions, and uses fingerprints and vector search so that copying or
rewording private data is still caught.

## 4. The guard

`Guard.check()` (`core/guard.py`) runs two read-only queries:

1. **Context:** is this a Sends out call, where is it going, is any destination untrusted, and
   has a human already allowed it once?
2. **Lineage** (`core/queries/guard_lineage.cypher`): every Outside or Private call in the
   session whose data reaches this call, with one concrete chain each.

The lineage query uses a breadth-first `shortestPath` per source. A path-enumerating quantified
pattern expresses the same question, but in strict mode every earlier data item feeds every
later call, so the number of distinct paths grows exponentially (about 0.9 s at 16 calls in our
measurements). Reachability needs only one path per source, which BFS finds in linear time
(about 2 ms at 200 calls and 19,900 edges). The quantified pattern is still used where it reads
best: the console presets and the README queries.

Decision table:

| Lineage | Untrusted destination | Decision |
|---|---|---|
| Outside and Private | yes | Block |
| Outside or Private | yes | Ask |
| otherwise | | Allow |

The verdict's `path` joins the chains end to end; each consecutive pair inside a chain is a real
edge, which is what the UI highlights.

## 5. Paraphrase detection

Every `:Data` item in a precise session gets an embedding stored as a `vector(...)` property. On
a Sends out call, each paragraph of the outgoing text is searched against the session's data:

```cypher
MATCH (d:Data)
SEARCH d IN (VECTOR INDEX data_vec FOR vector($q, $dims, FLOAT32) WHERE d.session = $session LIMIT 5)
SCORE AS score
RETURN d.id AS id, score
```

Matches above the embedder's threshold become ordinary lineage edges, so the guard needs no
special case. Three embedders are available:

- **OpenAI** (`OPENAI_EMBED_MODEL`, 256 dimensions), threshold 0.85, for live sessions;
- **cached** vectors stored in a scenario file, so scripted replays need no key;
- a **built-in lexical** embedder (hashed words and word pairs), threshold 0.70, when nothing
  else is configured.

## 6. Runners

All runners go through the same `GuardedSession`, so the guard behaves identically everywhere:

- **Scripted** (`runner_scripted.py`) replays `scenarios/*.yaml`. Each tool step can state the
  expected decision, which the CLI and tests check.
- **Live** (`runner_live.py`) is an OpenAI chat-completions tool-calling loop with a deliberately
  naive system prompt.
- **MCP proxy** (`proxy/`) exposes real MCP servers' tools to any MCP client and guards every call.

## 7. API and UI

FastAPI (`api/`) runs agent sessions in background threads and streams their events over a
WebSocket: a snapshot first, then each change. Asks wait on a threading event that the UI's
Allow / Deny resolves. The Cypher console runs read-only queries in a transaction that is
always rolled back.

The React UI (`web/`) keeps a reducer per session, renders the chat and the live Cytoscape
graph, and highlights a verdict's path on request.

## 8. Testing

`make test` covers every guard rule, both lineage modes, a ten-step multi-hop chain, all
scenarios, the API and WebSocket, the read-only console, paraphrase detection (including that it
is the only reason scenario 05 is blocked), and the MCP proxy end to end over stdio. A timing
test prints the `check()` latency on a 200-call session.

## What's next

- Per-destination policies (for example, allow Private data to a specific partner domain).
- Faster recording for very long strict sessions.
- A policy editor in the UI.
