# GraphSentinel: project guide

> **See the connections, Stop the threats.**
> Graph-powered security for autonomous AI agents.

This guide describes how the project is put together and the conventions to follow when
changing it. How the pieces work in more depth: [`docs/architecture.md`](docs/architecture.md).

## The idea

An AI agent becomes dangerous when one session combines **the risky three**:
1. it reads **Outside** content (an email, a web page) that may hide instructions,
2. it reads **Private** data (files, inbox, secrets),
3. it can **Send out** (email, Slack, HTTP).

GraphSentinel records every tool call and every piece of data as a graph in **Relate**, the
embedded graph database, running inside the agent process. Before any Sends out call it walks
the data's history (lineage) backwards. If the outgoing data traces back to both Outside and
Private sources and the destination isn't trusted, the call is **blocked** and the exact path
is shown as the reason.

Vocabulary used everywhere (code, UI, docs): **Outside**, **Private**, **Sends out**,
**the risky three**, **lineage**, **Allow / Ask / Block**. User-facing text avoids security
jargon such as "exfiltration" or "taint".

## Why an embedded graph database

- The check runs before every tool call, so it lives in-process with no server round trip.
  Target: under 5 ms per check.
- Multi-hop lineage is a path question, answered by one Cypher query instead of recursive
  application code.
- Each session is kept in a durable store that anyone can open and query.
- Vector search on the same graph catches reworded (paraphrased) leaks.
- Storage mode is **directory** (`stores/graphsentinel/`): durable, inspectable with the
  `relate` CLI, and exportable to a single `.rl` file with `relate clone`.

## Tech stack

- **Python 3.11+**, `relate-db` (import `relate`), `fastapi`, `uvicorn[standard]`, `openai`,
  `pydantic`, `pyyaml`, `python-dotenv`, `pytest`, `mcp` (proxy).
- **Web:** React + Vite + TypeScript + Tailwind CSS, `cytoscape` + `cytoscape-dagre`,
  `cmdk` for the command palette, `lucide-react` icons.
- No external database or credentials: Relate is embedded.

## Configuration (`.env`, never committed; `.env.example` is the template)

```
OPENAI_API_KEY=            # live mode only
OPENAI_MODEL=              # chat model for live mode (configured, never hard-coded)
OPENAI_EMBED_MODEL=        # embeddings for paraphrase detection in live precise sessions
GS_MODE=scripted           # scripted (no key, deterministic) | live (real LLM)
GS_STORE_PATH=./stores/graphsentinel
GS_TRUSTED_DESTINATIONS=*@acme.test,#internal*   # wildcards: whole domain, channel prefix
GS_LINEAGE_MODE=strict     # strict (anything in context counts) | precise (copied or similar content)
```

Scripted mode must always work with **no API key**, so anyone can run the demo.

## Repository layout (small modules, one job each)

```
graphsentinel/
  core/                     # the guard library; no web or LLM imports
    store.py                # GraphStore: owns the Relate connection on one worker thread
    schema.cypher           # constraints and indexes, run at startup (idempotent)
    policy.py               # tool risk tags from policy.yaml
    recorder.py             # writes sessions, calls, data and lineage edges
    fingerprint.py          # text -> shingle hashes, for content matching
    embedding.py            # embedders for vector search
    guard.py                # check(call) -> Verdict(decision, reason, path)
    lineage.py              # explain(call_id) and session graphs for the UI
    queries/*.cypher        # every Cypher query, one file each, loaded by name
  agent/
    tools/                  # sandbox tools: email, files, web, slack, calc
    sandbox_data/           # fake inbox, files and web pages
    guarded.py              # record -> check -> run or refuse (shared by every runner)
    runner_live.py          # OpenAI tool-calling loop
    runner_scripted.py      # replays scenario YAML through the same guarded path
  api/                      # FastAPI REST + WebSocket, read-only Cypher console
  proxy/                    # MCP proxy in front of real MCP servers
policy.yaml                 # tool -> [outside, private, sends_out]
scenarios/*.yaml            # demo scenarios
stores/demo/                # committed demo store (`make demo-store`)
web/                        # React app
tests/
Makefile                    # setup, dev, serve, test, scenarios, demo-store, inspect, proxy
```

## Graph model

```
(:Session {id, title, mode, lineage, started_at})
(:Session)-[:HAS_STEP]->(:Call {id, step, tool, label, args_json, at, decision, reason, path})
(:Call)-[:USED]->(:Tool {name})-[:PART_OF]->(:Server {name})
  Tool labels from policy.yaml: :Outside  :Private  :SendsOut
(:Call)-[:PRODUCED]->(:Data {id, preview, chars, fp, embedding})
(:Data)-[:FED_INTO {how, score}]->(:Call)                  # how: 'context' | 'content' | 'similar'
(:Call)-[:SENT_TO]->(:Destination {address, trusted})
(:User)-[:ASKED]->(:Message {role, text})-[:STARTED]->(:Session)
(:Override {by, at, note})-[:OVERRIDES]->(:Call)          # human "Allow once" on a block
```

