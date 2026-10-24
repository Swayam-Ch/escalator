"""AWS Lambda sandbox for the run_python tool: run a short Python program, return what it printed.

The program runs in a child process with an empty environment, so it cannot read the AWS
credentials Lambda puts in this function's environment. The function's role only allows writing
logs, and the child process is killed after `timeout` seconds.
"""

import subprocess
import sys

MAX_OUTPUT = 4000      # characters of stdout / stderr returned to the model
MAX_TIMEOUT = 10.0     # seconds; the function's own timeout is set a little higher


def _text(value):
    if value is None:
        return ""
    return value.decode(errors="replace") if isinstance(value, bytes) else value


def handler(event, context=None):
    code = event.get("code", "")
    timeout = min(float(event.get("timeout", 5)), MAX_TIMEOUT)
    try:
        done = subprocess.run(
            [sys.executable, "-I", "-c", code],
            capture_output=True, text=True, timeout=timeout,
            cwd="/tmp", env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"},
        )
        return {"stdout": done.stdout[-MAX_OUTPUT:], "stderr": done.stderr[-MAX_OUTPUT:],
                "exit_code": done.returncode, "timed_out": False}
    except subprocess.TimeoutExpired as exc:
        return {"stdout": _text(exc.stdout)[-MAX_OUTPUT:], "stderr": _text(exc.stderr)[-MAX_OUTPUT:],
                "exit_code": None, "timed_out": True}
