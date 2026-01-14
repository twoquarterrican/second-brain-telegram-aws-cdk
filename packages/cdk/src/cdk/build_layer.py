#!/usr/bin/env python3
"""
Build Lambda layer using uv from lambdas dependencies
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from common.environments import project_root, lambdas_dir, layer_dir


def run_command(cmd, cwd=None):
    """Run shell command and return result"""
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Command failed: {cmd}")
        print(f"Error: {result.stderr}")
        raise subprocess.CalledProcessError(result.returncode, cmd)
    return result


def build_lambda_layer():
    """Build Lambda layer from lambdas dependencies"""
    from common.environments import project_root, lambdas_dir, layer_dir

    print(f"Building Lambda layer...")
    print(f"Lambdas dir: {lambdas_dir()}")
    print(f"Layer output dir: {layer_dir()}")

    # Always clear existing layer directory
    layer_output = layer_dir()
    if layer_output.exists():
        print("Clearing existing layer directory...")
        shutil.rmtree(layer_output)

    layer_output.mkdir(parents=True, exist_ok=True)

    # Create python directory in layer
    python_dir = layer_output / "python"
    python_dir.mkdir(parents=True, exist_ok=True)

    pyproject_toml = (lambdas_dir() / "pyproject.toml").as_posix()

    # Manually install specific compatible versions
    compatible_deps = [
        "boto3>=1.26.0,<2.0.0",
        "requests>=2.28.0",
        "anthropic>=0.8.0,<1.0.0",
        "openai>=0.27.0,<2.0.0",
    ]

    for dep in compatible_deps:
        print(f"Installing {dep}")
        install_cmd = f'uv pip install --target {python_dir} --python=3.12 "{dep}"'
        run_command(install_cmd, project_root())

    print(f"✅ Lambda layer built successfully at: {layer_dir()}")
    return layer_output


if __name__ == "__main__":
    build_lambda_layer()
