"""
code_rhetoric.py
----------------
Applies the project's rhetorical coding scheme to extracted speaker turns.
 
Coding dimensions (0–3 scale per dimension per party per session):
    0 = no focus
    1 = minor / mentioned in passing
    2 = moderate / explicitly argued
    3 = dominant / central to speech
 
Dimensions:
    1. rechtsextremismus      — right-wing extremist antisemitism as primary frame
    2. islamist_immigration   — Islamist / immigration-linked antisemitism as primary frame
    3. wissenschaftsfreiheit  — definitional contestation and academic freedom
    4. bildung_erinnerung     — education and memory culture
    5. israel_staatsraeson    — Israel's right to exist / German Staatsräson
 
Usage:
    python code_rhetoric.py <speakers_json> [--output <output_file>]
 
    Or import and use code_party_turns() directly.
"""
 
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
 
 
# ── Keyword clusters for each dimension ───────────────────────────────────────
 
DIMENSION_KEYWORDS: dict[str, list[str]] = {
    "rechtsextremismus": [
        r"rechtsextrem",
        r"rechtsradikal",
        r"neonazi",
        r"vogelschiss",
        r"afd.*(antisemit|vogelschiss)",
        r"sächsische.?separatist",
        r"gauland",
        r"halle.*synagoge",
        r"völkisch",
        r"nationalsozialist",
        r"rechtsterror",
    ],
    "islamist_immigration": [
        r"islamist",
        r"eingewandert.*antisemit",
        r"importiert.*antisemit",
        r"zuwander.*antisemit",
        r"muslimisch.*antisemit",
        r"antisemit.*muslim",
        r"nordafrika",
        r"nahen.*osten.*antisemit",
        r"antisemit.*nahen.*osten",
        r"abschieb",
        r"masseneinwanderung",
    ],
    "wissenschaftsfreiheit": [
        r"wissenschaftsfreiheit",
        r"kunstfreiheit",
        r"meinungsfreiheit",
        r"ihra.defin",
        r"jerusalem.*erklärung",
        r"wissenschaftlich.*umstritt",
        r"förder.*kriterien",
        r"förder.*antisemit",
        r"fördermittel.*definition",
        r"hochschulrektorenkonferenz",
        r"ulrich.?herbert",
    ],
    "bildung_erinnerung": [
        r"reichspogromnacht",
        r"shoah",
        r"holocaust",
        r"gedenkstätt",
        r"erinnerungskultur",
        r"politische.bildung",
        r"schüler",
        r"hochschul.*antisemit",
        r"antisemit.*hochschul",
        r"bildungseinrichtung",
        r"auschwitz",
        r"geschichtsunterricht",
    ],
    "israel_staatsraeson": [
        r"staatsräson",
        r"existenzrecht.*israel",
        r"israel.*existenzrecht",
        r"sicherheit.*israel",
        r"israel.*sicherheit",
        r"bds",
        r"boykott.*israel",
        r"zweistaatenlösung",
        r"einzige.*demokratie.*nahen.*osten",
        r"7\.\s*oktober",
        r"hamas.*terror",
    ],
}
 
 
def score_passage(text: str) -> dict[str, int]:
    """
    Score a single passage on all five dimensions.
    Scoring heuristic:
        3+ keyword matches → score 3
        2 matches          → score 2
        1 match            → score 1
        0 matches          → score 0
    """
    scores = {}
    text_lower = text.lower()
    for dim, patterns in DIMENSION_KEYWORDS.items():
        hits = sum(1 for p in patterns if re.search(p, text_lower))
        scores[dim] = min(hits, 3)
    return scores
 
 
