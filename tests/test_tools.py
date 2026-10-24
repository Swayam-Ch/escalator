import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "bench"), str(ROOT / "lambda" / "run_python")]

from handler import handler  # noqa: E402
from run_tool_bench import ANSWER_FORMAT, ESCALATOR, is_correct, parse_answer, summarise, with_answer_format  # noqa: E402,E501

from escalator.agent import CLARIFY_PROMPT, SYSTEM_PROMPT, Escalator, Reply  # noqa: E402
from escalator.patterns import AdequacyGate, TierRouter  # noqa: E402
from escalator.tools import RunBudget, fix_escaped_newlines, format_result, make_run_python  # noqa: E402
from test_escalator import FakeDecider  # noqa: E402

# ----------------------------------------------------------------------------- Lambda handler


def test_handler_returns_what_the_program_prints():
    assert handler({"code": "print(6 * 7)"}) == {"stdout": "42\n", "stderr": "", "exit_code": 0, "timed_out": False}


def test_handler_hides_the_functions_aws_credentials(monkeypatch):
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "do-not-leak")
    result = handler({"code": "import os; print(os.environ.get('AWS_SECRET_ACCESS_KEY'))"})
    assert "do-not-leak" not in result["stdout"]


def test_handler_stops_runaway_code():
    assert handler({"code": "while True: pass", "timeout": 1})["timed_out"] is True


def test_handler_reports_errors():
    result = handler({"code": "1 / 0"})
    assert result["exit_code"] == 1 and "ZeroDivisionError" in result["stderr"]


# ----------------------------------------------------------------------------- the Strands tool


def test_tool_runs_code_through_the_invoker():
    seen = []

    def invoke(payload):
        seen.append(payload)
        return handler(payload)

    run_python = make_run_python(invoke)
    assert run_python.tool_name == "run_python"
    assert "42" in run_python(code="print(6 * 7)")
    assert seen == [{"code": "print(6 * 7)"}]


def test_tool_logs_each_run():
    log = []
    make_run_python(handler, log=log)(code="print(2 + 2)")
    assert log[0]["code"] == "print(2 + 2)" and log[0]["result"]["stdout"] == "4\n"


def test_cli_shows_the_code_that_ran():
    from escalator.cli import render_runs

    text = render_runs([{"code": "print(6 * 7)", "result": {"stdout": "42\n"}}])
    assert "run_python #1" in text and "print(6 * 7)" in text and "-> 42" in text


def test_cli_indents_multi_line_output_and_shows_runs_before_the_answer():
    from escalator.agent import Outcome
    from escalator.cli import render, render_runs

    text = render_runs([{"code": "print(1); print(2)", "result": {"stdout": "1\n2\n"}}])
    assert text.splitlines()[-1].endswith("     \033[32m2\033[0m")
    reply = Reply("us.amazon.nova-micro-v1:0", "2", 10, 5, 100.0, tool_calls=1)
    outcome = Outcome(answer="2", final_model=reply.model_id, replies=[reply],
                      route=TierRouter(FakeDecider(route=("small", 0.95))).route("q"))
    shown = render(outcome, [{"code": "print(2)", "result": {"stdout": "2\n"}}])
    assert shown.index("decider route") < shown.index("run_python #1") < shown.index("[nova-micro-v1]")


def test_format_result_shows_timeouts_and_errors():
    assert format_result({"timed_out": True, "stdout": "", "stderr": ""}).startswith("timed out")
    text = format_result({"exit_code": 1, "stdout": "", "stderr": "NameError: x"})
    assert "(nothing printed)" in text and "NameError" in text


def test_escalator_gives_tools_to_answering_models_but_not_to_clarify():
    calls = []

    def call(model_id, system_prompt, prompt, tools=None):
        calls.append((model_id, tools))
        return Reply(model_id, "answer", 10, 5, 100.0)

    tools = [make_run_python(handler)]
    for route in [("small", 0.95), ("large", 0.95), ("clarify", 0.95)]:
        Escalator(TierRouter(FakeDecider(route=route)), AdequacyGate(FakeDecider()), call=call,
                  small_model="us.amazon.nova-micro-v1:0",
                  large_model="us.anthropic.claude-haiku-4-5-20251001-v1:0", tools=tools)("q")
    assert [t for _, t in calls] == [tools, tools, None]


# ----------------------------------------------------------------------------- benchmark


