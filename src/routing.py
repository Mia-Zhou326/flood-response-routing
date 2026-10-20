"""Risk-aware emergency routing on a synthetic street network.

This independently authored portfolio example optimizes a closed route that
visits designated service sites exactly once and never revisits a junction.
Gurobi is preferred when present; SciPy HiGHS provides a no-license fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix


@dataclass
class RouteResult:
    route: list[str]
    distance_m: float
    risk_exposure_m: float
    objective: float
    runtime_s: float
    backend: str
    risk_weight: float
    scenario: str


def load_city(data_dir: Path | str = 'data') -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load nodes, undirected streets, and closures; validate basic data integrity."""
    base = Path(data_dir)
    nodes = pd.read_csv(base / 'nodes.csv')
    streets = pd.read_csv(base / 'streets.csv')
    closures = pd.read_csv(base / 'closures.csv')
    assert len(nodes.node_id) == len(set(nodes.node_id)), 'duplicate node IDs'
    assert len(streets.street_id) == len(set(streets.street_id)), 'duplicate street IDs'
    assert set(streets[['from_node', 'to_node']].to_numpy().flatten()) <= set(nodes.node_id)
    assert nodes.is_required.sum() >= 3
    assert len(nodes[nodes.kind == 'hub']) == 1
    assert streets.length_m.gt(0).all()
    assert streets.risk_score.between(0, 1).all()
    assert set(closures.street_id) <= set(streets.street_id)
    return nodes, streets, closures


def _get_backend(backend: str) -> str:
    if backend not in {'auto', 'gurobi', 'scipy'}:
        raise ValueError('backend must be auto, gurobi, or scipy')
    if backend == 'scipy':
        return 'scipy'
    try:
        import gurobipy  # noqa: F401
        return 'gurobi'
    except ImportError:
        if backend == 'gurobi':
            raise ImportError('gurobipy is not installed. Use backend="scipy".')
        return 'scipy'


def solve_route(
    nodes: pd.DataFrame,
    streets: pd.DataFrame,
    closures: pd.DataFrame | None = None,
    scenario: str = 'normal',
    risk_weight: float = 0.0,
    backend: str = 'auto',
    time_limit: float = 90,
) -> RouteResult:
    """Solve selective undirected TSP with MTZ subtour elimination.

    Objective: sum(length_m + risk_weight * length_m * risk_score)
    Both travel distance and risk exposure are measured in meters (risk is
    dimensionless); risk_weight is an explicit preference parameter.
    """
    if risk_weight < 0:
        raise ValueError('risk_weight must be nonnegative')
    available = streets.copy()
    if closures is not None and len(closures):
        blocked = set(closures.loc[closures.scenario == scenario, 'street_id'])
        available = available[~available.street_id.isin(blocked)].copy()
    if available.empty:
        raise ValueError('No streets available under this scenario.')

    node_ids = nodes.node_id.tolist()
    hub = str(nodes.loc[nodes.kind == 'hub', 'node_id'].iloc[0])
    required = set(nodes.loc[nodes.is_required == 1, 'node_id'])
    required.add(hub)
    n = len(node_ids)
    arcs: list[tuple[str, str]] = []
    props: dict[tuple[str, str], tuple[float, float, str]] = {}
    for s in available.itertuples(index=False):
        a, b = str(s.from_node), str(s.to_node)
        for i, j in [(a, b), (b, a)]:
            arcs.append((i, j))
            props[(i, j)] = (float(s.length_m), float(s.risk_score), str(s.street_id))

    method = _get_backend(backend)
    started = time.perf_counter()
    if method == 'gurobi':
        selected = _solve_gurobi(node_ids, required, hub, arcs, props, risk_weight, time_limit)
    else:
        selected = _solve_scipy(node_ids, required, hub, arcs, props, risk_weight, time_limit)
    runtime = time.perf_counter() - started

    next_node = {i: j for i, j in selected}
    route = [hub]
    cursor = hub
    for _ in range(n + 1):
        cursor = next_node.get(cursor)
        if cursor is None:
            raise RuntimeError('Solver returned an incomplete route.')
        route.append(cursor)
        if cursor == hub:
            break
    else:
        raise RuntimeError('Solver did not return to the hub.')

    if set(route[:-1]) != set(next_node) or len(set(route[:-1])) != len(route)-1:
        raise RuntimeError('Unexpected subtour or repeated intersection.')
    assert required <= set(route), 'required stop missing'
    taken_ids = [props[(i, j)][2] for i, j in zip(route[:-1], route[1:])]
    assert len(set(taken_ids)) == len(taken_ids), 'reused street'
    distance = sum(props[(i, j)][0] for i, j in zip(route[:-1], route[1:]))
    exposure = sum(props[(i, j)][0] * props[(i, j)][1] for i, j in zip(route[:-1], route[1:]))
    return RouteResult(route, distance, exposure, distance + risk_weight*exposure,
                       runtime, method, risk_weight, scenario)


