.PHONY: all
all:
	@echo "Nothing to build."


.PHONY: test check
test check:
	tox -p auto


.PHONY: coverage
coverage:
	tox -e coverage


.PHONY: flake8
flake8:
	tox -e flake8

DISTCHECK_DIFF_OPTS = $(DISTCHECK_DIFF_DEFAULT_OPTS) -x .github
include release.mk