@pytest.mark.parametrize("text,expected", [
    ("The result is 42.\nANSWER: 42", 42.0),
    ("ANSWER: $260,463.33", 260463.33),
    ("**ANSWER: 1111.111**", 1111.111),
    ("first ANSWER: 1 then corrected\nANSWER: 2", 2.0),
    ("no answer line here", None),
])
def test_parse_answer(text, expected):
    assert parse_answer(text) == expected


def test_is_correct_uses_the_tolerance():
    assert is_correct(386.66, 386.66, 0.011) and is_correct(386.67, 386.66, 0.011)
    assert not is_correct(386.70, 386.66, 0.011) and not is_correct(None, 1, 0)


def test_tool_bench_summary():
    small = "us.amazon.nova-micro-v1:0"
    rows = [{"id": "calc-01", "kind": "finance", "answer": 1.0, "model": small, "tool": tool,
             "correct": tool, "predicted": 1.0 if tool else 2.0, "cost": 0.00001,
             "latency_ms": 500.0, "tool_calls": int(tool)} for tool in (False, True)]
    text = summarise(rows, [(small, False), (small, True)])
    assert "| nova-micro-v1 | off | 0/1 |" in text and "| nova-micro-v1 | on | 1/1 |" in text
    assert "✗ 2.0" in text


def test_tool_bench_summary_with_repeats_reports_the_range_and_tool_use():
    small = "us.amazon.nova-micro-v1:0"
    rows = [{"id": f"calc-0{i}", "kind": "arithmetic", "answer": 1.0, "model": small, "tool": True, "rep": rep,
             "correct": not (rep == 1 and i == 1), "predicted": 1.0, "cost": 0.001, "latency_ms": 500.0,
             "tool_calls": 0 if (rep, i) == (0, 1) else 1, "path": None} for rep in (0, 1) for i in (1, 2)]
    text = summarise(rows, [(small, True)])
    assert "| nova-micro-v1 | on | 1.5/2 (1-2) | $0.002000 |" in text
    assert "| 3/4 |" in text and "✗ 1/2" in text and "✓ 2/2" in text


def test_tool_bench_summary_lists_escalator_routes():
    rows = [{"id": "calc-01", "kind": "finance", "answer": 1.0, "model": ESCALATOR, "tool": True, "correct": True,
             "predicted": 1.0, "cost": 0.001, "latency_ms": 900.0, "tool_calls": 1, "path": path}
            for path in ("direct-large", "direct-small")]
    assert "tool on: direct-large 1, direct-small 1" in summarise(rows, [(ESCALATOR, True)])


def test_answer_format_goes_to_answering_calls_only():
    seen = []
    call = with_answer_format(lambda model_id, system_prompt, prompt, tools=None: seen.append(system_prompt))
    call("m", SYSTEM_PROMPT, "q")
    call("m", CLARIFY_PROMPT, "q")
    assert seen == [f"{SYSTEM_PROMPT}\n\n{ANSWER_FORMAT}", CLARIFY_PROMPT]


def test_run_budget_cancels_tool_calls_past_the_limit():
    from types import SimpleNamespace

    from strands.hooks import HookProvider

    budget = RunBudget(limit=2)
    events = [SimpleNamespace(cancel_tool=False) for _ in range(4)]
    for event in events:
        budget.check(event)
    assert [bool(e.cancel_tool) for e in events] == [False, False, True, True]
    assert "Answer now" in events[-1].cancel_tool
    assert isinstance(budget, HookProvider)  # Strands accepts it in Agent(hooks=[...])


def test_escaped_newlines_are_fixed_only_when_that_makes_the_code_compile():
    broken = "def f(n):\\n    return n * 2\\nprint(f(21))"          # one line, literal backslash-n
    assert fix_escaped_newlines(broken) == "def f(n):\n    return n * 2\nprint(f(21))"
    assert handler({"code": fix_escaped_newlines(broken)})["stdout"] == "42\n"
    in_a_string = 'print("a\\nb")'                                 # valid as sent: leave it alone
    assert fix_escaped_newlines(in_a_string) == in_a_string
    assert fix_escaped_newlines("x = 1\nprint(x)") == "x = 1\nprint(x)"


def test_tool_runs_and_logs_the_fixed_code():
    log = []
    out = make_run_python(handler, log=log)(code="x = 6\\nprint(x * 7)")
    assert "42" in out and log[0]["code"] == "x = 6\nprint(x * 7)"
