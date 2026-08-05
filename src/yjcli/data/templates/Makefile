# Platform targets are discovered from */scripts/run.sh (after yjcli platform add).
# Usage:
#   make <platform>                 # all services under that platform (concurrent)
#   make <platform> NAME=<service>  # one service
# Extend this root file for repository-owned work when needed. A useful pattern
# is <platform>-<action> with the same optional NAME selector, for example
# `make backend-deploy [NAME=api]`. yjcli does not define those actions.

PLATFORMS := $(patsubst %/scripts/run.sh,%,$(wildcard */scripts/run.sh))

.PHONY: help $(PLATFORMS)

help:
	@echo "Usage:"
	@echo "  make <platform>                 # start all services concurrently"
	@echo "  make <platform> NAME=<service>  # start one service"
	@echo ""
	@echo "Available platforms (dirs with scripts/run.sh):"
	@if [ -z "$(PLATFORMS)" ]; then \
		echo "  (none — run: yjcli platform add)"; \
	else \
		for p in $(PLATFORMS); do echo "  $$p"; done; \
	fi
	@echo ""
	@echo "Example: make backend"
	@echo "         make backend NAME=api"

$(PLATFORMS):
	@test -x "$@/scripts/run.sh" || (echo "missing: $@/scripts/run.sh"; exit 1)
	@if [ -n "$(NAME)" ]; then \
		"$@/scripts/run.sh" "$(NAME)" $(ARGS); \
	else \
		"$@/scripts/run.sh" $(ARGS); \
	fi
