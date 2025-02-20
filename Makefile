SRC_FILES := $(wildcard src/gh_parser/*.py)
UTIL_FILES := $(wildcard src/gh_parser/utils/*.py)

format:
	black $(SRC_FILES) $(UTIL_FILES)

black: format