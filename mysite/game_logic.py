import random
from collections import Counter
from typing import Dict, Iterable, List, Optional, Tuple


def decide_winner(alive_mafia: int, alive_others: int) -> Optional[str]:
    if alive_mafia <= 0:
        return "CITIZENS"
    if alive_mafia >= alive_others:
        return "MAFIA"
    return None


def pick_kill_target(target_ids: Iterable[int], rng=random) -> Optional[int]:
    counts = Counter(target_ids)
    if not counts:
        return None
    top = max(counts.values())
    leaders = sorted(t for t, c in counts.items() if c == top)
    return rng.choice(leaders)


def tally_votes(votes: Iterable[Tuple[int, int]]) -> Tuple[Dict[int, int], List[int]]:
    counts: Dict[int, int] = {}
    for _voter, target in votes:
        counts[target] = counts.get(target, 0) + 1
    if not counts:
        return counts, []
    top = max(counts.values())
    return counts, [t for t, c in counts.items() if c == top]


def validate_role_counts(total_players: int, mafia: int, doctor: int, commissar: int) -> Optional[str]:
    if min(mafia, doctor, commissar) < 0:
        return "Количество ролей не может быть отрицательным"
    if mafia < 1:
        return "Количество мафии должно быть минимум 1"
    if mafia + doctor + commissar > total_players:
        return "Количество ролей больше количества игроков"
    if mafia * 2 >= total_players:
        return "Мафии должно быть строго меньше половины игроков"
    return None


def role_stat_field(role: str) -> str:
    return {
        "mafia": "mafia_games",
        "doctor": "doctor_games",
        "commissar": "detective_games",
        "civilian": "citizen_games",
    }[role]


def most_played_role(roles: Dict[str, int]) -> Optional[str]:
    if not roles or max(roles.values()) == 0:
        return None
    return max(roles, key=roles.get)
