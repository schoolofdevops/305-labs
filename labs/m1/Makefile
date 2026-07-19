# M1 — How LLMs Work. Ollama runs native on the host (Apple Silicon pattern,
# taught properly in M3). There is no container stack yet, so `make up` only
# checks that Ollama is reachable and the course model is pulled.

OLLAMA_URL ?= http://127.0.0.1:11434
MODEL ?= qwen3:0.6b

.PHONY: up down

up:
	@echo "==> Checking Ollama is running at $(OLLAMA_URL) ..."
	@curl -s --max-time 3 $(OLLAMA_URL)/api/version >/dev/null 2>&1 \
		|| { echo "Ollama is NOT reachable. Start it: 'ollama serve' or the desktop app."; exit 1; }
	@echo "    Ollama is up."
	@echo "==> Checking the course model $(MODEL) is pulled ..."
	@ollama list | grep -q "$(MODEL)" \
		|| { echo "Model $(MODEL) not found. Pull it: ollama pull $(MODEL)"; exit 1; }
	@echo "    $(MODEL) is present. You are ready for the lab."

down:
	@echo "Nothing to tear down for M1 — Ollama runs native and no containers were started."
	@echo "The model unloads itself after the keep-alive window (about 5 minutes idle)."
	@echo "To free its memory now: ollama stop $(MODEL)"
