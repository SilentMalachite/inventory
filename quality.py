#!/usr/bin/env python3
"""
Code quality utilities for the inventory system.
"""
import subprocess
import sys
from pathlib import Path


def run_command(cmd: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    print(f"Running: {cmd}")
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, check=check
    )
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result


def format_code() -> bool:
    """Format code using black and isort."""
    print("\n=== Formatting code ===")
    try:
        # Run black
        run_command("uv run black src tests")
        
        # Run isort
        run_command("uv run isort src tests")
        
        print("✓ Code formatted successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Code formatting failed: {e}")
        return False


def lint_code() -> bool:
    """Lint code using ruff."""
    print("\n=== Linting code ===")
    try:
        # Run ruff check and fix
        result = run_command("uv run ruff check src tests --fix", check=False)
        
        if result.returncode == 0:
            print("✓ Code linting passed")
            return True
        else:
            print("✗ Code linting found issues")
            return False
    except subprocess.CalledProcessError as e:
        print(f"✗ Code linting failed: {e}")
        return False


def type_check() -> bool:
    """Run type checking with mypy."""
    print("\n=== Type checking ===")
    try:
        result = run_command("uv run mypy src", check=False)
        
        if result.returncode == 0:
            print("✓ Type checking passed")
            return True
        else:
            print("✗ Type checking found issues")
            return False
    except subprocess.CalledProcessError as e:
        print(f"✗ Type checking failed: {e}")
        return False


def run_tests() -> bool:
    """Run tests with coverage."""
    print("\n=== Running tests ===")
    try:
        # Set test environment
        env = {
            "PYTHONPATH": "src",
            "INVENTORY_APP_DIR": "/tmp/inventory-test",
            "INVENTORY_AUDIT_DISABLED": "1",
            "INVENTORY_DEV_MODE": "true",
        }
        
        # Run pytest with coverage
        cmd = (
            "uv run pytest tests/ -v --cov=src --cov-report=term-missing "
            "--cov-report=html --cov-fail-under=80"
        )
        
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, env=env
        )
        
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        
        if result.returncode == 0:
            print("✓ All tests passed")
            return True
        else:
            print("✗ Some tests failed")
            return False
    except Exception as e:
        print(f"✗ Test execution failed: {e}")
        return False


def security_scan() -> bool:
    """Run security scanning with bandit."""
    print("\n=== Security scanning ===")
    try:
        result = run_command("uv run bandit -r src/", check=False)
        
        if result.returncode == 0:
            print("✓ Security scan passed")
            return True
        else:
            print("✗ Security scan found issues")
            return False
    except subprocess.CalledProcessError as e:
        print(f"✗ Security scan failed: {e}")
        return False


def complexity_analysis() -> bool:
    """Analyze code complexity with radon."""
    print("\n=== Complexity analysis ===")
    try:
        # Calculate complexity
        result = run_command("uv run radon cc src/ -a -nb", check=False)
        
        if result.returncode == 0:
            print("✓ Complexity analysis completed")
            return True
        else:
            print("✗ Complexity analysis failed")
            return False
    except subprocess.CalledProcessError as e:
        print(f"✗ Complexity analysis failed: {e}")
        return False


def install_dev_deps() -> bool:
    """Install development dependencies."""
    print("\n=== Installing development dependencies ===")
    try:
        run_command("uv sync --dev")
        print("✓ Development dependencies installed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install development dependencies: {e}")
        return False


def pre_commit_check() -> bool:
    """Run all pre-commit checks."""
    print("\n=== Running pre-commit checks ===")
    try:
        run_command("uv run pre-commit run --all-files")
        print("✓ Pre-commit checks passed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Pre-commit checks failed: {e}")
        return False


def setup_pre_commit() -> bool:
    """Set up pre-commit hooks."""
    print("\n=== Setting up pre-commit hooks ===")
    try:
        run_command("uv run pre-commit install")
        print("✓ Pre-commit hooks installed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to set up pre-commit hooks: {e}")
        return False


def main() -> int:
    """Main function."""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "format":
            return 0 if format_code() else 1
        elif command == "lint":
            return 0 if lint_code() else 1
        elif command == "type":
            return 0 if type_check() else 1
        elif command == "test":
            return 0 if run_tests() else 1
        elif command == "security":
            return 0 if security_scan() else 1
        elif command == "complexity":
            return 0 if complexity_analysis() else 1
        elif command == "install-dev":
            return 0 if install_dev_deps() else 1
        elif command == "pre-commit":
            return 0 if pre_commit_check() else 1
        elif command == "setup-pre-commit":
            return 0 if setup_pre_commit() else 1
        else:
            print(f"Unknown command: {command}")
            return 1
    else:
        # Run all checks
        print("=== Running all code quality checks ===")
        
        checks = [
            ("Format code", format_code),
            ("Lint code", lint_code),
            ("Type check", type_check),
            ("Run tests", run_tests),
            ("Security scan", security_scan),
            ("Complexity analysis", complexity_analysis),
        ]
        
        passed = 0
        total = len(checks)
        
        for name, check_func in checks:
            if check_func():
                passed += 1
        
        print(f"\n=== Summary ===")
        print(f"Passed: {passed}/{total}")
        
        if passed == total:
            print("✓ All checks passed!")
            return 0
        else:
            print("✗ Some checks failed")
            return 1


if __name__ == "__main__":
    sys.exit(main())