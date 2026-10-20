"""Reproduce portfolio outputs: route plots, scenario metrics, and risk sweep."""
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src.routing import load_city, plot_network, solve_route

ROOT = Path(__file__).resolve().parent
FIGURES = ROOT / 'figures'
FIGURES.mkdir(exist_ok=True)


def main(backend='auto'):
    nodes, streets, closures = load_city(ROOT / 'data')

    fast = solve_route(nodes, streets, closures, risk_weight=0, backend=backend)
    safer = solve_route(nodes, streets, closures, risk_weight=.5, backend=backend)

    fig, axes = plt.subplots(1, 2, figsize=(15, 6), constrained_layout=True)
    plot_network(nodes, streets, fast.route, 'Shortest-distance plan', axes[0])
    plot_network(nodes, streets, safer.route, 'Risk-aware plan (weight = 0.5)', axes[1])
    fig.savefig(FIGURES / 'route_comparison.png', dpi=170, bbox_inches='tight')
    plt.close(fig)

    weights = [0, .1, .2, .3, .32, .35, .5, 1, 2]
    sweep = [solve_route(nodes, streets, closures, risk_weight=w, backend=backend)
             for w in weights]
    sweep_df = pd.DataFrame([{
        'risk_weight': s.risk_weight,
        'distance_m': s.distance_m,
        'risk_exposure_m': round(s.risk_exposure_m, 2),
        'objective': round(s.objective, 2),
        'runtime_s': round(s.runtime_s, 3),
        'backend': s.backend
    } for s in sweep])
    sweep_df.to_csv(ROOT / 'risk_sensitivity.csv', index=False)

    fig, ax = plt.subplots(figsize=(7.5, 5))
    ax.plot(sweep_df.risk_exposure_m, sweep_df.distance_m,
            marker='o', lw=2.1, color='#28598a')
    for row in sweep_df.itertuples():
        if row.risk_weight in {0, .32}:
            ax.annotate(f'weight={row.risk_weight:g}',
                        xy=(row.risk_exposure_m, row.distance_m),
                        xytext=(8, 8), textcoords='offset points', fontsize=9)
    ax.set_xlabel('Risk-weighted exposure (risk × meters) — lower is safer')
    ax.set_ylabel('Travel distance (meters)')
    ax.set_title('Distance–risk trade-off', pad=10)
    ax.grid(alpha=.2)
    fig.savefig(FIGURES / 'risk_tradeoff.png', dpi=170, bbox_inches='tight')
    plt.close(fig)

    scenario_list = [('normal', 0), ('normal', .5), ('flash_flood', 0),
                     ('flash_flood', .5), ('localized_outage', .5)]
    rows = []
    for scenario, weight in scenario_list:
        s = solve_route(nodes, streets, closures, scenario=scenario,
                        risk_weight=weight, backend=backend)
        rows.append(dict(scenario=scenario, risk_weight=weight,
                         distance_m=s.distance_m,
                         risk_exposure_m=round(s.risk_exposure_m, 2),
                         runtime_s=round(s.runtime_s, 3),
                         backend=s.backend,
                         route=' → '.join(s.route)))
    scenario_df = pd.DataFrame(rows)
    scenario_df.to_csv(ROOT / 'scenario_results.csv', index=False)

    print('FASTEST\n', ' → '.join(fast.route))
    print(f'Distance: {fast.distance_m:.0f} m; risk exposure: {fast.risk_exposure_m:.2f}')
    print('\nRISK AWARE\n', ' → '.join(safer.route))
    print(f'Distance: {safer.distance_m:.0f} m; risk exposure: {safer.risk_exposure_m:.2f}')
    print('\nSCENARIOS\n', scenario_df.drop(columns='route').to_string(index=False))
    print('\nOutputs saved to', FIGURES)
    return fast, safer, sweep_df, scenario_df


if __name__ == '__main__':
    main()
