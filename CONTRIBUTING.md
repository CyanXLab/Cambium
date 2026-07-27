# Contributing to Cambium

Thank you for your interest in contributing to Cambium! This document outlines the development workflow and standards.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/CyanXLab/Cambium.git
cd Cambium

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or .venv\Scripts\activate  # Windows

# Install in development mode with all optional dependencies
pip install -e ".[dev,all]"

# Run tests
python -m pytest tests/ -v

# Start the development server
python -m uvicorn app.main:app --port 3000 --reload
```

## Code Style

- **Python**: Follow PEP 8, enforced by `ruff`
- **Line length**: 120 characters
- **Type hints**: Required for all new functions
- **Docstrings**: Required for all public functions and classes
- **Imports**: Use `ruff` to sort imports automatically

```bash
# Format and lint
ruff check --fix app/ tests/
ruff format app/ tests/
```

## Architecture

Cambium follows a layered architecture:

```
app/
├── main.py              # FastAPI app + legacy routes (being migrated to app/api/)
├── config.py            # Pydantic Settings configuration
├── logging_config.py    # Structured logging
├── exceptions.py        # Global exception handlers
├── lifespan.py          # Application lifecycle (startup/shutdown)
├── agent_loop_v2.py     # CoALA + Claude Code Agent Loop
├── cognitive_kernel.py  # Seven-pillar cognitive kernel
├── memory_orchestrator.py # Four-layer memory + decay + dedup
├── memory_governance.py # SSGM: quarantine → validate → promote
├── adaptive_retrieval.py # EvolveMem: self-evolving retrieval weights
├── reflection_tree.py   # Generative Agents: three-level reflection
├── identity_consistency.py # Identity Layer: drift detection
└── ...                  # Other modules
```

See `docs/audit/01_FUNCTIONAL_SPEC.md` for the full module list and `ARCHITECTURE.md` for the design philosophy.

## Testing

- **Unit tests**: `tests/test_*.py` — test individual modules
- **API integration tests**: `tests/test_api_*.py` — test HTTP endpoints via TestClient
- **LLM mock tests**: Use `respx` to mock httpx calls
- **Coverage**: Aim for ≥ 70% on new code

```bash
# Run all tests
python -m pytest tests/

# Run with coverage
python -m pytest tests/ --cov=app --cov-report=term-missing

# Run a specific test file
python -m pytest tests/test_cognitive_kernel.py -v
```

## Pull Request Process

1. **Create a feature branch**: `git checkout -b feat/my-feature`
2. **Write tests** for your changes
3. **Ensure all tests pass**: `python -m pytest tests/`
4. **Lint your code**: `ruff check app/ tests/`
5. **Update documentation** if needed
6. **Submit a pull request** with a clear description

### Commit Message Convention

We follow a simplified Conventional Commits format:

```
<type>: <description>

[optional body]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `refactor`: Code restructuring (no behavior change)
- `test`: Test additions/changes
- `chore`: Build/CI/tooling changes

Examples:
```
feat: add memory governance SSGM pipeline
fix: correct asyncio.get_event_loop() deprecation
docs: update README to v2.0
test: add API integration tests for chat endpoint
```

## Adding New Features

### New API Endpoint

1. Add the route to the appropriate module in `app/` (or `app/api/` for new modules)
2. Use the `CambiumError` hierarchy from `app/exceptions.py` for error responses
3. Add type hints to the request/response models
4. Write API integration tests in `tests/test_api_*.py`
5. Update `docs/USAGE.md` if user-facing

### New Cognitive Module

1. Create `app/<module>.py` with schema initialization
2. Add the module to `app/lifespan.py::_init_module_schemas()`
3. Use `from app.db_utils import safe_connect` for all DB access
4. Use `from app.logging_config import get_logger` for logging
5. Write unit tests in `tests/test_<module>.py`

### New Tool

1. Add the tool definition to `app/tools_ext.py::build_tool_definitions()`
2. Set the appropriate `danger_level` (`low` / `medium` / `high`)
3. Add path validation via `_safe_resolve()` for file operations
4. Test the tool in isolation

## Code Review Checklist

- [ ] All tests pass
- [ ] No new `print()` calls (use `get_logger()` instead)
- [ ] No bare `except:` or `except Exception: pass`
- [ ] Type hints on all new functions
- [ ] Docstrings on all public functions/classes
- [ ] No hardcoded secrets or paths
- [ ] New settings added to `app/config.py`
- [ ] Database changes include migration in `app/migrations.py`

## Reporting Issues

When reporting a bug, please include:
- Python version
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Relevant log output (with `CAMBIUM_LOG_LEVEL=DEBUG`)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
