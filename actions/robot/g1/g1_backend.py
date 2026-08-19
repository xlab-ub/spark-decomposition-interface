"""Unitree G1 real-robot backend (unitree_sdk2py).

Selected with SPARK_ROBOT_BACKEND=g1. Not implemented yet: the factory below
raises so the actions server fails loudly instead of silently running noop.
"""


def create_g1_backend(connection_settings=None, audio=False):
    raise NotImplementedError(
        "SPARK_ROBOT_BACKEND=g1 (real Unitree G1) is not implemented yet. "
        "Use g1_noop for a dry run."
    )


__all__ = ["create_g1_backend"]
