"""Offline M3.4.1 beliefs; no StateEngine mutation or empirical priors."""
VERSION = 'speed-inference-v1'

from .domains import configuration_space
from .posterior import SpeedBelief, BeliefBank, infer

__all__ = ['configuration_space', 'SpeedBelief', 'BeliefBank', 'infer']
