"""Escalator: a Strands agent that only pays for a big model when Strands Decider 2B says so."""

from .agent import Escalator, Outcome, Reply, bedrock_call
from .decider import Decider, ServerUnavailable
from .patterns import AdequacyGate, GatePolicy, TierRouter, Verdict

__all__ = [
    "AdequacyGate", "Decider", "Escalator", "GatePolicy", "Outcome", "Reply",
    "ServerUnavailable", "TierRouter", "Verdict", "bedrock_call",
]
