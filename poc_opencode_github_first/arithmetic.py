"""Isolated Issue #19 fixture; not production code."""


def add(a, b):
    # Intentional Phase A defect: preserve for the Producer → Debugger handoff.
    return a - b
