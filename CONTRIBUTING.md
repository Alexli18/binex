# Contributing

Contributions are welcome! Here's how to get started.

## Development Setup

```bash
git clone https://github.com/Alexli18/binex.git
cd binex
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,rich]"
```

## Run Tests

```bash
python -m pytest tests/
```

## Run Linter

```bash
ruff check src/
```

## Run Documentation Locally

```bash
mkdocs serve
```

Then open [http://localhost:8000](http://localhost:8000).

## Code Style

- Python 3.11+
- Linting via [ruff](https://docs.astral.sh/ruff/)
- Type checking via [mypy](https://mypy-lang.org/) (strict mode)
- Models via [Pydantic v2](https://docs.pydantic.dev/)

## Submitting Changes

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Run tests and linter
5. Commit and push
6. Open a Pull Request

## Reporting Issues

Use [GitHub Issues](https://github.com/Alexli18/binex/issues) to report bugs or request features.
