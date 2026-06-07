import type { Conference, ScheduleRow } from "../types";

export const weeks = Array.from({ length: 18 }, (_, index) => index + 1);

export const scheduleRows: ScheduleRow[] = [
  { Team: "ARI", W1: "@NO", W2: "CAR", W3: "@SF", W4: "SEA", W5: "TEN", W6: "@IND", W7: "GB", W8: "BYE", W9: "@DAL", W10: "@SEA", W11: "SF", W12: "JAX", W13: "@TB", W14: "LAR", W15: "@HOU", W16: "ATL", W17: "@CIN", W18: "@LAR" },
  { Team: "ATL", W1: "TB", W2: "@MIN", W3: "@CAR", W4: "WAS", W5: "BYE", W6: "BUF", W7: "@SF", W8: "MIA", W9: "@NE", W10: "@IND", W11: "CAR", W12: "@NO", W13: "@NYJ", W14: "SEA", W15: "@TB", W16: "@ARI", W17: "LAR", W18: "NO" },
  { Team: "BAL", W1: "@BUF", W2: "CLE", W3: "DET", W4: "@KC", W5: "HOU", W6: "LAR", W7: "BYE", W8: "CHI", W9: "@MIA", W10: "@MIN", W11: "@CLE", W12: "NYJ", W13: "CIN", W14: "PIT", W15: "@CIN", W16: "NE", W17: "@GB", W18: "@PIT" },
  { Team: "BUF", W1: "BAL", W2: "@NYJ", W3: "MIA", W4: "NO", W5: "NE", W6: "@ATL", W7: "BYE", W8: "@CAR", W9: "KC", W10: "@MIA", W11: "TB", W12: "@HOU", W13: "@PIT", W14: "CIN", W15: "@NE", W16: "@CLE", W17: "PHI", W18: "NYJ" },
  { Team: "CAR", W1: "@JAX", W2: "@ARI", W3: "ATL", W4: "@NE", W5: "MIA", W6: "DAL", W7: "@NYJ", W8: "BUF", W9: "@GB", W10: "NO", W11: "@ATL", W12: "@SF", W13: "LAR", W14: "BYE", W15: "@NO", W16: "TB", W17: "SEA", W18: "@TB" },
  { Team: "CHI", W1: "MIN", W2: "@DET", W3: "DAL", W4: "@LV", W5: "BYE", W6: "@WAS", W7: "NO", W8: "@BAL", W9: "@CIN", W10: "NYG", W11: "@MIN", W12: "PIT", W13: "@PHI", W14: "@GB", W15: "CLE", W16: "GB", W17: "@SF", W18: "DET" },
  { Team: "CIN", W1: "@CLE", W2: "JAX", W3: "@MIN", W4: "@DEN", W5: "DET", W6: "@GB", W7: "PIT", W8: "NYJ", W9: "CHI", W10: "BYE", W11: "@PIT", W12: "NE", W13: "@BAL", W14: "@BUF", W15: "BAL", W16: "@MIA", W17: "ARI", W18: "CLE" },
  { Team: "CLE", W1: "CIN", W2: "@BAL", W3: "GB", W4: "@DET", W5: "MIN", W6: "@PIT", W7: "MIA", W8: "@NE", W9: "BYE", W10: "@NYJ", W11: "BAL", W12: "@LV", W13: "SF", W14: "TEN", W15: "@CHI", W16: "BUF", W17: "PIT", W18: "@CIN" },
  { Team: "DAL", W1: "@PHI", W2: "NYG", W3: "@CHI", W4: "GB", W5: "@NYJ", W6: "@CAR", W7: "WAS", W8: "@DEN", W9: "ARI", W10: "BYE", W11: "@LV", W12: "PHI", W13: "KC", W14: "@DET", W15: "MIN", W16: "LAC", W17: "@WAS", W18: "@NYG" },
  { Team: "DEN", W1: "TEN", W2: "@IND", W3: "@LAC", W4: "CIN", W5: "@PHI", W6: "@NYJ", W7: "NYG", W8: "DAL", W9: "@HOU", W10: "LV", W11: "KC", W12: "BYE", W13: "@WAS", W14: "@LV", W15: "GB", W16: "JAX", W17: "@KC", W18: "LAC" },
  { Team: "DET", W1: "@GB", W2: "CHI", W3: "@BAL", W4: "CLE", W5: "@CIN", W6: "@KC", W7: "TB", W8: "BYE", W9: "MIN", W10: "@WAS", W11: "@PHI", W12: "NYG", W13: "GB", W14: "DAL", W15: "@LAR", W16: "PIT", W17: "@MIN", W18: "@CHI" },
  { Team: "GB", W1: "DET", W2: "WAS", W3: "@CLE", W4: "@DAL", W5: "BYE", W6: "CIN", W7: "@ARI", W8: "@PIT", W9: "CAR", W10: "PHI", W11: "@NYG", W12: "MIN", W13: "@DET", W14: "CHI", W15: "@DEN", W16: "@CHI", W17: "BAL", W18: "@MIN" },
  { Team: "HOU", W1: "@LAR", W2: "TB", W3: "@JAX", W4: "TEN", W5: "@BAL", W6: "BYE", W7: "@SEA", W8: "SF", W9: "DEN", W10: "JAX", W11: "@TEN", W12: "BUF", W13: "@IND", W14: "@KC", W15: "ARI", W16: "LV", W17: "@LAC", W18: "IND" },
  { Team: "IND", W1: "MIA", W2: "DEN", W3: "@TEN", W4: "@LAR", W5: "LV", W6: "ARI", W7: "@LAC", W8: "TEN", W9: "@PIT", W10: "ATL", W11: "BYE", W12: "@KC", W13: "HOU", W14: "@JAX", W15: "@SEA", W16: "SF", W17: "JAX", W18: "@HOU" },
  { Team: "JAX", W1: "CAR", W2: "@CIN", W3: "HOU", W4: "@SF", W5: "KC", W6: "SEA", W7: "LAR", W8: "BYE", W9: "@LV", W10: "@HOU", W11: "LAC", W12: "@ARI", W13: "@TEN", W14: "IND", W15: "NYJ", W16: "@DEN", W17: "@IND", W18: "TEN" },
  { Team: "KC", W1: "@LAC", W2: "PHI", W3: "@NYG", W4: "BAL", W5: "@JAX", W6: "DET", W7: "LV", W8: "WAS", W9: "@BUF", W10: "BYE", W11: "@DEN", W12: "IND", W13: "@DAL", W14: "HOU", W15: "LAC", W16: "@TEN", W17: "DEN", W18: "@LV" },
  { Team: "LAC", W1: "KC", W2: "@LV", W3: "DEN", W4: "@NYG", W5: "WAS", W6: "@MIA", W7: "IND", W8: "MIN", W9: "@TEN", W10: "PIT", W11: "@JAX", W12: "BYE", W13: "LV", W14: "PHI", W15: "@KC", W16: "@DAL", W17: "HOU", W18: "@DEN" },
  { Team: "LAR", W1: "HOU", W2: "@TEN", W3: "@PHI", W4: "IND", W5: "SF", W6: "@BAL", W7: "@JAX", W8: "BYE", W9: "NO", W10: "@SF", W11: "SEA", W12: "TB", W13: "@CAR", W14: "@ARI", W15: "DET", W16: "@SEA", W17: "@ATL", W18: "ARI" },
  { Team: "LV", W1: "@NE", W2: "LAC", W3: "@WAS", W4: "CHI", W5: "@IND", W6: "TEN", W7: "@KC", W8: "BYE", W9: "JAX", W10: "@DEN", W11: "DAL", W12: "CLE", W13: "@LAC", W14: "DEN", W15: "@PHI", W16: "@HOU", W17: "NYG", W18: "KC" },
  { Team: "MIA", W1: "@IND", W2: "NE", W3: "@BUF", W4: "NYJ", W5: "@CAR", W6: "LAC", W7: "@CLE", W8: "@ATL", W9: "BAL", W10: "BUF", W11: "WAS", W12: "BYE", W13: "NO", W14: "@NYJ", W15: "@PIT", W16: "CIN", W17: "TB", W18: "@NE" },
  { Team: "MIN", W1: "@CHI", W2: "ATL", W3: "CIN", W4: "@PIT", W5: "@CLE", W6: "BYE", W7: "PHI", W8: "@LAC", W9: "@DET", W10: "BAL", W11: "CHI", W12: "@GB", W13: "@SEA", W14: "WAS", W15: "@DAL", W16: "@NYG", W17: "DET", W18: "GB" },
  { Team: "NE", W1: "LV", W2: "@MIA", W3: "PIT", W4: "CAR", W5: "@BUF", W6: "@NO", W7: "@TEN", W8: "CLE", W9: "ATL", W10: "@TB", W11: "NYJ", W12: "@CIN", W13: "NYG", W14: "BYE", W15: "BUF", W16: "@BAL", W17: "@NYJ", W18: "MIA" },
  { Team: "NO", W1: "ARI", W2: "SF", W3: "@SEA", W4: "@BUF", W5: "NYG", W6: "NE", W7: "@CHI", W8: "TB", W9: "@LAR", W10: "@CAR", W11: "BYE", W12: "ATL", W13: "@MIA", W14: "@TB", W15: "CAR", W16: "NYJ", W17: "@TEN", W18: "@ATL" },
  { Team: "NYG", W1: "@WAS", W2: "@DAL", W3: "KC", W4: "LAC", W5: "@NO", W6: "PHI", W7: "@DEN", W8: "@PHI", W9: "SF", W10: "@CHI", W11: "GB", W12: "@DET", W13: "@NE", W14: "BYE", W15: "WAS", W16: "MIN", W17: "@LV", W18: "DAL" },
  { Team: "NYJ", W1: "PIT", W2: "BUF", W3: "@TB", W4: "@MIA", W5: "DAL", W6: "DEN", W7: "CAR", W8: "@CIN", W9: "BYE", W10: "CLE", W11: "@NE", W12: "@BAL", W13: "ATL", W14: "MIA", W15: "@JAX", W16: "@NO", W17: "NE", W18: "@BUF" },
  { Team: "PHI", W1: "DAL", W2: "@KC", W3: "LAR", W4: "@TB", W5: "DEN", W6: "@NYG", W7: "@MIN", W8: "NYG", W9: "BYE", W10: "@GB", W11: "DET", W12: "@DAL", W13: "CHI", W14: "@LAC", W15: "LV", W16: "@WAS", W17: "@BUF", W18: "WAS" },
  { Team: "PIT", W1: "@NYJ", W2: "SEA", W3: "@NE", W4: "MIN", W5: "BYE", W6: "CLE", W7: "@CIN", W8: "GB", W9: "IND", W10: "@LAC", W11: "CIN", W12: "@CHI", W13: "BUF", W14: "@BAL", W15: "MIA", W16: "@DET", W17: "@CLE", W18: "BAL" },
  { Team: "SEA", W1: "SF", W2: "@PIT", W3: "NO", W4: "@ARI", W5: "TB", W6: "@JAX", W7: "HOU", W8: "BYE", W9: "@WAS", W10: "ARI", W11: "@LAR", W12: "@TEN", W13: "MIN", W14: "@ATL", W15: "IND", W16: "LAR", W17: "@CAR", W18: "@SF" },
  { Team: "SF", W1: "@SEA", W2: "@NO", W3: "ARI", W4: "JAX", W5: "@LAR", W6: "@TB", W7: "ATL", W8: "@HOU", W9: "@NYG", W10: "LAR", W11: "@ARI", W12: "CAR", W13: "@CLE", W14: "BYE", W15: "TEN", W16: "@IND", W17: "CHI", W18: "SEA" },
  { Team: "TB", W1: "@ATL", W2: "@HOU", W3: "NYJ", W4: "PHI", W5: "@SEA", W6: "SF", W7: "@DET", W8: "@NO", W9: "BYE", W10: "NE", W11: "@BUF", W12: "@LAR", W13: "ARI", W14: "NO", W15: "ATL", W16: "@CAR", W17: "@MIA", W18: "CAR" },
  { Team: "TEN", W1: "@DEN", W2: "LAR", W3: "IND", W4: "@HOU", W5: "@ARI", W6: "@LV", W7: "NE", W8: "@IND", W9: "LAC", W10: "BYE", W11: "HOU", W12: "SEA", W13: "JAX", W14: "@CLE", W15: "@SF", W16: "KC", W17: "NO", W18: "@JAX" },
  { Team: "WAS", W1: "NYG", W2: "@GB", W3: "LV", W4: "@ATL", W5: "@LAC", W6: "CHI", W7: "@DAL", W8: "@KC", W9: "SEA", W10: "DET", W11: "@MIA", W12: "BYE", W13: "DEN", W14: "@MIN", W15: "@NYG", W16: "PHI", W17: "DAL", W18: "@PHI" }
];

