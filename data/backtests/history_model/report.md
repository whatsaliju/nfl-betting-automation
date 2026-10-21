# History layer: walk-forward side and total models

Generated 2026-10-21T17:21:07+00:00. Trained on 2015-2025; each test season uses only earlier seasons. Graded at the closing line; break-even at -110 is 52.4%.

## Sides, all inputs (home cover)

Pooled 2018-2025: 2075 games, log loss 0.6958 (coin flip = 0.6931).

| Confidence | Picks | W-L | Win % | Seasons above 52.4% |
|---|---:|---:|---:|---:|
| 53%+ | 1112 | 567-545 | 51.0% | 2 of 8 |
| 55%+ | 633 | 327-306 | 51.7% | 3 of 8 |
| 57%+ | 308 | 157-151 | 51.0% | 4 of 8 |

| Season | Games | Log loss | 53%+ W-L | Win % |
|---|---:|---:|---:|---:|
| 2018 | 247 | 0.6884 | 79-67 | 54.1% |
| 2019 | 246 | 0.699 | 71-69 | 50.7% |
| 2020 | 256 | 0.6957 | 78-74 | 51.3% |
| 2021 | 268 | 0.6902 | 85-71 | 54.5% |
| 2022 | 261 | 0.698 | 80-78 | 50.6% |
| 2023 | 258 | 0.6958 | 70-65 | 51.8% |
| 2024 | 268 | 0.7061 | 67-81 | 45.3% |
| 2025 | 271 | 0.6934 | 37-40 | 48.0% |
| **2026 to date** | 87 | 0.6894 | 27-23 | 54.0% |

Final-model weights (per standard deviation; positive pushes toward home cover):

- `home_spread`: -0.087
- `warps_edge_early`: +0.082
- `home_ats_form`: -0.070
- `home_dog`: +0.070
- `away_ats_form`: +0.064
- `div_game`: -0.035
- `neutral`: +0.019
- `ref_home_cover`: +0.016
- `warps_edge`: -0.015
- `rest_diff`: +0.009

## Totals, all inputs (over)

Pooled 2018-2025: 2107 games, log loss 0.6953 (coin flip = 0.6931).

| Confidence | Picks | W-L | Win % | Seasons above 52.4% |
|---|---:|---:|---:|---:|
| 53%+ | 1155 | 593-562 | 51.3% | 3 of 8 |
| 55%+ | 671 | 346-325 | 51.6% | 4 of 8 |
| 57%+ | 331 | 176-155 | 53.2% | 3 of 8 |

| Season | Games | Log loss | 53%+ W-L | Win % |
|---|---:|---:|---:|---:|
| 2018 | 253 | 0.6853 | 75-57 | 56.8% |
| 2019 | 255 | 0.703 | 83-84 | 49.7% |
| 2020 | 251 | 0.7064 | 63-77 | 45.0% |
| 2021 | 269 | 0.6839 | 74-60 | 55.2% |
| 2022 | 268 | 0.699 | 76-85 | 47.2% |
| 2023 | 270 | 0.6878 | 70-49 | 58.8% |
| 2024 | 269 | 0.703 | 83-87 | 48.8% |
| 2025 | 272 | 0.6949 | 69-63 | 52.3% |
| **2026 to date** | 93 | 0.6873 | 15-10 | 60.0% |

Final-model weights (per standard deviation; positive pushes toward over):

- `wind`: -0.098
- `under_start`: +0.082
- `away_ou_form`: -0.060
- `home_ou_form`: -0.026
- `dome`: -0.017
- `total_line`: +0.016
- `temp_dev`: +0.011
- `div_game`: -0.007
- `ref_over`: -0.003

## Sides, lean (home cover)

Pooled 2018-2025: 2075 games, log loss 0.6929 (coin flip = 0.6931).

| Confidence | Picks | W-L | Win % | Seasons above 52.4% |
|---|---:|---:|---:|---:|
| 53%+ | 752 | 406-346 | 54.0% | 6 of 8 |
| 55%+ | 290 | 144-146 | 49.7% | 1 of 8 |
| 57%+ | 94 | 42-52 | 44.7% | 4 of 8 |

| Season | Games | Log loss | 53%+ W-L | Win % |
|---|---:|---:|---:|---:|
| 2018 | 247 | 0.687 | 35-23 | 60.3% |
| 2019 | 246 | 0.6936 | 52-45 | 53.6% |
| 2020 | 256 | 0.6926 | 59-41 | 59.0% |
| 2021 | 268 | 0.6905 | 66-48 | 57.9% |
| 2022 | 261 | 0.6904 | 55-46 | 54.5% |
| 2023 | 258 | 0.6956 | 57-55 | 50.9% |
| 2024 | 268 | 0.7006 | 53-63 | 45.7% |
| 2025 | 271 | 0.6927 | 29-25 | 53.7% |
| **2026 to date** | 87 | 0.6855 | 22-13 | 62.9% |

Final-model weights (per standard deviation; positive pushes toward home cover):

- `warps_edge_early`: +0.066
- `home_ats_form`: -0.053
- `away_ats_form`: +0.049
- `home_dog`: -0.001

## Totals, lean (over)

Pooled 2018-2025: 2107 games, log loss 0.6912 (coin flip = 0.6931).

| Confidence | Picks | W-L | Win % | Seasons above 52.4% |
|---|---:|---:|---:|---:|
| 53%+ | 790 | 436-354 | 55.2% | 5 of 8 |
| 55%+ | 355 | 188-167 | 53.0% | 5 of 8 |
| 57%+ | 117 | 61-56 | 52.1% | 4 of 8 |

| Season | Games | Log loss | 53%+ W-L | Win % |
|---|---:|---:|---:|---:|
| 2018 | 253 | 0.6906 | 19-11 | 63.3% |
| 2019 | 255 | 0.6883 | 34-23 | 59.7% |
| 2020 | 251 | 0.6949 | 46-42 | 52.3% |
| 2021 | 269 | 0.6838 | 66-40 | 62.3% |
| 2022 | 268 | 0.6909 | 65-53 | 55.1% |
| 2023 | 270 | 0.6869 | 70-47 | 59.8% |
| 2024 | 269 | 0.7006 | 72-76 | 48.6% |
| 2025 | 272 | 0.6936 | 64-62 | 50.8% |
| **2026 to date** | 93 | 0.6896 | 15-12 | 55.6% |

Final-model weights (per standard deviation; positive pushes toward over):

- `wind`: -0.080
- `under_start`: +0.076
- `away_ou_form`: -0.053
- `home_ou_form`: -0.022
