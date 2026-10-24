import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "lambda" / "run_python")]

from handler import handler  # noqa: E402

from escalator import verify  # noqa: E402
from escalator.agent import Escalator, Reply, tool_results  # noqa: E402
from escalator.patterns import AdequacyGate, TierRouter  # noqa: E402
from escalator.tools import format_result  # noqa: E402
from test_escalator import FakeDecider  # noqa: E402

SMALL, LARGE = "us.amazon.nova-micro-v1:0", "us.anthropic.claude-haiku-4-5-20251001-v1:0"


def ran(code):
    """What run_python returns to the model for this program."""
    return format_result(handler({"code": code}))


def draft(answer, *programs):
    return Reply(SMALL, answer, 100, 20, 500.0, tool_calls=len(programs), tool_results=[ran(p) for p in programs])


# ----------------------------------------------------------------------------- the check


def test_printed_value_is_the_last_number_the_last_clean_program_printed():
    results = [ran("print('Monthly payment: $500')\nprint('Final balance: $260,463.33')"), ran("1 / 0")]
    assert verify.printed_value(results) == 260463.33
    assert verify.printed_value([ran("print('done')")]) is None


def test_two_grounded_runs_that_agree_are_accepted():
    check = verify.check(draft("It equals **361,105,294**.", "print(48917 * 7382)"),
                         draft("48,917 × 7,382 = 361105294", "x = 48917 * 7382\nprint(x)"))
    assert check.action == "accept" and "361105294" in check.reason


def test_a_formatting_slip_after_the_run_is_caught():
    # benchmark calc-03: the program printed 13678.52, the answer line said 1367852
    slip = draft("The result is 13678.52.\nANSWER: 1367852", "print(13678.52)")
    assert verify.check(slip, draft("ANSWER: 13678.52", "print(13678.52)")).action == "escalate"


def test_runs_that_disagree_are_escalated():
    check = verify.check(draft("ANSWER: 14.802", "print(14.802)"), draft("ANSWER: 14.6436", "print(14.6436)"))
    assert check.action == "escalate" and "disagree" in check.reason


def test_no_code_means_no_verification():
    assert verify.check(draft("Paris"), draft("Paris")).reason == "no code ran"


def test_tool_results_are_read_from_strands_messages():
    messages = [{"role": "assistant", "content": [{"toolUse": {"toolUseId": "1", "name": "run_python"}}]},
                {"role": "user", "content": [{"toolResult": {"toolUseId": "1", "status": "success",
                                                             "content": [{"text": "exit code 0\nstdout:\n42\n"}]}}]}]
    assert tool_results(messages) == ["exit code 0\nstdout:\n42\n"]


# ----------------------------------------------------------------------------- verify mode in the cascade


class Scripted:
    """A CallModel that returns queued small-model drafts and a fixed large-model answer."""

    def __init__(self, *drafts):
        self.drafts, self.calls = list(drafts), []

    def __call__(self, model_id, system_prompt, prompt, tools=None):
        self.calls.append((model_id, bool(tools)))
        if model_id == SMALL:
            return self.drafts.pop(0)
        return Reply(LARGE, "ANSWER: 361105294", 900, 80, 3000.0, tool_calls=1)


def run(route, call, gate=0.95):
    decider = FakeDecider(route=route, answers=gate)
    return Escalator(TierRouter(decider), AdequacyGate(decider), call=call, small_model=SMALL,
                     large_model=LARGE, tools=["run_python"], verify=True)("What is 48,917 × 7,382?")


def test_verified_answers_stay_on_the_small_model_even_on_a_large_route():
    call = Scripted(draft("ANSWER: 361105294", "print(48917 * 7382)"), draft("361,105,294", "print(48917*7382)"))
    outcome = run(("large", 0.95), call)
    assert outcome.path == "verified" and outcome.final_model == SMALL
    assert [m for m, _ in call.calls] == [SMALL, SMALL]


def test_a_failed_check_goes_to_the_large_model_with_the_tool():
    call = Scripted(draft("ANSWER: 361049194", "print(361049194)"), draft("ANSWER: 361105294", "print(48917 * 7382)"))
    outcome = run(("small", 0.95), call)
    assert outcome.path == "escalated" and outcome.final_model == LARGE
    assert call.calls[-1] == (LARGE, True) and len(outcome.replies) == 3


def test_questions_without_code_fall_back_to_the_gate():
    call = Scripted(draft("Canberra"), draft("Canberra"))
    outcome = run(("small", 0.95), call, gate=0.95)
    assert outcome.path == "direct-small" and outcome.final_model == SMALL and outcome.gate.action == "accept"


def test_a_draft_that_errors_escalates_instead_of_failing_the_question():
    class Flaky(Scripted):
        def __call__(self, model_id, system_prompt, prompt, tools=None):
            if model_id == SMALL and len(self.calls) == 0:
                self.calls.append((model_id, True))
                raise RuntimeError("Model produced invalid sequence as part of ToolUse")
            return super().__call__(model_id, system_prompt, prompt, tools)

    call = Flaky(draft("ANSWER: 361105294", "print(48917 * 7382)"))
    outcome = run(("small", 0.95), call)
    assert outcome.final_model == LARGE and outcome.path == "escalated"
    assert outcome.check.reason == "a draft failed: RuntimeError"


def test_summary_survives_a_row_without_a_route():
    sys.path.insert(0, str(ROOT / "bench"))
    from run_tool_bench import VERIFY, summarise

    rows = [{"id": "calc-13", "kind": "counting", "answer": 242, "model": VERIFY, "tool": True, "rep": 0,
             "correct": ok, "predicted": 242.0 if ok else None, "cost": 0.0, "latency_ms": 1.0, "tool_calls": 1,
             "path": "verified" if ok else None} for ok in (True, False)]
    assert "tool on: error 1, verified 1" in summarise(rows, [(VERIFY, True)])
