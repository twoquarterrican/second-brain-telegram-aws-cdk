#!/usr/bin/env python3
"""
Build Lambda layer using uv from lambdas dependencies
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
import sys

from common.environments import project_root, lambdas_dir, layer_dir


def run_command(cmd, cwd=None):
    """Run shell command and return result"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        print(f"Command failed: {cmd}")
        print(f"Error: {result.stderr}")
        raise subprocess.CalledProcessError(result.returncode, cmd)
    return result


def build_lambda_layer():
    """Build Lambda layer from lambdas dependencies"""
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
    install_cmd = f"uv pip install --target {python_dir} -r {pyproject_toml}"
    run_command(install_cmd, project_root())

    print(f"✅ Lambda layer built successfully at: {layer_dir()}")
    return layer_output


if __name__ == "__main__":
    build_lambda_layer()
