// On-time trigger for Workflow 3 (market update). GitHub's own cron starts these
// runs hours late on game days, after kickoff. This Worker fires every 15 minutes,
// matches the current Eastern time against SLOTS, and dispatches the workflow
// with the stage set explicitly. Matching in ET (not UTC cron) keeps slots right
// across the daylight-saving change mid-season.

export const SLOTS = [
  { day: "Tue", time: "16:00", stage: "update" },   // early seed: next week's lines are up
  { day: "Wed", time: "09:00", stage: "opening" },
  { day: "Thu", time: "14:00", stage: "pre_tnf" },
  { day: "Sat", time: "21:00", stage: "update" },
  { day: "Sun", time: "08:30", stage: "lock" },     // before 9:30 international games
  { day: "Sun", time: "12:30", stage: "final" },    // before 1:00 kickoffs; the full run takes ~5 min
  { day: "Mon", time: "18:00", stage: "pre_mnf" },
];

export function easternSlot(date) {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-US", {
      timeZone: "America/New_York",
      weekday: "short",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    })
      .formatToParts(date)
      .map((p) => [p.type, p.value]),
  );
  const minute = String(Math.floor(Number(parts.minute) / 15) * 15).padStart(2, "0");
  return { day: parts.weekday, time: `${parts.hour}:${minute}` };
}

async function dispatch(env, stage) {
  const url = `https://api.github.com/repos/${env.GITHUB_REPO}/actions/workflows/${env.WORKFLOW_FILE}/dispatches`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "nflsignal-scheduler",
    },
    body: JSON.stringify({ ref: "main", inputs: { week: "", season: "auto", analysis_type: stage } }),
  });
  if (!res.ok) {
    throw new Error(`dispatch ${stage} failed: ${res.status} ${await res.text()}`);
  }
}

export default {
  async scheduled(event, env) {
    // scheduledTime is the intended fire time, so a few seconds of Cloudflare lag can't skip a slot.
    const now = easternSlot(new Date(event.scheduledTime));
    const slot = SLOTS.find((s) => s.day === now.day && s.time === now.time);
    if (!slot) return;
    await dispatch(env, slot.stage);
    console.log(`Dispatched ${env.WORKFLOW_FILE} stage=${slot.stage} for ${now.day} ${now.time} ET`);
  },
};
