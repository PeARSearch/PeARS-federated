.DEFAULT_GOAL: help
SHELL := /bin/bash

PROJECTNAME := "pears-federated"

.PHONY: help
all: help
help: Makefile
	@echo
	@echo " Choose a command to run in "$(PROJECTNAME)":"
	@echo
	@sed -n 's/^##//p' $< | column -t -s ':' |  sed -e 's/^/ /'
	@echo note: call scripts from /scripts

check-%: # detection of required software.
	@which ${*} > /dev/null || (echo '*** Please install `${*}` ***' && exit 1)

## build: Build the container image
build: check-docker
	@docker buildx build --no-cache --pull -f deployment/Dockerfile -t ${PROJECTNAME}:local-build .

test:
	pytest -v

test-docker:
	bash tests/run_tests_docker.sh

test-cov:
	pytest --cov=app tests/ -v