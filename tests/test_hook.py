"""Tests for the auto-trigger hook's matching precision.

The hook fires on every message, so a false positive is expensive twice over:
it injects an irrelevant prompt AND records a use that never happened, which
corrupts the very stats used to decide what to calibrate.
"""
from iceni.integrations.hook import has_task_signal, instruction_zone, match_workflow


def _fires(text):
    """Mirror the hook's gate: what workflow (if any) would this message trigger?"""
    zone = instruction_zone(text)
    if not (has_task_signal(zone) or "```" in text):
        return None
    return match_workflow(zone)


def test_real_request_still_fires():
    assert _fires("please review this code:\n```python\ndef f(): pass\n```") == "review"
    assert _fires("write tests for this module") == "test-gen"
    assert _fires("refactor this function please") == "refactor"


def test_pasted_transcript_does_not_fire():
    """Regression: an incidental word deep in pasted content must not trigger.

    This is a real misfire — 'Disk Clean-up' quoted inside a pasted chat log
    matched the `refactor` triggers and logged a phantom use.
    """
    msg = (
        "Hey! Just checking in on this. Please can you do some checks to see "
        "whether this has been functioning correctly? Below is the chat I had:\n\n"
        + "Some long pasted conversation about browsers. " * 20
        + "BleachBit or Disk Clean-up, both of which you have installed, would help."
    )
    assert _fires(msg) is None


def test_trigger_word_only_deep_in_body_does_not_fire():
    msg = "Here is the transcript you asked for:\n\n" + ("filler text. " * 60) + " refactor"
    assert _fires(msg) is None


def test_plain_chat_does_not_fire():
    assert _fires("what's the weather in Norwich?") is None
    assert _fires("thanks, that worked!") is None
