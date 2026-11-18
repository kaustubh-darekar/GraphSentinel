# GraphSentinel developer tasks. Works on macOS/Linux and on Windows (GNU Make).

ifeq ($(OS),Windows_NT)
  PY_BOOT ?= python
  VENV_PY := .venv/Scripts/python.exe
else
  PY_BOOT ?= python3
  VENV_PY := .venv/bin/python
endif

PY := "$(VENV_PY)"

.PHONY: setup dev dev-api dev-web serve test scenarios demo-store inspect proxy

## setup: create the venv, install Python deps (editable) and web deps
setup:
	$(PY_BOOT) -m venv .venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e ".[dev]"
	npm --prefix web install

## dev: run the API (port 8000) and the web app (port 5173) together
dev:
	$(MAKE) -j2 dev-api dev-web

# Single worker and no --reload: Relate allows one writable process per store.
dev-api:
	$(PY) -m uvicorn graphsentinel.api.main:app --host 127.0.0.1 --port 8000 --workers 1

dev-web:
	npm --prefix web run dev

## serve: build the web app once and serve UI + API together on http://127.0.0.1:8000
serve:
	npm --prefix web run build
	$(PY) -m uvicorn graphsentinel.api.main:app --host 127.0.0.1 --port 8000 --workers 1

## test: run the Python test suite
test:
	$(PY) -m pytest

## scenarios: replay every scenario in the terminal (no key needed)
scenarios:
	$(PY) -m graphsentinel.run --all

## demo-store: replay every scenario into stores/demo/ and export stores/demo.rl
demo-store:
	$(PY) -m graphsentinel.demo_store

## inspect: open the committed demo store read-only with the Relate CLI
inspect:
	relate query --read-only --database stores/demo

## proxy: guard real MCP servers (edit examples/servers.json first); UI on :8000
proxy:
	$(PY) -m graphsentinel.proxy --config examples/servers.json --policy examples/policy.mcp.yaml
