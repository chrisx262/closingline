"""
Weekly digest generator — the email IS the product's monetization surface.

    python digest.py            # writes weekly_digest.html + subscribers.csv

- weekly_digest.html: ready-to-send email body — leaderboard movers, the
  week's best CLV picks, affiliate CTA, responsible-gambling footer.
- subscribers.csv: every agent email, importable into any sender
  (Resend, Mailchimp, Buttondown...). Wire real sending in HANDOFF task 9.

Rules baked in: affiliate relationship disclosed in the email itself;
picks shown are already-graded (the free delayed tier — real-time feeds
stay on-platform); responsible gambling line always present.
"""

import csv
import sys

sys.path.insert(0, ".")
from app import SessionLocal, Agent, Pick, Game, load_partners, _agg  # noqa

MAX_BOARD = 5
MAX_PICKS = 5


def run():
    s = SessionLocal()

    # subscribers export
    emails = [(a.name, a.email) for a in s.query(Agent)
              if a.email]
    with open("subscribers.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name", "email"])
        w.writerows(emails)

    # leaderboard (live first, fall back to backtest pre-season)
    def board(mode):
        out = []
        for a in s.query(Agent).all():
            rows = [p for p in s.query(Pick).filter(
                Pick.agent_id == a.id, Pick.mode == mode,
                Pick.result != "pending")]
            if len(rows) >= 5:
                out.append((a.name, _agg(rows)))
        out.sort(key=lambda x: ((x[1]["avg_clv_points"] or -99),
                                x[1]["roi_pct"]), reverse=True)
        return out[:MAX_BOARD]

    top = board("live") or board("backtest")

    # best graded CLV picks of the latest completed week
    last_wk = (s.query(Game.week).filter(Game.final == True)
                .order_by(Game.week.desc()).first())
    best = []
    if last_wk:
        rows = (s.query(Pick, Game, Agent)
                 .join(Game, Pick.game_id == Game.id)
                 .join(Agent, Pick.agent_id == Agent.id)
                 .filter(Game.week == last_wk[0], Pick.result != "pending")
                 .all())
        rows.sort(key=lambda r: (r[0].clv_points or 0), reverse=True)
        best = rows[:MAX_PICKS]

    partners = load_partners()
    cta = "".join(
        f'<a href="{{BASE_URL}}/go/{pid}" style="display:inline-block;'
        f'padding:10px 16px;background:#185fa5;color:#fff;text-decoration:none;'
        f'font-weight:700;margin-right:8px">{p["label"]}</a>'
        for pid, p in partners.items() if not pid.startswith("_"))

    rows_html = "".join(
        f"<tr><td style='padding:6px 10px'><b>{name}</b></td>"
        f"<td style='padding:6px 10px'>{a['wins']}–{a['losses']}</td>"
        f"<td style='padding:6px 10px'>{a['roi_pct']}%</td>"
        f"<td style='padding:6px 10px'>{a['avg_clv_points']}</td></tr>"
        for name, a in top)

    picks_html = "".join(
        f"<tr><td style='padding:6px 10px'>{ag.name}</td>"
        f"<td style='padding:6px 10px'>{g.away} @ {g.home}</td>"
        f"<td style='padding:6px 10px'>{p.market} {p.side} {p.snap_line or ''}"
        f"</td><td style='padding:6px 10px'>{p.result}</td>"
        f"<td style='padding:6px 10px'>{p.clv_points}</td></tr>"
        for p, g, ag in best)

    html = f"""<div style="max-width:600px;margin:auto;font-family:Georgia,serif;
color:#101418">
<h1 style="font-size:24px">Closing<span style="color:#185fa5">Line</span>
 — the week in picks</h1>
<h2 style="font-size:17px">Leaderboard</h2>
<table style="border-collapse:collapse;font-size:14px" border="0">
<tr><th align="left" style="padding:6px 10px">Agent</th>
<th align="left" style="padding:6px 10px">Record</th>
<th align="left" style="padding:6px 10px">ROI</th>
<th align="left" style="padding:6px 10px">CLV</th></tr>{rows_html}</table>
<h2 style="font-size:17px">Picks that beat the closing line</h2>
<table style="border-collapse:collapse;font-size:14px">{picks_html}</table>
<p style="margin:22px 0 8px">{cta}</p>
<p style="font-size:12px;color:#5b6570">Disclosure: ClosingLine may earn a
commission when you sign up with a sportsbook through our links. This never
affects leaderboard rankings, which are computed purely from graded picks.
Past performance does not predict future results.</p>
<p style="font-size:12px;color:#5b6570">If you or someone you know has a
gambling problem, call 1-800-GAMBLER. Must be 21+ and physically present in
a state with legal sports betting to place wagers.</p>
<p style="font-size:12px;color:#5b6570">You're receiving this because you
signed up at ClosingLine. {{UNSUBSCRIBE_LINK}}</p></div>"""

    with open("weekly_digest.html", "w") as f:
        f.write(html)
    s.close()
    print(f"weekly_digest.html written | {len(emails)} subscribers exported "
          f"| {len(top)} agents on board | {len(best)} featured picks")


if __name__ == "__main__":
    run()
