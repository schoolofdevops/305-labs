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

.PHONY: up down preflight

preflight:
	@bash preflight.sh

up: preflight
	@echo "==> Starting the OpsMate stack ..."
	@# Ensure the Chroma bind-mount source exists before compose starts. On a
	@# fresh clone this directory is absent; some Docker setups fail to create
	@# and chown a missing bind source, so create it ourselves (M4+ uses it).
	@mkdir -p ./data/chroma
	@$(COMPOSE) up -d
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
