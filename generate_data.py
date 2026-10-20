"""Generate deterministic *fictional* nodes and roads. Nothing is scraped."""
from pathlib import Path
import math
import random
import pandas as pd

SEED = 2026
GRID = 5
STEP_M = 220
OUT = Path(__file__).resolve().parent / 'data'
OUT.mkdir(exist_ok=True)

required = {
    (0, 0): ('DEPOT', 'Emergency operations hub', 'hub'),
    (0, 3): ('CLINIC', 'Mobile health clinic', 'service'),
    (2, 2): ('PANTRY', 'Community food pantry', 'service'),
    (4, 0): ('WATER', 'Drinking water station', 'service'),
    (3, 4): ('SHELTER', 'Temporary shelter', 'service'),
    (1, 3): ('POWER', 'Portable power depot', 'service'),
}

def node(r, c):
    return required[(r, c)][0] if (r, c) in required else f'J{r}{c}'

nodes = []
for r in range(GRID):
    for c in range(GRID):
        name, label, kind = required.get((r, c), (f'J{r}{c}', f'Junction {r},{c}', 'junction'))
        nodes.append(dict(node_id=name, x_m=c*STEP_M, y_m=(GRID-1-r)*STEP_M,
                          label=label, kind=kind, is_required=int((r,c) in required)))

# An invented street network: several missing links and seven connecting diagonals.
missing = {frozenset((a, b)) for a, b in [
    ((3,1),(3,2)), ((1,1),(2,1)), ((2,3),(3,3))
]}
links = []
for r in range(GRID):
    for c in range(GRID):
        for rr, cc in [(r+1,c),(r,c+1)]:
            if rr < GRID and cc < GRID and frozenset(((r,c),(rr,cc))) not in missing:
                links.append(((r,c),(rr,cc)))
links += [((0,1),(1,2)), ((1,2),(2,3)), ((2,0),(3,1)),
          ((3,2),(4,3)), ((2,2),(3,3)), ((1,0),(2,1)), ((0,3),(1,4)),
          ((1,3),(2,4)), ((3,0),(4,1)), ((2,1),(3,2)), ((0,2),(1,3))]

random.seed(SEED)
streets = []
for k, ((r1,c1),(r2,c2)) in enumerate(links, 1):
    length = round(math.hypot(c2-c1, r2-r1)*STEP_M)
    # Higher flood exposure on fictional low-lying north-east corridors.
    avg_c = (c1+c2)/2
    avg_r = (r1+r2)/2
    base = .08 + .16 * avg_c / 4 + .10 * (4 - avg_r) / 4
    score = min(.95, round(base + random.uniform(0, .52), 2))
    # The central low-lying crossing is short but highly exposed;
    # its longer southern bypass is comparatively safer.
    special_risk = {frozenset(('J32', 'J42')): .94,
                    frozenset(('J41', 'J42')): .08,
                    frozenset(('J42', 'J43')): .05,
                    frozenset(('J43', 'J44')): .06,
                    frozenset(('SHELTER', 'J44')): .07}
    score = special_risk.get(frozenset((node(r1,c1), node(r2,c2))), score)
    streets.append(dict(street_id=f'R{k:02d}', from_node=node(r1,c1), to_node=node(r2,c2),
                        length_m=length, risk_score=score))

# Two separate invented closure scenarios, allowing sensitivity checks.
closures = [
    dict(scenario='flash_flood', street_id='R04', reason='standing water'),
    dict(scenario='flash_flood', street_id='R17', reason='culvert overflow'),
    dict(scenario='flash_flood', street_id='R30', reason='bridge inspection'),
    dict(scenario='localized_outage', street_id='R11', reason='debris'),
    dict(scenario='localized_outage', street_id='R22', reason='debris'),
]
pd.DataFrame(nodes).to_csv(OUT / 'nodes.csv', index=False)
pd.DataFrame(streets).to_csv(OUT / 'streets.csv', index=False)
pd.DataFrame(closures).to_csv(OUT / 'closures.csv', index=False)
print(f'Wrote {len(nodes)} nodes, {len(streets)} streets, {len(closures)} closure records.')