export const teamStats: Record<string, { sos: number; wins: number }> = {
  NYG: { sos: 1, wins: 5.5 }, CHI: { sos: 2, wins: 8.5 }, DET: { sos: 3, wins: 10.5 },
  PHI: { sos: 4, wins: 11.5 }, DAL: { sos: 5, wins: 7.5 }, GB: { sos: 6, wins: 9.5 },
  MIN: { sos: 7, wins: 8.5 }, WAS: { sos: 8, wins: 9.5 }, BAL: { sos: 9, wins: 11.5 },
  PIT: { sos: 10, wins: 8.5 }, KC: { sos: 11, wins: 11.5 }, LAC: { sos: 12, wins: 9.5 },
  CLE: { sos: 13, wins: 5.5 }, CIN: { sos: 14, wins: 9.5 }, DEN: { sos: 15, wins: 9.5 },
  LV: { sos: 16, wins: 6.5 }, LAR: { sos: 17, wins: 9.5 }, HOU: { sos: 18, wins: 9.5 },
  TB: { sos: 19, wins: 9.5 }, ATL: { sos: 20, wins: 7.5 }, MIA: { sos: 21, wins: 8.5 },
  SEA: { sos: 22, wins: 7.5 }, BUF: { sos: 23, wins: 11.5 }, JAX: { sos: 24, wins: 7.5 },
  IND: { sos: 25, wins: 7.5 }, NYJ: { sos: 26, wins: 5.5 }, ARI: { sos: 27, wins: 8.5 },
  CAR: { sos: 28, wins: 6.5 }, TEN: { sos: 29, wins: 5.5 }, NE: { sos: 30, wins: 7.5 },
  NO: { sos: 31, wins: 6.5 }, SF: { sos: 32, wins: 10.5 }
};