def _solve_gurobi(node_ids, required, hub, arcs, props, risk_weight, time_limit):
    import gurobipy as gp
    from gurobipy import GRB

    n = len(node_ids)
    m = gp.Model('risk_aware_rescue_route')
    m.Params.OutputFlag = 0
    m.Params.TimeLimit = time_limit
    x = m.addVars(arcs, vtype=GRB.BINARY, name='arc')
    u = m.addVars([i for i in node_ids if i != hub], lb=1, ub=n-1,
                  vtype=GRB.CONTINUOUS, name='order')
    m.setObjective(gp.quicksum(props[a][0] * (1 + risk_weight*props[a][1]) * x[a]
                               for a in arcs), GRB.MINIMIZE)
    for i in node_ids:
        outflow = gp.quicksum(x[a] for a in arcs if a[0] == i)
        inflow = gp.quicksum(x[a] for a in arcs if a[1] == i)
        m.addConstr(inflow == outflow, name=f'flow_{i}')
        if i in required:
            m.addConstr(outflow == 1, name=f'required_{i}')
        else:
            m.addConstr(outflow <= 1, name=f'optional_{i}')
    for i, j in arcs:
        if i < j:
            m.addConstr(x[i, j] + x[j, i] <= 1, name=f'road_{i}_{j}')
        if i != hub and j != hub:
            m.addConstr(u[i] - u[j] + (n-1)*x[i, j] <= n-2,
                        name=f'mtz_{i}_{j}')
    m.optimize()
    if m.Status != GRB.OPTIMAL:
        raise RuntimeError(f'Gurobi did not prove optimality (status {m.Status}).')
    return [(i, j) for i, j in arcs if x[i, j].X > .5]


def _solve_scipy(node_ids, required, hub, arcs, props, risk_weight, time_limit):
    """The same MTZ MIP using SciPy's HiGHS MILP interface."""
    n = len(node_ids)
    na = len(arcs)
    arc_index = {a: k for k, a in enumerate(arcs)}
    nonhub = [i for i in node_ids if i != hub]
    order_index = {i: na + k for k, i in enumerate(nonhub)}
    nvars = na + len(nonhub)

    c = np.zeros(nvars)
    lower = np.zeros(nvars)
    upper = np.ones(nvars)
    upper[na:] = n-1
    lower[na:] = 1
    integrality = np.zeros(nvars, dtype=int)
    integrality[:na] = 1
    for arc, k in arc_index.items():
        length, risk, _ = props[arc]
        c[k] = length * (1 + risk_weight * risk)

    rows = []
    lb = []
    ub = []
    def add_row(terms, low=-np.inf, high=np.inf):
        rows.append(terms)
        lb.append(low)
        ub.append(high)

    for i in node_ids:
        flow = {}
        outgoing = {}
        for a, k in arc_index.items():
            if a[0] == i:
                flow[k] = flow.get(k, 0) + 1
                outgoing[k] = 1
            if a[1] == i:
                flow[k] = flow.get(k, 0) - 1
        add_row(flow, 0, 0)
        if i in required:
            add_row(outgoing, 1, 1)
        else:
            add_row(outgoing, high=1)

    for (i, j), k in arc_index.items():
        if i < j:
            add_row({k: 1, arc_index[(j, i)]: 1}, high=1)
        if i != hub and j != hub:
            add_row({order_index[i]: 1, order_index[j]: -1, k: n-1}, high=n-2)

    I, J, V = [], [], []
    for r, terms in enumerate(rows):
        for k, v in terms.items():
            if v != 0:
                I.append(r)
                J.append(k)
                V.append(v)
    mat = coo_matrix((V, (I, J)), shape=(len(rows), nvars)).tocsr()
    result = milp(c, integrality=integrality, bounds=Bounds(lower, upper),
                  constraints=LinearConstraint(mat, lb, ub),
                  options={'time_limit': time_limit, 'mip_rel_gap': 0.0})
    if not result.success:
        raise RuntimeError(f'SciPy HiGHS did not prove optimality: {result.message}')
    return [a for a, k in arc_index.items() if result.x[k] > 0.5]


def plot_network(nodes, streets, route: list[str] | None = None,
                 title: str = 'Fictional city street network', ax=None):
    """Render all streets and optionally overlay a solved directed route."""
    if ax is None:
        _, ax = plt.subplots(figsize=(9, 7))
    positions = {r.node_id: (r.x_m, r.y_m) for r in nodes.itertuples(index=False)}
    graph = nx.Graph()
    graph.add_nodes_from(positions)
    for s in streets.itertuples(index=False):
        graph.add_edge(s.from_node, s.to_node)
    nx.draw_networkx_edges(graph, positions, ax=ax, edge_color='#d2d9e2', width=2.0)
    if route:
        for a, b in zip(route[:-1], route[1:]):
            x1, y1 = positions[a]
            x2, y2 = positions[b]
            dx, dy = x2-x1, y2-y1
            ax.annotate('', xy=(x2 - dx*0.11, y2 - dy*0.11),
                        xytext=(x1 + dx*0.11, y1 + dy*0.11),
                        arrowprops=dict(arrowstyle='-|>', mutation_scale=15,
                                        color='#ef6c38', lw=2.7), zorder=5)
    regular = nodes[nodes.is_required == 0]
    major = nodes[(nodes.is_required == 1) & (nodes.kind != 'hub')]
    hub = nodes[nodes.kind == 'hub']
    for df, color, size in [(regular, '#cbd5e1', 43), (major, '#1d8f83', 155),
                            (hub, '#24476f', 220)]:
        ax.scatter(df.x_m, df.y_m, s=size, c=color, ec='white', lw=1.4, zorder=6)
    for s in pd.concat([major, hub]).itertuples(index=False):
        ax.annotate(s.label, (s.x_m, s.y_m), xytext=(9, 8),
                    textcoords='offset points', fontsize=8, fontweight='bold')
    ax.set_title(title, fontsize=14, fontweight='bold', pad=13)
    ax.set_xlabel('East–west coordinate (m)')
    ax.set_ylabel('North–south coordinate (m)')
    ax.set_aspect('equal')
    ax.grid(alpha=.16)
    ax.spines[['top', 'right']].set_visible(False)
    return ax
