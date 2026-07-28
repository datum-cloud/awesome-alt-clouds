"""Tiny shell-command helper shared by the PR-creation scripts."""

import subprocess


def run_command(cmd, check=True):
    """Run a shell command and return its stdout, stripped."""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error: {result.stderr}")
        raise Exception(f"Command failed: {cmd}")
    return result.stdout.strip()
