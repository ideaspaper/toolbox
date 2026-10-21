.PHONY: test lint format build clean

VERSION := $(shell uv version --short)

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff format .
	uv run ruff check --fix .

# Single-file executable for the current OS/architecture, written to dist/toolbox.
# It unpacks itself once per version into ~/.cache/toolbox/<version> (a rebuild
# with the same version is detected and unpacked again), so later runs start fast.
# ccache is disabled because Nuitka's downloaded copy is x86_64-only on macOS.
# self-execution protection is disabled because it rejects our `-c` option.
build:
	uv run python -m nuitka --onefile --assume-yes-for-downloads --disable-ccache \
		--no-deployment-flag=self-execution \
		--product-name=toolbox --product-version=$(VERSION) \
		--onefile-tempdir-spec="{CACHE_DIR}/{PRODUCT}/{VERSION}" \
		--output-dir=dist --output-filename=toolbox --remove-output \
		src/toolbox/__main__.py

clean:
	rm -rf build dist
