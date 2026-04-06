"""CLI integration tests using subprocess."""
import subprocess
import json
import sys
import os
import pytest

PYTHON = sys.executable


def run_cli(*args, cwd=None):
    cmd = [PYTHON, '-m', 'buildingspacegen.cli.main'] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result


def test_cli_generate(tmp_path):
    out = str(tmp_path / "building.json")
    result = run_cli('generate', '--type', 'medium_office', '--sqft', '10000', '--seed', '42', '--output', out)
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    assert os.path.exists(out)
    with open(out) as f:
        data = json.load(f)
    assert "building" in data
    assert data["building"]["building_type"] == "medium_office"


def test_cli_batch(tmp_path):
    out = str(tmp_path / "batch.json")
    result = run_cli('batch', '--type', 'medium_office', '--sqft', '10000', '--runs', '3',
                     '--freq', '900000000', '--output', out)
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    assert os.path.exists(out)
    with open(out) as f:
        data = json.load(f)
    assert data["num_runs"] == 3


def test_cli_help():
    result = run_cli('--help')
    assert result.returncode == 0
    assert 'generate' in result.stdout
