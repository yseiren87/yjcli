.PHONY: help run

help:
	@echo "Usage:"
	@echo "  make run PLATFORM=<platform> NAME=<service> [ARGS='...']"
	@echo ""
	@echo "Platforms: backend backend-service frontend mobile-app pc-app cli browser-extension"
	@echo "Delegates to: <PLATFORM>/scripts/run.sh <NAME> ..."

run:
	@test -n "$(PLATFORM)" || (echo "PLATFORM required"; exit 1)
	@test -n "$(NAME)" || (echo "NAME required"; exit 1)
	@test -x "$(PLATFORM)/scripts/run.sh" || (echo "missing: $(PLATFORM)/scripts/run.sh (run: yjcli add platform)"; exit 1)
	@"$(PLATFORM)/scripts/run.sh" "$(NAME)" $(ARGS)
