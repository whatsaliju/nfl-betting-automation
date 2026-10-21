# Engine 2026.9 replay without look-ahead

Run Oct 21 2026 with `scripts/replay_2025_engine.py --stage final` after the review fixes (#243) and the
look-ahead fixes in this PR: referee trends use only games before the replayed week, and rest days come
from the replayed season. Picks are graded against nflverse final scores at the line in the pick.

| Window | Record | Win % | Spreads | Totals |
|---|---:|---:|---:|---:|
| 2025 Weeks 11-18 | 4-4 | 50.0% | 2-0 | 2-4 |
| 2026 Weeks 1-6 | 10-8 | 55.6% | 3-6 | 7-2 |
| **Both** | **14-12** | **53.8%** | 5-6 | 9-6 |

By label: Targeted plays 6-7 (46.2%), leans 8-5 (61.5%).

The earlier replay of the same 2025 window (Aug 2026, engine 2026.1 with referee look-ahead) reported 14-4.
Without look-ahead and with today's rules the same weeks go 4-4, so that 14-4 should not be used as
evidence. 26 picks is far too few to show an edge either way; break-even at -110 is 52.4%.

Caveat: 2026 total picks average +2.1 points better than the nflverse closing total. The replay uses the
dated Action Network file closest before kickoff, which can be days earlier; that number is not verified.
