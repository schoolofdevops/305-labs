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

# --- KIND phase (M8+) settings ---------------------------------------------
# The Kubernetes phase runs its cluster with an ISOLATED kubeconfig so the lab
# never touches your default context. Every k8s target below writes/reads this
# file (gitignored). The cluster name matches kind-config.yaml.
KUBECONFIG_FILE ?= k8s/kubeconfig
KIND_CLUSTER    ?= opsmate
K8S_FREE_MB     ?= 3000       # KIND control-plane + one model pod need more headroom
                              # than the Compose model service — a higher floor here.

.PHONY: up down preflight registry-catalog k8s-up k8s-down

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

# ============================================================================
# KIND phase (M8-M13). The Compose verbs above are the Compose phase; these are
# the Kubernetes phase. ONE stack at a time — bring the Compose stack down
# (`make down`) before `make k8s-up`. The only Compose service that runs
# alongside KIND is `registry` (it IS the model source), started here.
#
#   make k8s-up    free-mem preflight -> ensure registry is up (model source)
#                  -> kind create (isolated kubeconfig) -> wait node Ready
#   make k8s-down  kind delete (registry data on ./data/zot PERSISTS)
# ============================================================================
k8s-up:
	@echo "==> KIND preflight (free memory) ..."
	@bash preflight.sh $(K8S_FREE_MB) || { \
	  echo "    Not enough free memory for the KIND phase. Close apps and retry."; exit 1; }
	@echo "==> Ensuring the registry (model source) is up on localhost:5100 ..."
	@mkdir -p ./data/zot
	@curl -fsS http://localhost:5100/v2/_catalog >/dev/null 2>&1 || $(COMPOSE) up -d registry
	@i=0; while [ $$i -lt 20 ]; do \
	  curl -fsS http://localhost:5100/v2/_catalog >/dev/null 2>&1 && break; \
	  sleep 1; i=$$((i+1)); done
	@curl -fsS http://localhost:5100/v2/_catalog >/dev/null 2>&1 || \
	  { echo "    Registry did not come up — M7 kits are the model source; run M7 first."; exit 1; }
	@echo "==> Creating the slim KIND cluster '$(KIND_CLUSTER)' (isolated kubeconfig: $(KUBECONFIG_FILE)) ..."
	@if kind get clusters 2>/dev/null | grep -qx "$(KIND_CLUSTER)"; then \
	  echo "    Cluster '$(KIND_CLUSTER)' already exists — reusing it."; \
	  kind export kubeconfig --name "$(KIND_CLUSTER)" --kubeconfig "$(KUBECONFIG_FILE)"; \
	else \
	  kind create cluster --config k8s/kind-config.yaml --kubeconfig "$(KUBECONFIG_FILE)"; \
	fi
	@echo "==> Waiting for the node to report Ready (up to 120s) ..."
	@kubectl --kubeconfig "$(KUBECONFIG_FILE)" wait --for=condition=Ready nodes --all --timeout=120s
	@echo "    Node Ready. Cluster is up. Your default context was NOT touched."
	@echo "    Use it with:  kubectl --kubeconfig $(KUBECONFIG_FILE) get nodes"

k8s-down:
	@echo "==> Deleting the KIND cluster '$(KIND_CLUSTER)' ..."
	@kind delete cluster --name "$(KIND_CLUSTER)" || true
	@rm -f "$(KUBECONFIG_FILE)"
	@echo "    Cluster gone. The registry and its data on ./data/zot PERSIST — the"
	@echo "    signed kits survive, so the next module re-creates the cluster and"
	@echo "    pulls the same 1.0.0 artifact. (Cluster create is ~30s — cheap by design.)"
