"""Offline, explicit-state Speed/order constraints under versioned profiles."""
from .core import effective_speed
from .solver import infer_speed,compare_speed
__all__=['effective_speed','infer_speed','compare_speed']