export const divisions: Record<string, string[]> = {
  "AFC East": ["BUF", "MIA", "NE", "NYJ"],
  "AFC North": ["BAL", "CIN", "CLE", "PIT"],
  "AFC South": ["HOU", "IND", "JAX", "TEN"],
  "AFC West": ["DEN", "KC", "LAC", "LV"],
  "NFC East": ["DAL", "NYG", "PHI", "WAS"],
  "NFC North": ["CHI", "DET", "GB", "MIN"],
  "NFC South": ["ATL", "CAR", "NO", "TB"],
  "NFC West": ["ARI", "LAR", "SEA", "SF"]
};

export const gameSchedule: Record<number, Record<string, string>> = {
  1: { DAL: "Thu", PHI: "Thu", KC: "Fri", LAC: "Fri", BAL: "Sun", BUF: "Sun", MIN: "Mon", CHI: "Mon" },
  2: { WAS: "Thu", GB: "Thu", ATL: "Sun", MIN: "Sun", LAC: "Mon", LV: "Mon", TB: "Mon", HOU: "Mon" },
  3: { MIA: "Thu", BUF: "Thu", NYG: "Sun", KC: "Sun", DET: "Mon", BAL: "Mon" },
  4: { SEA: "Thu", ARI: "Thu", GB: "Sun", DAL: "Sun", NYJ: "Mon", MIA: "Mon", CIN: "Mon", DEN: "Mon" },
  5: { SF: "Thu", LAR: "Thu", BUF: "Sun", NE: "Sun", KC: "Mon", JAX: "Mon" },
  6: { PHI: "Thu", NYG: "Thu", DET: "Sun", KC: "Sun", BUF: "Mon", ATL: "Mon", CHI: "Mon", WAS: "Mon" },
  7: { CIN: "Thu", PIT: "Thu", ATL: "Sun", SF: "Sun", DET: "Mon", TB: "Mon", HOU: "Mon", SEA: "Mon" },
  8: { MIN: "Thu", LAC: "Thu", GB: "Sun", PIT: "Sun", WAS: "Mon", KC: "Mon" },
  9: { BAL: "Thu", MIA: "Thu", SEA: "Sun", WAS: "Sun", ARI: "Mon", DAL: "Mon" },
  10: { DEN: "Thu", LV: "Thu", PIT: "Sun", LAC: "Sun", PHI: "Mon", GB: "Mon" },
  11: { NYJ: "Thu", NE: "Thu", PHI: "Sun", DET: "Sun", DAL: "Mon", LV: "Mon" },
  12: { BUF: "Thu", HOU: "Thu", TB: "Sun", LAR: "Sun", CAR: "Mon", SF: "Mon" },
  13: { CIN: "Thu", BAL: "Thu", DEN: "Sun", WAS: "Sun", NYG: "Mon", NE: "Mon" },
  14: { DAL: "Thu", DET: "Thu", HOU: "Sun", KC: "Sun", PHI: "Mon", LAC: "Mon" },
  15: { ATL: "Thu", TB: "Thu", MIN: "Sun", DAL: "Sun", MIA: "Mon", PIT: "Mon" },
  16: { LAR: "Thu", SEA: "Thu", CIN: "Sun", MIA: "Sun", SF: "Mon", IND: "Mon" },
  17: { DEN: "Thu", KC: "Thu", CHI: "Sun", SF: "Sun", LAR: "Mon", ATL: "Mon" },
  18: {}
};

