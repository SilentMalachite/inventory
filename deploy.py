#!/usr/bin/env python3
"""
Deployment script for the inventory system.
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path
import platform


def run_command(cmd, cwd=None, check=True):
    """Run a command and handle errors."""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, check=check)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result


def check_dependencies():
    """Check if all required dependencies are available."""
    print("Checking dependencies...")
    
    # Check Python
    try:
        result = run_command("python --version", check=False)
        if result.returncode != 0:
            raise RuntimeError("Python is not installed")
        print(f"✓ Python: {result.stdout.strip()}")
    except Exception as e:
        print(f"✗ Python check failed: {e}")
        return False
    
    # Check Node.js
    try:
        result = run_command("node --version", check=False)
        if result.returncode != 0:
            raise RuntimeError("Node.js is not installed")
        print(f"✓ Node.js: {result.stdout.strip()}")
    except Exception as e:
        print(f"✗ Node.js check failed: {e}")
        return False
    
    # Check uv
    try:
        result = run_command("uv --version", check=False)
        if result.returncode != 0:
            print("⚠ uv is not installed, using pip instead")
        else:
            print(f"✓ uv: {result.stdout.strip()}")
    except Exception as e:
        print(f"⚠ uv check failed: {e}, using pip instead")
    
    return True


def install_backend_deps():
    """Install backend dependencies."""
    print("\nInstalling backend dependencies...")
    
    # Try uv first, fall back to pip
    try:
        run_command("uv sync", check=False)
        print("✓ Backend dependencies installed with uv")
    except:
        run_command("pip install -e .")
        print("✓ Backend dependencies installed with pip")


def install_frontend_deps():
    """Install frontend dependencies."""
    print("\nInstalling frontend dependencies...")
    run_command("cd frontend && npm install")
    print("✓ Frontend dependencies installed")


def build_frontend():
    """Build the frontend."""
    print("\nBuilding frontend...")
    run_command("cd frontend && npm run build")
    print("✓ Frontend built successfully")


def run_tests():
    """Run tests."""
    print("\nRunning tests...")
    
    # Set test environment
    env = os.environ.copy()
    env["INVENTORY_APP_DIR"] = "/tmp/inventory-test"
    env["INVENTORY_AUDIT_DISABLED"] = "1"
    env["INVENTORY_DEV_MODE"] = "true"
    
    try:
        result = run_command(
            "PYTHONPATH=src python -m pytest tests/ -v",
            check=False,
            env=env
        )
        if result.returncode == 0:
            print("✓ All tests passed")
            return True
        else:
            print("✗ Some tests failed")
            return False
    except Exception as e:
        print(f"✗ Test execution failed: {e}")
        return False


def create_executable():
    """Create executable with PyInstaller."""
    print("\nCreating executable...")
    
    # Build frontend first
    build_frontend()
    
    # Install PyInstaller if not available
    try:
        run_command("python -c 'import PyInstaller'", check=False)
    except:
        print("Installing PyInstaller...")
        run_command("pip install pyinstaller")
    
    # Create executable
    try:
        run_command("uv run pyinstaller inventory-app.spec")
        print("✓ Executable created successfully")
        
        # Show file info
        if platform.system() == "Windows":
            exe_path = "dist/inventory-app.exe"
        else:
            exe_path = "dist/inventory-app"
        
        if Path(exe_path).exists():
            size = Path(exe_path).stat().st_size / (1024 * 1024)  # MB
            print(f"✓ Executable size: {size:.1f} MB")
        
        return True
    except Exception as e:
        print(f"✗ Failed to create executable: {e}")
        return False


def create_docker_image():
    """Create Docker image."""
    print("\nCreating Docker image...")
    
    dockerfile_content = """
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    nodejs \\
    npm \\
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# Copy source code
COPY src/ ./src/
COPY frontend/ ./frontend/

# Build frontend
RUN cd frontend && npm install && npm run build

# Create app directory
RUN mkdir -p /var/lib/inventory

# Set environment variables
ENV INVENTORY_APP_DIR=/var/lib/inventory
ENV INVENTORY_SECRET_KEY=change-me-in-production

# Expose port
EXPOSE 8000

# Run the application
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
"""
    
    with open("Dockerfile", "w") as f:
        f.write(dockerfile_content.strip())
    
    # Create .dockerignore
    dockerignore_content = """
__pycache__
*.pyc
*.pyo
*.pyd
.git
.pytest_cache
.coverage
.tox
.env
*.log
.DS_Store
dist/
build/
*.egg-info/
"""
    
    with open(".dockerignore", "w") as f:
        f.write(dockerignore_content.strip())
    
    try:
        run_command("docker build -t inventory-system .")
        print("✓ Docker image created successfully")
        return True
    except Exception as e:
        print(f"✗ Failed to create Docker image: {e}")
        return False


def deploy_production():
    """Deploy to production."""
    print("\n=== Production Deployment ===")
    
    if not check_dependencies():
        print("✗ Dependencies check failed")
        return False
    
    install_backend_deps()
    install_frontend_deps()
    
    if not run_tests():
        print("✗ Tests failed, aborting deployment")
        return False
    
    print("\n✓ All checks passed, ready for deployment")
    print("\nDeployment options:")
    print("1. Create executable")
    print("2. Create Docker image")
    print("3. Both")
    
    choice = input("\nSelect deployment option (1/2/3): ").strip()
    
    success = True
    
    if choice in ("1", "3"):
        if not create_executable():
            success = False
    
    if choice in ("2", "3"):
        if not create_docker_image():
            success = False
    
    if success:
        print("\n✓ Deployment completed successfully!")
        print("\nNext steps:")
        print("- For executable: Run 'dist/inventory-app'")
        print("- For Docker: Run 'docker run -p 8000:8000 -v /var/lib/inventory:/var/lib/inventory inventory-system'")
        print("- Set environment variables for production use")
    else:
        print("\n✗ Deployment completed with errors")
    
    return success


def main():
    """Main deployment function."""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "test":
            return run_tests()
        elif command == "build":
            return build_frontend()
        elif command == "exe":
            return create_executable()
        elif command == "docker":
            return create_docker_image()
        elif command == "deploy":
            return deploy_production()
        else:
            print(f"Unknown command: {command}")
            return 1
    else:
        return deploy_production()


if __name__ == "__main__":
    sys.exit(0 if main() else 1)