### Lineage rules

- `strict`: every Data item already in the agent's context gets `FED_INTO {how:'context'}`
  to the next call.
- `precise`: only Data whose shingle hashes overlap the call's arguments gets
  `FED_INTO {how:'content'}`; on Sends out calls, vector search adds `FED_INTO {how:'similar'}`.

### The guard rule (`guard.py`)

For a call to a `:SendsOut` tool:
- **Block** if its lineage includes an `:Outside` call AND a `:Private` call AND a destination
  is not trusted.
- **Ask** if the lineage includes Outside or Private (but not both) and a destination isn't trusted.
- **Allow** otherwise, including Private data going to a trusted destination.

Calls that don't send data out are always allowed and always recorded. `Verdict.path` holds the
concrete chain (call and data ids) that the UI highlights.

The lineage query (`core/queries/guard_lineage.cypher`) runs one breadth-first `shortestPath`
per Outside or Private source in the session. In strict mode every earlier Data item feeds
every later call, so the number of distinct paths grows exponentially; BFS keeps the check
linear. Quantified path patterns are used where they read best: the console presets and the
README queries.

## Working with Relate

1. **Thread affinity.** A Relate connection is bound to the thread that opened it, so
   `GraphStore` owns one worker thread that runs every query from a queue
   (`submit(query, params) -> Future`). Nothing else imports `relate` directly.
2. **One writer per store.** The API runs with `--workers 1` and without `--reload`. The MCP
   proxy serves the UI from its own process rather than opening the store twice. Inspect a
   store with `relate query --read-only` or `relate serve --read-only`.
3. **Vector search:** `MATCH (d:Data) SEARCH d IN (VECTOR INDEX data_vec FOR vector($q, $dims, FLOAT32)
   WHERE d.session = $s LIMIT 5) SCORE AS score RETURN d, score`. The score is `(1 + cosine) / 2`.
4. **Conditional labels:** `FOREACH (_ IN CASE WHEN cond THEN [1] ELSE [] END | SET n:Label)`.
5. **Batching:** use `UNWIND $rows AS r ...` for bulk writes; each autocommit statement is one fsync.
6. **Read-only console:** queries are keyword-filtered and always run in a transaction that is
   rolled back.

## Code conventions

- Small files, small functions, type hints, docstrings on public functions.
- No Cypher strings in Python: every query lives in `core/queries/*.cypher`.
- `core/` stays importable and testable without FastAPI, OpenAI or a browser.
- Every guard behaviour has a pytest case; run `make test` before calling a change done.
- Never log or display API keys. Sandbox data is fake: `.test` domains and fake names.

## UI: light precision (Linear / Raycast style)

Calm, dense, keyboard-first. No gradients or glassmorphism, no emoji, no bouncy animation.
Primary colours: sky blue and cloudy white; amber red only for Block / Sends out.

Design tokens (CSS variables in `web/src/index.css`, mirrored in `web/src/lib/tokens.ts`):
```
--bg:        #F4F8FC     --surface:   #FDFDFE (cloudy white)   --surface-2: #EEF4FA
--border:    #DCE4EE     --text:      #0E1A2B     --muted:     #5D6B7E
--accent:    #0099FF     (sky blue: focus rings, primary buttons)
--outside:   #C77700     (amber)   --private: #7C4DDB (violet)
--sendsout:  #E4572E     (amber red)  --allow: #1F9D55 (green)   --ask: #C77700
Font: Inter (UI), JetBrains Mono (ids, args, Cypher). Text 12px minimum, 13-14px body,
6px radius, 1px borders, spacing scale 4/8/12/16/24/32, 150ms ease-out transitions only.
```

Layout (one screen, three columns):
- **Left:** logo and tagline, scenarios with one-line descriptions, recent runs (with
  Clear history), mode and the ⌘K hint.
- **Center:** the agent chat. Consecutive tool calls are grouped in one card, each row showing
  the tool, a readable label and a verdict pill. A Block shows an inline card ("Blocked: data
  from **Outside** (inbox) and **Private** (salaries.xlsx) was about to go to
  `audit@ext-review.test`") with *Show path* and *Allow once* (creates an `:Override`).
- **Right (resizable):** live Cytoscape graph, dagre top-to-bottom layout (reads in the same
  order as the chat). Node colour by tag (Outside amber, Private violet, Sends out amber-red
  border); data nodes small and grey. A shown path glows; everything else dims to 30%.
- **⌘K palette:** run a scenario, switch strict/precise, open the Cypher console, export a
  session, clear history.
- **Cypher console (bottom drawer):** read-only queries against the live graph, with presets.
