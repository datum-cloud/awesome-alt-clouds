"""Tiny shell-command helper shared by the PR-creation scripts."""

import subprocess


def run_command(cmd, check=True, input=None, strip=True):
    """Run a command as an argument list and return its stdout.

    `cmd` is a sequence of arguments, for example ["git", "add", "README.md"].
    The command runs without a shell, so a submitted value passed as an
    argument stays data and cannot change which command runs. Pass `input` to
    send text to the command's stdin, and `strip=False` to keep the raw stdout
    (for NUL-separated output).
    """
    printable = " ".join(cmd)
    print(f"Running: {printable}")
    result = subprocess.run(cmd, capture_output=True, text=True, input=input)
    if check and result.returncode != 0:
        print(f"Error: {result.stderr}")
        raise Exception(f"Command failed: {printable}")
    return result.stdout.strip() if strip else result.stdout