def code_party_turns(turns: list[dict]) -> dict[str, dict[str, int]]:
    """
    Score all speaker turns and aggregate to party level.
    Returns: { party: { dimension: max_score_across_speakers } }
    """
    party_scores: dict[str, dict[str, list[int]]] = defaultdict(
        lambda: {dim: [] for dim in DIMENSION_KEYWORDS}
    )
 
    for turn in turns:
        party = turn.get("party") or "Unidentified"
        if party in ("Präsidium", "Bundesregierung", None):
            continue
        scores = score_passage(turn["text"])
        for dim, score in scores.items():
            party_scores[party][dim].append(score)
 
    # Aggregate: use the maximum score per dimension per party
    # (reflects the strongest position taken by any speaker in the faction)
    aggregated = {}
    for party, dim_scores in party_scores.items():
        aggregated[party] = {
            dim: max(scores) if scores else 0
            for dim, scores in dim_scores.items()
        }
 
    return aggregated
 
 
def code_session_from_file(path: Path) -> dict:
    """Load a speakers JSON and return coded party positions."""
    turns = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(turns, dict):
        # by_party format: flatten
        flat = []
        for party_turns in turns.values():
            flat.extend(party_turns)
        turns = flat
    return code_party_turns(turns)
 
 
def compare_sessions(results: dict[str, dict]) -> dict:
    """
    Compare coded results across multiple sessions.
 
    Args:
        results: { session_id: { party: { dimension: score } } }
 
    Returns a diff showing changes per party per dimension.
    """
    session_ids = list(results.keys())
    if len(session_ids) < 2:
        raise ValueError("Need at least two sessions to compare.")
 
    s1, s2 = session_ids[0], session_ids[1]
    r1, r2 = results[s1], results[s2]
 
    all_parties = sorted(set(r1.keys()) | set(r2.keys()))
    all_dims = list(DIMENSION_KEYWORDS.keys())
 
    diff = {}
    for party in all_parties:
        diff[party] = {}
        for dim in all_dims:
            score1 = r1.get(party, {}).get(dim, 0)
            score2 = r2.get(party, {}).get(dim, 0)
            diff[party][dim] = {
                s1: score1,
                s2: score2,
                "delta": score2 - score1,
            }
 
    return diff
 
 
def print_summary(coded: dict[str, dict[str, int]], session_id: str = ""):
    """Pretty-print coded results to stdout."""
    dims = list(DIMENSION_KEYWORDS.keys())
    col_w = 22
 
    header = f"{'Party':<20}" + "".join(f"{d[:col_w]:<{col_w}}" for d in dims)
    print(f"\n{'─' * len(header)}")
    if session_id:
        print(f"  Session {session_id}")
    print(f"{'─' * len(header)}")
    print(header)
    print(f"{'─' * len(header)}")
 
    for party, scores in sorted(coded.items()):
        row = f"{party:<20}"
        for dim in dims:
            score = scores.get(dim, 0)
            bar = "█" * score + "░" * (3 - score)
            row += f"{bar} ({score})          "[:col_w]
        print(row)
    print(f"{'─' * len(header)}\n")
 
 
def main():
    parser = argparse.ArgumentParser(
        description="Apply rhetorical coding to Bundestag speaker turns"
    )
    parser.add_argument("inputs", nargs="+", help="Speaker JSON files (one per session)")
    parser.add_argument("--output", default=None, help="Write results to JSON file")
    args = parser.parse_args()
 
    results = {}
    for path_str in args.inputs:
        path = Path(path_str)
        session_id = path.stem.split("_")[0]
        print(f"Coding {path.name}...")
        coded = code_session_from_file(path)
        results[session_id] = coded
        print_summary(coded, session_id)
 
    if len(results) >= 2:
        print("Cross-session comparison:")
        diff = compare_sessions(results)
        for party, dims in diff.items():
            deltas = {d: v["delta"] for d, v in dims.items() if v["delta"] != 0}
            if deltas:
                print(f"  {party}: {deltas}")
 
    if args.output:
        out = Path(args.output)
        out.write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\nResults written to {out}")
 
 
if __name__ == "__main__":
    main()
