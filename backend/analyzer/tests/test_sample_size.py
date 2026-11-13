import pytest
from abkit import mde_two_proportions


def test_solve_for_n(api):
    r = api.post("/api/sample-size", {"base_rate": 0.1, "mde_abs": 0.01, "alpha": 0.05, "power": 0.8}, format="json")
    assert r.status_code == 200
    b = r.json()
    assert b["solved_for"] == "n_per_arm"
    n = b["n_per_arm"]
    assert mde_two_proportions(0.1, n) <= 0.01 < mde_two_proportions(0.1, n - 1)
    assert len(b["curve"]) == 30
    assert all(p["mde_abs"] > q["mde_abs"] for p, q in zip(b["curve"], b["curve"][1:], strict=False))


def test_solve_for_mde(api):
    r = api.post("/api/sample-size", {"base_rate": 0.10617, "n_per_arm": 21306}, format="json")
    b = r.json()
    assert b["solved_for"] == "mde_abs" and b["mde_abs"] == mde_two_proportions(0.10617, 21306)
    assert len(b["curve"]) == 30


@pytest.mark.parametrize(
    "payload",
    [
        {"base_rate": 0.1},
        {"base_rate": 0.1, "mde_abs": 0.01, "n_per_arm": 100},
        {"base_rate": 1.5, "mde_abs": 0.01},
        {"base_rate": 0.1, "mde_abs": -0.01},
        {"base_rate": 0.1, "mde_abs": 0.01, "alpha": 0.5},
        {"base_rate": 0.1, "mde_abs": 0.01, "power": 1.2},
        {"base_rate": 0.1, "n_per_arm": 1},
    ],
)
def test_invalid_is_422(api, payload):
    r = api.post("/api/sample-size", payload, format="json")
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"
