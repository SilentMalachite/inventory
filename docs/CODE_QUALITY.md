# Code Quality Guide

## Overview

This document describes the code quality standards and tools used in the inventory system project.

## Tools Used

### Code Formatting
- **Black**: Opinionated code formatter
- **isort**: Import sorter

### Linting
- **Ruff**: Fast Python linter and code formatter
- **Flake8**: Additional linting rules

### Type Checking
- **MyPy**: Static type checker

### Testing
- **Pytest**: Test framework
- **pytest-cov**: Coverage reporting
- **httpx**: HTTP client for testing

### Security
- **Bandit**: Security linter

### Code Analysis
- **Radon**: Code complexity analysis

## Quality Commands

### Quick Quality Check
```bash
# Run all quality checks
python quality.py

# Individual checks
python quality.py format    # Format code
python quality.py lint      # Lint code
python quality.py type      # Type check
python quality.py test      # Run tests
python quality.py security  # Security scan
python quality.py complexity # Complexity analysis
```

### Pre-commit Hooks
```bash
# Install pre-commit hooks
python quality.py setup-pre-commit

# Run pre-commit checks manually
python quality.py pre-commit
```

## Code Standards

### Python Style Guide
- Follow PEP 8
- Use Black for formatting (line length 88)
- Use type hints for all function parameters and return values
- Use docstrings for all public functions and classes

### Naming Conventions
- **Functions and variables**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private members**: `_single_underscore_prefix`

### Type Hints
```python
from typing import Optional, List, Dict, Any

def get_item_balance(session: Session, item_id: int) -> Dict[str, Any]:
    """Get detailed balance information for an item.
    
    Args:
        session: Database session
        item_id: ID of the item
        
    Returns:
        Dict[str, Any]: Dictionary containing balance information
    """
    # Implementation
```

### Error Handling
```python
from fastapi import HTTPException
from ..exceptions import InventoryError

@handle_api_errors
def create_item(item: ItemCreate, session: Session) -> Item:
    """Create a new item."""
    try:
        obj = Item(**item.model_dump())
        session.add(obj)
        session.commit()
        session.refresh(obj)
        return obj
    except IntegrityError as e:
        if "unique" in str(e).lower():
            raise InventoryError("Duplicate SKU", status_code=409)
        raise
```

### Database Patterns
```python
from sqlmodel import Session, select
from contextlib import contextmanager

@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Get database session with automatic commit/rollback."""
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

### API Patterns
```python
from fastapi import APIRouter, Depends, HTTPException
from ..schemas import ItemCreate, ItemResponse
from ..dependencies import get_current_user

router = APIRouter()

@router.post(
    "/",
    response_model=ItemResponse,
    status_code=201,
    summary="Create item",
    description="Create a new inventory item",
    responses={
        409: {"model": ErrorResponse, "description": "Duplicate SKU"},
    }
)
@handle_api_errors
def create_item(
    item: ItemCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ItemResponse:
    """Create a new item."""
    # Implementation
```

## Quality Metrics

### Test Coverage
- Minimum coverage: 80%
- Coverage reports generated in `htmlcov/`
- Run with: `python quality.py test`

### Complexity
- Maximum cyclomatic complexity: 10
- Analyze with: `python quality.py complexity`

### Security
- No high-severity security issues
- Run security scan: `python quality.py security`

## Pre-commit Configuration

The project uses pre-commit hooks to ensure code quality:

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files

  - repo: https://github.com/psf/black
    hooks:
      - id: black

  - repo: https://github.com/astral-sh/ruff-pre-commit
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    hooks:
      - id: mypy
```

## CI/CD Integration

Quality checks are integrated into the CI pipeline:

```yaml
jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - name: Install dependencies
        run: uv sync --dev
      - name: Run quality checks
        run: python quality.py
      - name: Upload coverage
        run: |
          python quality.py test
          upload-to-codecov
```

## Best Practices

### 1. Write Tests First
- Write tests before implementing features
- Aim for high test coverage
- Test both happy paths and error cases

### 2. Use Type Hints
- Add type hints to all functions
- Use generic types when appropriate
- Run MyPy regularly

### 3. Keep Functions Small
- Functions should do one thing well
- Maximum 20-30 lines per function
- Extract complex logic to helper functions

### 4. Handle Errors Gracefully
- Use custom exceptions
- Provide meaningful error messages
- Log errors appropriately

### 5. Document Code
- Write docstrings for all public APIs
- Add inline comments for complex logic
- Keep documentation up to date

### 6. Follow Security Best Practices
- Validate all inputs
- Use parameterized queries
- Keep secrets out of code

### 7. Optimize Performance
- Use database indexes
- Implement caching where appropriate
- Profile and optimize slow queries

## Troubleshooting

### Common Issues

1. **Type checking fails**
   - Check type hints are correct
   - Update stub packages if needed
   - Use `type: ignore` sparingly

2. **Tests fail**
   - Check test environment setup
   - Verify database state
   - Run tests with verbose output

3. **Linting errors**
   - Run formatter first
   - Check for deprecated features
   - Review error messages carefully

4. **Security warnings**
   - Review flagged code
   - Consider alternative approaches
   - Document security decisions

### Performance Tips

1. **Reduce test runtime**
   - Use fixtures and mocking
   - Parallelize test execution
   - Optimize database operations

2. **Speed up quality checks**
   - Use incremental type checking
   - Cache dependencies
   - Run checks in parallel

## Continuous Improvement

Regularly review and update quality standards:
- Stay current with tool updates
- Adopt new best practices
- Solicit team feedback
- Monitor quality metrics