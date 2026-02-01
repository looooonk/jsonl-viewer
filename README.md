# jsonl-viewer

A CLI tool to manually view the rows of a JSON lines file.

## Requirements

`curses` and Python (>= 3.9) must be installed.

## Installation

After cloning the repository, run the following installation command:

```
$ git clone https://github.com/looooonk/jsonl-viewer.git
$ cd jsonl-viewer
$ python -m pip install -e .
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