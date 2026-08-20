def create_g1_sim_backend(connection_settings=None, audio=False):
    raise NotImplementedError(
        "SPARK_ROBOT_BACKEND=g1_sim (Unitree G1 MuJoCo) is not implemented yet. "
        "Use g1_noop for a dry run."
    )


__all__ = ["create_g1_sim_backend"]
