# Platform targets are discovered from */scripts/run.sh (after yjcli platform add).
# Usage:
#   make <platform>                 # all services under that platform (concurrent)
#   make <platform> NAME=<service>  # one service
# Build/deploy templates are platform-owned extension points. They intentionally fail
# until the repository implements the printed build/package/upload steps.
# Build/deploy scripts are POSIX shell (.sh) only — build/deploy tooling (Docker, etc.)
# is not native to Windows. Run this Makefile through WSL on Windows for those targets.

PLATFORMS := $(patsubst %/scripts/run.sh,%,$(wildcard */scripts/run.sh))
BUILD_DEVELOPMENT_TARGETS := $(addsuffix -build-development,$(PLATFORMS))
BUILD_PRODUCTION_TARGETS := $(addsuffix -build-production,$(PLATFORMS))
DEPLOY_DEVELOPMENT_TARGETS := $(addsuffix -deploy-development,$(PLATFORMS))
DEPLOY_PRODUCTION_TARGETS := $(addsuffix -deploy-production,$(PLATFORMS))

.PHONY: help $(PLATFORMS) $(BUILD_DEVELOPMENT_TARGETS) $(BUILD_PRODUCTION_TARGETS) $(DEPLOY_DEVELOPMENT_TARGETS) $(DEPLOY_PRODUCTION_TARGETS)

help:
	@echo "Usage:"
	@echo "  make <platform>                 # start all services concurrently"
	@echo "  make <platform> NAME=<service>  # start one service"
	@echo "  make <platform>-build-development  [NAME=<service>]"
	@echo "  make <platform>-build-production   [NAME=<service>]"
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
	@echo "         make backend-build-development NAME=api"
	@echo "         make backend-deploy-production NAME=api"

$(PLATFORMS):
	@test -x "$@/scripts/run.sh" || (echo "missing: $@/scripts/run.sh"; exit 1)
	@if [ -n "$(NAME)" ]; then \
		"$@/scripts/run.sh" "$(NAME)" $(ARGS); \
	else \
		"$@/scripts/run.sh" $(ARGS); \
	fi

$(BUILD_DEVELOPMENT_TARGETS): %-build-development:
	@test -x "$*/scripts/build-development.sh" || (echo "missing: $*/scripts/build-development.sh"; exit 1)
	@"$*/scripts/build-development.sh" "$(NAME)" $(ARGS)

$(BUILD_PRODUCTION_TARGETS): %-build-production:
	@test -x "$*/scripts/build-production.sh" || (echo "missing: $*/scripts/build-production.sh"; exit 1)
	@"$*/scripts/build-production.sh" "$(NAME)" $(ARGS)

$(DEPLOY_DEVELOPMENT_TARGETS): %-deploy-development:
	@test -x "$*/scripts/deploy-development.sh" || (echo "missing: $*/scripts/deploy-development.sh"; exit 1)
	@"$*/scripts/deploy-development.sh" "$(NAME)" $(ARGS)

$(DEPLOY_PRODUCTION_TARGETS): %-deploy-production:
	@test -x "$*/scripts/deploy-production.sh" || (echo "missing: $*/scripts/deploy-production.sh"; exit 1)
	@"$*/scripts/deploy-production.sh" "$(NAME)" $(ARGS)
