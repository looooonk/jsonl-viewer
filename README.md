# jsonl-viewer

A CLI tool to manually view the rows of a JSON lines file.

Requires the use of `curses`, and therefore only supports MacOS & Linux.

## Installation

After cloning the repository, run the following installation command:

```
python -m pip install -e .
```

## Usage

To view the contents of a JSON lines file, use

```
jsonl PATH_TO_FILE
```

To view a summary of a JSON lines file, use

```
jsonl PATH_TO_FILE -b
```

To view more information, use

```
jsonl -h
```