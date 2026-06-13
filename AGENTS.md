# Repository Guidelines

## Purpose

`jsonl-viewer` is a Python CLI for inspecting JSON Lines files in a terminal. The
installed command is `jsonl`, provided by the `jsonl-cli` package.

The main interface is a curses viewer for row-by-row navigation, plus a brief
summary mode for file characteristics.

## Repository Structure

- `pyproject.toml`: setuptools package metadata, Python version requirement,
  console script entry point, and bundled package data.
- `README.md`: user-facing install and usage documentation.
- `LICENSE`: project license.
- `jsonl_cli/__main__.py`: enables `python -m jsonl_cli`.
- `jsonl_cli/cli.py`: argparse setup, curses lifecycle, viewer state, keyboard
  handling, and brief mode.
- `jsonl_cli/command.py`: command prompt input and command dispatch, such as
  `:goto` and `:quit`.
- `jsonl_cli/search.py`: vim-like search parsing, nested field traversal, row
  scanning, and match state helpers.
- `jsonl_cli/render.py`: JSON value rendering and terminal-width wrapping.
- `jsonl_cli/colors.py`: theme loading and curses color mapping.
- `jsonl_cli/helpers.py`: file validation, byte offsets, row parsing, summaries,
  and CLI error exits.
- `jsonl_cli/containers.py`: shared dataclasses and render type aliases.
- `jsonl_cli/themes/*.json`: packaged color themes. These are included through
  `tool.setuptools.package-data`.
- `tests/`: committed `unittest` coverage and synthetic JSONL fixtures.
- `resources/`: README and documentation assets only.

## Development Commands

Set up an editable install from the repository root:

```sh
python -m pip install -e .
```

Run the CLI after installation:

```sh
jsonl path/to/file.jsonl
jsonl path/to/file.jsonl --brief
```

Run without installing the script:

```sh
python -m jsonl_cli path/to/file.jsonl
```

Build a source and wheel distribution when packaging locally:

```sh
python -m build
```

Run the committed unit tests:

```sh
python -m unittest
```

For CLI behavior changes, also validate manually with at least:

```sh
jsonl tests/fixtures/search_sample.jsonl --brief
jsonl tests/fixtures/search_sample.jsonl
```

For curses changes, manually check small terminals, wide terminals, empty files,
invalid JSON rows, long wrapped values, and theme fallback behavior.

## Coding Standards

- Target Python 3.9 or newer.
- Keep code straightforward and concise. Avoid dense cleverness that makes
  terminal behavior or JSON rendering hard to reason about.
- Prefer standard library modules. The package currently has no runtime
  dependencies beyond Python and curses.
- Preserve the existing helper-module split. Do not move rendering, command
  parsing, color mapping, and file I/O into `cli.py` unless the change is very
  small.
- Keep private helpers prefixed with `_` unless they are intended as public API.
- Use type hints for new functions and data structures.
- Keep comments short and useful. Do not comment code that is obvious from the
  implementation.
- Use ASCII in comments and documentation unless there is a specific need for
  user-facing Unicode.
- Avoid broad `except` clauses in new code. Catch the specific exception when the
  fallback behavior is intentional.
- Do not introduce unrelated formatting churn while making behavior changes.

## CLI Behavior Guidelines

- Keep errors user-oriented and route fatal CLI errors through `_die` where it
  fits the existing flow.
- Preserve `.jsonl` path validation unless the user-facing contract changes.
- Avoid loading whole JSONL files into memory for viewer navigation. The current
  design stores byte offsets and reads one row at a time.
- Treat JSON rows independently. Invalid rows should not prevent viewing other
  rows.
- Keep curses drawing defensive. Terminal resize and edge dimensions can raise
  `curses.error`; handle those cases without crashing where practical.
- When changing key bindings, update both the header text in `cli.py` and the
  README.
- When adding general commands, implement parsing in `jsonl_cli/command.py`.
  Keep search-specific parsing and matching in `jsonl_cli/search.py`.
- Keep command status messages short enough for narrow terminals.
- Search should preserve byte-offset navigation and scan rows one at a time.
  Field filters should support nested object paths, list indexes, and wildcards.

## Theme Guidelines

- Themes live in `jsonl_cli/themes/` as JSON files.
- Each theme should expose a `key-colors` array of hex colors.
- Theme names are selected by filename without `.json`.
- If theme loading changes, keep package-data configuration in `pyproject.toml`
  in sync so installed packages include the theme files.

## Packaging and Redistribution

The Python package name is `jsonl-cli`, and the console script is:

```toml
[project.scripts]
jsonl = "jsonl_cli.cli:main"
```

The user-facing redistribution path is Homebrew:

```sh
brew tap looooonk/tap
brew install jsonl-cli
```

The Homebrew formula is expected to live outside this repository in the
`looooonk/tap` tap. When releasing a new version:

1. Update `version` in `pyproject.toml`.
2. Build and publish the Python package artifact or source archive used by the
   formula.
3. Update the `jsonl-cli` Homebrew formula in `looooonk/tap` with the new URL
   and checksum.
4. Verify install from the tap with `brew install jsonl-cli` or
   `brew reinstall jsonl-cli`.
5. Keep README installation instructions aligned with the formula name and tap.

Do not rename the package, console script, or tap instructions without updating
`pyproject.toml`, `README.md`, and the Homebrew formula together.

## Documentation Expectations

- Update `README.md` when user-visible commands, key bindings, installation
  steps, theme behavior, or screenshots change.
- Keep examples runnable from a normal shell.
- Do not document planned behavior as currently available behavior.
