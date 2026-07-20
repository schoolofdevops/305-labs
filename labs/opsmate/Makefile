# ============================================================================
# OpsMate spine — make targets that carry from M3 to M13.
#
#   make up        preflight (free-memory + model-file check) → compose up →
#                  wait until the model service reports healthy
#   make down      stop and remove the stack (the GGUF on disk stays for M4+)
#   make preflight run only the safety check
#
# The stack grows per module; these two verbs do not. Every module you run the
# same `make up` and it brings up whatever services this file has grown to hold.
# ============================================================================

# Prefer the compose v2 plugin; fall back to the standalone docker-compose
# binary automatically (some runtimes ship only one of the two).
COMPOSE ?= $(shell docker compose version >/dev/null 2>&1 && echo "docker compose" || echo "docker-compose")
HEALTH_URL ?= http://127.0.0.1:8080/health
WAIT_SECONDS ?= 90

.PHONY: up down preflight registry-catalog

preflight:
	@bash preflight.sh

up: preflight
	@echo "==> Starting the OpsMate stack ..."
	@# Ensure the bind-mount sources exist before compose starts. On a fresh clone
	@# these directories are absent; some Docker setups fail to create and chown a
	@# missing bind source, so create them ourselves (Chroma from M4, Zot from M7).
	@mkdir -p ./data/chroma ./data/zot
	@$(COMPOSE) up -d --build
	@echo "==> Waiting for the model service to report healthy (up to $(WAIT_SECONDS)s) ..."
	@i=0; \
	while [ $$i -lt $(WAIT_SECONDS) ]; do \
	  if curl -fsS --max-time 2 $(HEALTH_URL) >/dev/null 2>&1; then \
	    echo "    Model service is healthy at $(HEALTH_URL)."; \
	    echo "    Stack is up. Try:  curl -s $(HEALTH_URL)"; \
	    exit 0; \
	  fi; \
	  sleep 2; i=$$((i+2)); \
	done; \
	echo "    Model service did not become healthy in $(WAIT_SECONDS)s."; \
	echo "    Check logs:  $(COMPOSE) logs model"; \
	exit 1

# M7: a one-line look at what the local registry holds — repositories and, for the
# model repo, its tags. Handy after a push and as the "is the registry up?" probe.
registry-catalog:
	@curl -fsS http://localhost:5100/v2/_catalog || \
	  { echo "registry not reachable at localhost:5100 — is the stack up? (make up)"; exit 1; }
	@echo
	@curl -fsS http://localhost:5100/v2/opsmate/model/tags/list 2>/dev/null || true
	@echo
	@echo "==> Waiting for the model service to report healthy (up to $(WAIT_SECONDS)s) ..."
	@i=0; \
	while [ $$i -lt $(WAIT_SECONDS) ]; do \
	  if curl -fsS --max-time 2 $(HEALTH_URL) >/dev/null 2>&1; then \
	    echo "    Model service is healthy at $(HEALTH_URL)."; \
	    echo "    Stack is up. Try:  curl -s $(HEALTH_URL)"; \
	    exit 0; \
	  fi; \
	  sleep 2; i=$$((i+2)); \
	done; \
	echo "    Model service did not become healthy in $(WAIT_SECONDS)s."; \
	echo "    Check logs:  $(COMPOSE) logs model"; \
	exit 1

down:
	@echo "==> Stopping the OpsMate stack ..."
	@$(COMPOSE) down
	@echo "    Stopped. The GGUF model file on disk stays for the next module."
