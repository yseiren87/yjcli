# Platform targets are discovered from */scripts/run.sh (after yjcli platform add).
# Usage:
#   make <platform>                 # all services under that platform (concurrent)
#   make <platform> NAME=<service>  # one service
# Deploy templates are platform-owned extension points. They intentionally fail
# until the repository implements the printed build/package/upload steps.

PLATFORMS := $(patsubst %/scripts/run.sh,%,$(wildcard */scripts/run.sh))
DEPLOY_DEVELOPMENT_TARGETS := $(addsuffix -deploy-development,$(PLATFORMS))
DEPLOY_PRODUCTION_TARGETS := $(addsuffix -deploy-production,$(PLATFORMS))

.PHONY: help $(PLATFORMS) $(DEPLOY_DEVELOPMENT_TARGETS) $(DEPLOY_PRODUCTION_TARGETS)

help:
	@echo "Usage:"
	@echo "  make <platform>                 # start all services concurrently"
	@echo "  make <platform> NAME=<service>  # start one service"
	@echo "  make <platform>-deploy-development [NAME=<service>]"
	@echo "  make <platform>-deploy-production  [NAME=<service>]"
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
	@echo "         make backend-deploy-development NAME=api"
	@echo "         make backend-deploy-production NAME=api"

$(PLATFORMS):
	@test -x "$@/scripts/run.sh" || (echo "missing: $@/scripts/run.sh"; exit 1)
	@if [ -n "$(NAME)" ]; then \
		"$@/scripts/run.sh" "$(NAME)" $(ARGS); \
	else \
		"$@/scripts/run.sh" $(ARGS); \
	fi

$(DEPLOY_DEVELOPMENT_TARGETS): %-deploy-development:
	@test -x "$*/scripts/deploy-development.sh" || (echo "missing: $*/scripts/deploy-development.sh"; exit 1)
	@"$*/scripts/deploy-development.sh" "$(NAME)" $(ARGS)

$(DEPLOY_PRODUCTION_TARGETS): %-deploy-production:
	@test -x "$*/scripts/deploy-production.sh" || (echo "missing: $*/scripts/deploy-production.sh"; exit 1)
	@"$*/scripts/deploy-production.sh" "$(NAME)" $(ARGS)
