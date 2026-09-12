function Sparkline() {
  return (
    <svg
      className="pv-sparkline"
      width="340"
      height="150"
      viewBox="0 0 340 150"
      fill="none"
      aria-hidden="true"
    >
      {/* Smooth uptrend — quant/markets */}
      <path
        d="M0,120 C22,114 46,105 68,94 S106,77 132,66 S172,50 202,40 S252,26 302,16 S328,10 340,7"
        stroke="#013369"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      {/* Jagged line — sports data */}
      <path
        d="M0,136 L32,122 L54,130 L86,108 L114,116 L144,90 L170,100 L200,76 L228,86 L260,62 L286,70 L320,48 L340,54"
        stroke="#013369"
        strokeWidth="1"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Smooth probability curve */}
      <path
        d="M0,143 C72,140 122,120 182,110 S272,88 340,76"
        stroke="#013369"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
      {/* Inflection dots */}
      <circle cx="132" cy="66" r="2.5" fill="#013369" />
      <circle cx="302" cy="16" r="2.5" fill="#013369" />
      <circle cx="200" cy="76" r="2" fill="#013369" />
    </svg>
  );
}

const PROJECTS = [
  {
    category: "Sports Analytics",
    items: [
      {
        id: "nfl-signal",
        label: "NFL Signal",
        tagline: "Weekly edge board & picks platform",
        desc: "Data-driven NFL betting analysis for the 2026 season. Every game graded across spread, total, and moneyline — model-backed picks, WARPS fair-value overlays, Pick'em tools, and a survivor pool manager.",
        links: [
          { text: "Open NFL Signal", href: "https://nflsignal.com/matrix.html", primary: true },
          { text: "Weekly Picks", href: "https://nflsignal.com/matrix.html#command" },
          { text: "Pick'em", href: "https://nflsignal.com/matrix.html#pickem" },
          { text: "Edge Board", href: "https://nflsignal.com/matrix.html#edges" },
        ],
        accent: "navy",
      },
      {
        id: "warps",
        label: "WARPS-NFL™",
        tagline: "Preseason win-total probability model",
        desc: "A 75% Pythagorean + 25% point-differential blend for predicting NFL regular-season win totals. Built on 26 seasons of data (2000–2025). Beats the statistical baseline in 25 of 26 seasons — MAE 2.374, p < 0.0001.",
        links: [
          { text: "Open WARPS", href: "https://nflsignal.com/warps.html", primary: true },
          { text: "Read the paper", href: "warps.html" },
        ],
        accent: "red",
      },
    ],
  },
  {
    category: "Financial Research",
    items: [
      {
        id: "valcap",
        label: "Val Cap Quant",
        tagline: "Quantitative equity screening & portfolio research",
        desc: "Factor-based equity research tools covering valuation, momentum, and quality screens. Long-hold strategy dashboard tracks portfolio construction and rebalancing signals across market cycles.",
        links: [
          { text: "Research Dashboard", href: "ytts/research_dashboard_app.html", primary: true },
          { text: "Long-Hold Dashboard", href: "ytts/longhold_dashboard.html" },
        ],
        accent: "green",
      },
    ],
  },
];

export default function PersonalApp() {
  return (
    <div className="pv-root">
      <header className="pv-header">
        <div className="pv-identity">
          <h1 className="pv-name">Liju Varughese</h1>
          <p className="pv-title">Quantitative research · Sports analytics · Financial markets</p>
        </div>
        <Sparkline />
      </header>

      <main className="pv-main">
        {PROJECTS.map((group) => (
          <section key={group.category} className="pv-section">
            <h2 className="pv-section-label">{group.category}</h2>
            <div className="pv-cards">
              {group.items.map((item) => (
                <article key={item.id} className={`pv-card pv-card-${item.accent}`}>
                  <div className="pv-card-head">
                    <span className="pv-card-label">{item.label}</span>
                    <span className="pv-card-tagline">{item.tagline}</span>
                  </div>
                  <p className="pv-card-desc">{item.desc}</p>
                  <div className="pv-card-links">
                    {item.links.map((link) => (
                      <a
                        key={link.href}
                        href={link.href}
                        className={link.primary ? "pv-link-primary" : "pv-link-ghost"}
                      >
                        {link.text}
                      </a>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          </section>
        ))}
      </main>

      <footer className="pv-footer">
        © {new Date().getFullYear()} Liju Varughese
      </footer>
    </div>
  );
}
