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
          { text: "Open NFL Signal", href: "https://nflsignal.pages.dev/matrix.html", primary: true },
          { text: "Weekly Picks", href: "https://nflsignal.pages.dev/matrix.html#command" },
          { text: "Pick'em", href: "https://nflsignal.pages.dev/matrix.html#pickem" },
          { text: "Edge Board", href: "https://nflsignal.pages.dev/matrix.html#edges" },
        ],
        accent: "navy",
      },
      {
        id: "warps",
        label: "WARPS-NFL™",
        tagline: "Preseason win-total probability model",
        desc: "A 75% Pythagorean + 25% point-differential blend for predicting NFL regular-season win totals. Built on 26 seasons of data (2000–2025). Beats the statistical baseline in 25 of 26 seasons — MAE 2.374, p < 0.0001.",
        links: [
          { text: "Open WARPS", href: "https://nflsignal.pages.dev/warps.html", primary: true },
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
