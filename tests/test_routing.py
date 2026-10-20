"""Smoke tests (run: python -m pytest -q)."""
from pathlib import Path
from src.routing import load_city, solve_route

ROOT = Path(__file__).resolve().parents[1]


def load():
    return load_city(ROOT / 'data')


def test_both_strategies_are_valid_closed_tours():
    nodes, streets, closures = load()
    for weight in [0, .5]:
        solution = solve_route(nodes, streets, closures, risk_weight=weight, backend='scipy')
        assert solution.route[0] == solution.route[-1] == 'DEPOT'
        assert len(set(solution.route[:-1])) == len(solution.route)-1
        assert set(nodes.loc[nodes.is_required == 1, 'node_id']) <= set(solution.route)


def test_risk_tradeoff_and_outages():
    nodes, streets, closures = load()
    fast = solve_route(nodes, streets, closures, risk_weight=0, backend='scipy')
    safe = solve_route(nodes, streets, closures, risk_weight=.5, backend='scipy')
    assert safe.distance_m >= fast.distance_m
    assert safe.risk_exposure_m < fast.risk_exposure_m
    assert abs(fast.distance_m - 3702) < 1e-6
    assert abs(safe.distance_m - 3831) < 1e-6
    for scenario in ['flash_flood', 'localized_outage']:
        solution = solve_route(nodes, streets, closures, scenario=scenario,
                               risk_weight=.5, backend='scipy')
        assert solution.route[0] == solution.route[-1] == 'DEPOT'
