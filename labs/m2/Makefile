# M2 — Models, Quantization & the OpenAI-Compatible Contract. Ollama runs native
# on the host (Apple Silicon pattern, taught in M3). `make up` checks Ollama is
# reachable and the Q4 course model is pulled. `make down` removes the M2-only
# Q8 quant to reclaim disk; the Q4 course model stays for M3.

OLLAMA_URL ?= http://127.0.0.1:11434
MODEL ?= qwen3:0.6b
Q8_MODEL ?= qwen3:0.6b-q8_0

.PHONY: up down

up:
	@echo "==> Checking Ollama is running at $(OLLAMA_URL) ..."
	@curl -s --max-time 3 $(OLLAMA_URL)/api/version >/dev/null 2>&1 \
		|| { echo "Ollama is NOT reachable. Start it: 'ollama serve' or the desktop app."; exit 1; }
	@echo "    Ollama is up."
	@echo "==> Checking the course model $(MODEL) (Q4_K_M) is pulled ..."
	@ollama list | grep -q "$(MODEL)" \
		|| { echo "Model $(MODEL) not found. Pull it: ollama pull $(MODEL)"; exit 1; }
	@echo "    $(MODEL) is present. You are ready for the lab."

down:
	@echo "==> Removing the M2-only quant $(Q8_MODEL) (reclaims ~832 MB) ..."
	@ollama rm $(Q8_MODEL) >/dev/null 2>&1 || true
	@echo "    Removed (or already absent). The Q4 course model $(MODEL) stays for M3."
	@echo "Ollama keeps running as your host model server."