export const teamLogos: Record<string, string> = Object.fromEntries(
  ["ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC", "LAC", "LAR", "LV", "MIA", "MIN", "NE", "NO", "NYG", "NYJ", "PHI", "PIT", "SF", "SEA", "TB", "TEN"]
    .map((team) => [team, `https://a.espncdn.com/i/teamlogos/nfl/500/${team.toLowerCase()}.png`])
    .concat([["WAS", "https://a.espncdn.com/i/teamlogos/nfl/500/wsh.png"]])
);

// Historical preseason Vegas win totals (nflverse/nfldata, 2015-2020)
// LA = LAR (Rams first year in LA), LAC includes SD era
export const historicalVegasLines: Record<string, Record<string, number>> = {
  "2015": { ARI:8.5,ATL:8.5,BAL:9.0,BUF:8.5,CAR:8.5,CHI:6.5,CIN:8.5,CLE:6.5,DAL:9.5,DEN:10.0,DET:8.5,GB:11.0,HOU:8.5,IND:10.5,JAX:5.5,KC:8.5,LAC:8.0,LAR:7.5,LV:5.5,MIA:9.0,MIN:8.0,NE:10.5,NO:8.5,NYG:8.0,NYJ:7.5,PHI:10.0,PIT:8.5,SEA:11.0,SF:6.5,TB:6.0,TEN:5.5,WAS:6.0 },
  "2016": { ARI:10.0,ATL:7.0,BAL:8.5,BUF:8.0,CAR:10.5,CHI:7.5,CIN:9.5,CLE:4.5,DAL:8.5,DEN:9.5,DET:7.0,GB:10.5,HOU:8.5,IND:9.0,JAX:7.5,KC:9.5,LAC:7.0,LAR:7.5,LV:8.5,MIA:7.0,MIN:8.5,NE:10.5,NO:7.0,NYG:8.5,NYJ:8.0,PHI:6.5,PIT:10.5,SEA:10.5,SF:5.5,TB:7.0,TEN:6.0,WAS:7.5 },
  "2017": { ARI:8.5,ATL:9.5,BAL:8.5,BUF:6.5,CAR:9.0,CHI:5.5,CIN:8.5,CLE:4.5,DAL:9.5,DEN:8.0,DET:7.5,GB:10.5,HOU:8.5,IND:8.0,JAX:6.5,KC:9.0,LAC:7.5,LAR:6.0,LV:9.5,MIA:7.0,MIN:8.5,NE:12.5,NO:8.0,NYG:9.0,NYJ:3.5,PHI:8.5,PIT:10.5,SEA:10.5,SF:5.0,TB:8.5,TEN:9.0,WAS:7.5 },
  "2018": { ARI:6.0,ATL:9.5,BAL:8.5,BUF:5.5,CAR:8.5,CHI:7.5,CIN:7.0,CLE:6.0,DAL:8.5,DEN:7.0,DET:7.5,GB:10.0,HOU:8.5,IND:7.5,JAX:9.0,KC:8.5,LAC:9.5,LAR:10.0,LV:7.5,MIA:6.5,MIN:10.0,NE:11.0,NO:9.5,NYG:7.0,NYJ:6.0,PHI:10.5,PIT:10.5,SEA:7.5,SF:8.5,TB:6.5,TEN:8.0,WAS:7.0 },
  "2019": { ARI:5.0,ATL:8.5,BAL:8.5,BUF:7.0,CAR:8.0,CHI:9.0,CIN:6.0,CLE:9.0,DAL:9.0,DEN:7.0,DET:6.5,GB:9.0,HOU:8.5,IND:7.5,JAX:8.0,KC:10.5,LAC:10.0,LAR:10.5,LV:6.0,MIA:4.5,MIN:9.0,NE:11.5,NO:10.5,NYG:6.0,NYJ:7.5,PHI:10.0,PIT:9.5,SEA:9.0,SF:8.0,TB:6.5,TEN:8.0,WAS:6.0 },
  "2020": { ARI:7.5,ATL:7.5,BAL:11.5,BUF:9.0,CAR:5.5,CHI:8.5,CIN:5.5,CLE:8.5,DAL:9.5,DEN:7.5,DET:6.5,GB:9.0,HOU:7.5,IND:9.0,JAX:4.5,KC:11.5,LAC:7.5,LAR:8.5,LV:7.5,MIA:6.5,MIN:9.0,NE:9.0,NO:10.5,NYG:6.5,NYJ:7.0,PHI:9.5,PIT:9.5,SEA:9.0,SF:10.5,TB:9.5,TEN:8.5,WAS:5.5 },
};

