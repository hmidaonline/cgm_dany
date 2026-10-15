import pytest
import time
import numpy as np
import gymnasium as gym
from gymnasium.utils.env_checker import check_env
from app.ml.rl.env.glucose_env import GlycoTwinEnv

def test_gym_check_env_compliance():
    """Validates full compliance with Gymnasium API specifications using official check_env."""
    env = GlycoTwinEnv(seed=42)
    # Gymnasium official linter & validation suite
    check_env(env.unwrapped)

def test_gym_reset_and_step_contract():
    env = GlycoTwinEnv(seed=123)
    obs, info = env.reset(seed=123)

    assert isinstance(obs, np.ndarray)
    assert obs.shape == (9,)
    assert env.observation_space.contains(obs)
    assert isinstance(info, dict)
    assert "scenario_id" in info

    # Step
    action = np.array([0.2], dtype=np.float32)
    next_obs, reward, terminated, truncated, step_info = env.step(action)

    assert isinstance(next_obs, np.ndarray)
    assert env.observation_space.contains(next_obs)
    assert isinstance(reward, float)
    assert isinstance(terminated, bool)
    assert isinstance(truncated, bool)
    assert isinstance(step_info, dict)
    assert "shield" in step_info

def test_seed_reproducibility():
    """Verifies that two environments initialized with identical seed yield strictly identical trajectories."""
    env1 = GlycoTwinEnv(seed=999)
    env2 = GlycoTwinEnv(seed=999)

    obs1, _ = env1.reset(seed=999)
    obs2, _ = env2.reset(seed=999)
    np.testing.assert_allclose(obs1, obs2, rtol=1e-5)

    actions = [np.array([0.5], dtype=np.float32), np.array([-0.3], dtype=np.float32), np.array([0.0], dtype=np.float32)]
    for a in actions:
        o1, r1, t1, tr1, _ = env1.step(a)
        o2, r2, t2, tr2, _ = env2.step(a)
        np.testing.assert_allclose(o1, o2, rtol=1e-5)
        assert r1 == pytest.approx(r2, rel=1e-5)
        assert t1 == t2
        assert tr1 == tr2

def test_execution_speed_benchmark():
    """Verifies that the environment execution speed reaches high performance (> 10,000 steps/s)."""
    env = GlycoTwinEnv(seed=42)
    obs, _ = env.reset(seed=42)
    action = np.array([0.0], dtype=np.float32)

    n_steps = 20000
    t0 = time.perf_counter()
    for _ in range(n_steps):
        _, _, term, trunc, _ = env.step(action)
        if term or trunc:
            env.reset()
    elapsed = time.perf_counter() - t0

    steps_per_sec = n_steps / elapsed
    print(f"\n[BENCHMARK] GlycoTwinEnv execution speed: {steps_per_sec:,.0f} steps/second (target: > 10,000)")
    assert steps_per_sec >= 10000.0
