"""Explicit-state, offline forward damage; never automatically consumes video state."""
from .engine import calculate,calculate_scenarios
from .inverse import infer_attack_stat
__all__=['calculate','calculate_scenarios','infer_attack_stat']
