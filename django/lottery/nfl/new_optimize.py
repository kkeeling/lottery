from draftfast import rules
from draftfast.optimize import run_multi
from draftfast.orm import Player
from draftfast.csv_parse import salary_download


def simulate_contest(contest, projections):
    player_pool = []

    for p in projections:
        player_pool.append(Player(
            name=p.name,
            cost=p.salary,
            proj=float(p.projection),
            pos=p.position
        ))

    rosters, _ = run_multi(
        iterations=contest.max_entrants,
        rule_set=rules.FD_NFL_RULE_SET,
        player_pool=player_pool,
        verbose=True,
    )
