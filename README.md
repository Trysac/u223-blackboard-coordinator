# blackboard-coordinator

[![PyPI version](https://img.shields.io/pypi/v/trysac-blackboard-coordinator)](https://pypi.org/project/trysac-blackboard-coordinator/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-blackboard-coordinator)](LICENSE)
[![CI](https://github.com/Trysac/u223-blackboard-coordinator/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u223-blackboard-coordinator/actions/workflows/ci.yml)

Coordinate agents through a shared blackboard: versioned JSON entries, knowledge sources triggered by key changes, deterministic priority scheduling, fault isolation and a goal check

## Problem

Describe in two or three sentences the concrete problem this utility solves, who hits it, and what
they do today without it. Replace this paragraph when the first real feature lands.

## Install

```sh
pip install trysac-blackboard-coordinator
# or
uv add trysac-blackboard-coordinator
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
import blackboard_coordinator

# normalize() trims surrounding whitespace and lower-cases the text.
print(blackboard_coordinator.normalize("  Hello World "))  # -> "hello world"

# Blank input is rejected explicitly instead of returning an empty string.
try:
    blackboard_coordinator.normalize("   ")
except ValueError as exc:
    print(f"rejected: {exc}")
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