export const intlGames: Record<number, Array<[string, string, string]>> = {
  1: [["KC", "@LAC", "BR"], ["LAC", "KC", "BR"]],
  4: [["MIN", "@PIT", "IE"], ["PIT", "MIN", "IE"]],
  6: [["NYJ", "@MIN", "GB"], ["MIN", "NYJ", "GB"]],
  7: [["DEN", "@NYJ", "GB"], ["NYJ", "DEN", "GB"]],
  8: [["LAR", "@JAX", "GB"], ["JAX", "LAR", "GB"]],
  10: [["ATL", "@IND", "DE"], ["IND", "ATL", "DE"]],
  11: [["WAS", "@MIA", "ES"], ["MIA", "WAS", "ES"]]
};

export const teamTimeZones: Record<string, "EST" | "CST" | "MST" | "PST"> = {
  ARI: "MST", ATL: "EST", BAL: "EST", BUF: "EST", CAR: "EST", CHI: "CST",
  CIN: "EST", CLE: "EST", DAL: "CST", DEN: "MST", DET: "EST", GB: "CST",
  HOU: "CST", IND: "EST", JAX: "EST", KC: "CST", LAC: "PST", LAR: "PST",
  LV: "PST", MIA: "EST", MIN: "CST", NE: "EST", NO: "CST", NYG: "EST",
  NYJ: "EST", PHI: "EST", PIT: "EST", SF: "PST", SEA: "PST", TB: "EST",
  TEN: "CST", WAS: "EST"
};

export const weekStartDates = [
  null, "2025-09-07", "2025-09-14", "2025-09-21", "2025-09-28", "2025-10-05",
  "2025-10-12", "2025-10-19", "2025-10-26", "2025-11-02", "2025-11-09",
  "2025-11-16", "2025-11-23", "2025-11-30", "2025-12-07", "2025-12-14",
  "2025-12-21", "2025-12-28", "2026-01-04"
];

export function getDivision(team: string) {
  return Object.entries(divisions).find(([, teams]) => teams.includes(team))?.[0] || "Unknown";
}

export function getConference(team: string): Conference {
  return getDivision(team).startsWith("AFC") ? "AFC" : "NFC";
}
