"""Tools the Escalator agents can call. One so far: run_python, backed by an AWS Lambda sandbox.

The decider can tell whether an answer addresses the question, but not whether a calculation is
right or code does what it claims. run_python lets the answering model compute instead of guess.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any

FUNCTION_NAME = os.environ.get("ESCALATOR_RUN_PYTHON_FUNCTION", "escalator-run-python")
MAX_RUNS = int(os.environ.get("ESCALATOR_MAX_RUNS", "6"))  # tool calls allowed in one answer

TOOL_HINT = (
    "You can run Python with the run_python tool. For any calculation, counting, date "
    "arithmetic, or question about what code outputs, write a short program that prints the "
    "result, run it, and answer from its output instead of working it out in your head."
)

Invoke = Callable[[dict[str, Any]], dict[str, Any]]


def lambda_invoke(payload: dict[str, Any]) -> dict[str, Any]:
    """Run the payload through the deployed Lambda function (see deploy/deploy_run_python.py)."""
    import boto3

    client = boto3.client("lambda", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    response = client.invoke(FunctionName=FUNCTION_NAME, Payload=json.dumps(payload).encode())
    body = json.loads(response["Payload"].read())
    if response.get("FunctionError"):
        return {"stdout": "", "stderr": body.get("errorMessage", "sandbox error"),
                "exit_code": None, "timed_out": False}
    return body


def format_result(result: dict[str, Any]) -> str:
    """What the model sees after a run: the output first, then anything that went wrong."""
    if result.get("timed_out"):
        status = "timed out"
    else:
        status = f"exit code {result.get('exit_code')}"
    parts = [status, "stdout:", result.get("stdout") or "(nothing printed)"]
    if result.get("stderr"):
        parts += ["stderr:", result["stderr"]]
    return "\n".join(parts)


def make_run_python(invoke: Invoke = lambda_invoke, log: list | None = None):
    """Build the Strands tool. Pass a different `invoke` to run code somewhere else (tests do).

    If `log` is a list, every run is appended to it as {"code": ..., "result": ...}, so callers
    can show or save exactly what the model ran.
    """
    from strands import tool

    @tool
    def run_python(code: str) -> str:
        """Run a short Python 3 program in an isolated sandbox and return what it printed.

        Use it for calculations, counting, dates, and checking what code outputs. The program has
        the standard library only, no files from the conversation, and a 5-second limit.

        Args:
            code: A complete Python 3 program. Print every value you need to see.
        """
        result = invoke({"code": code})
        if log is not None:
            log.append({"code": code, "result": result})
        return format_result(result)

    return run_python


class RunBudget:
    """A Strands hook provider that caps tool calls in one agent turn.

    Without it, a model stuck in a loop can keep calling the tool (one benchmark answer ran code
    122 times). After `limit` calls, further calls are cancelled with a message telling the model
    to answer from what it has.
    """

    def __init__(self, limit: int = MAX_RUNS):
        self.limit, self.used = limit, 0

    def register_hooks(self, registry, **kwargs) -> None:
        from strands.hooks import BeforeToolCallEvent

        registry.add_callback(BeforeToolCallEvent, self.check)

    def check(self, event) -> None:
        self.used += 1
        if self.used > self.limit:
            event.cancel_tool = (f"Limit of {self.limit} code runs reached. Answer now from the outputs "
                                 "you already have.")
