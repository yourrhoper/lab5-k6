"""Обработка CSV-выгрузки k6: агрегирование по 10-секундным окнам, графики и сводные таблицы.
Запуск: python3 analysis/analyze.py results
"""
import gzip, csv, json, sys, os
from collections import defaultdict
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RES = sys.argv[1] if len(sys.argv) > 1 else "results"
BUCKET = 10  # секунд

INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE, RED = "#2a78d6", "#eb6834", "#e34948"
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": INK2, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
})

TITLES = {"load": "Load-тест (50 VU, 5 мин)", "stress": "Stress-тест (×1 → ×5), исходная версия", "spike": "Spike-тест (10 → 250 VU)", "stress-async": "Stress-тест (×1 → ×5), версия с асинхронным хэшированием"}


def load(profile):
    path = os.path.join(RES, f"{profile}.csv.gz")
    vus, reqs = defaultdict(list), []
    with gzip.open(path, "rt", newline="") as f:
        for row in csv.DictReader(f):
            m, t, v = row["metric_name"], int(row["timestamp"]), float(row["metric_value"])
            if m == "vus":
                vus[t].append(v)
            elif m == "http_req_duration":
                reqs.append((t, v, row["scenario"], row["name"], row["status"]))
    t0 = min(min(vus), min(r[0] for r in reqs))
    return t0, vus, reqs


def series(profile):
    t0, vus, reqs = load(profile)
    end = max(r[0] for r in reqs) - t0
    nb = end // BUCKET + 1
    b = lambda t: (t - t0) // BUCKET
    vu = np.zeros(nb); rps = np.zeros(nb); err = np.zeros(nb)
    dur = {"browse": defaultdict(list), "submit": defaultdict(list)}
    for t, v in vus.items():
        i = b(t)
        if i < nb: vu[i] = max(vu[i], max(v))
    for t, d, sc, name, st in reqs:
        i = b(t); rps[i] += 1
        if not st.startswith("2"): err[i] += 1
        if sc in dur: dur[sc][i].append(d)
    x = (np.arange(nb) * BUCKET + BUCKET / 2) / 60.0
    p95 = {sc: np.array([np.percentile(dur[sc][i], 95) if dur[sc][i] else np.nan for i in range(nb)]) for sc in dur}
    err_pct = np.where(rps > 0, err / np.maximum(rps, 1) * 100, np.nan)
    return dict(x=x, vu=vu, rps=rps / BUCKET, p95=p95, err=err_pct, reqs=reqs, t0=t0)


def plot(profile, s):
    fig, ax = plt.subplots(4, 1, figsize=(9, 9.2), sharex=True, gridspec_kw=dict(hspace=0.35))
    x = s["x"]
    ax[0].plot(x, s["vu"], color=INK2, lw=2); ax[0].set_ylabel("VU"); ax[0].set_title("Виртуальные пользователи", loc="left", color=INK, fontsize=10)
    ax[1].plot(x, s["rps"], color=BLUE, lw=2); ax[1].set_ylabel("запр/с"); ax[1].set_title("Пропускная способность (RPS)", loc="left", color=INK, fontsize=10)
    for sc, c, lbl in (("browse", BLUE, "Сценарий 1 «browse»"), ("submit", ORANGE, "Сценарий 2 «submit»")):
        y = s["p95"][sc] / 1000
        ax[2].plot(x, y, color=c, lw=2, label=lbl)
    ax[2].axhline(2.0, color=INK2, lw=1, ls="--"); ax[2].text(x[-1], 2.0, "SLA p95 = 2 с ", va="bottom", ha="right", color=INK2, fontsize=8)
    ax[2].axhline(0.5, color=INK2, lw=1, ls=":"); ax[2].text(x[-1], 0.5, "SLA browse = 0,5 с ", va="bottom", ha="right", color=INK2, fontsize=8)
    ax[2].set_ylim(0, 2.6)
    ax[2].set_ylabel("p95, с"); ax[2].set_title("Время ответа p95 по сценариям (окно 10 с)", loc="left", color=INK, fontsize=10)
    ax[2].legend(frameon=False, loc="upper left", fontsize=8, ncol=2)
    ax[3].plot(x, s["err"], color=RED, lw=2); ax[3].axhline(1.0, color=INK2, lw=1, ls="--")
    ax[3].text(x[-1], 1.0, "SLA 1 % ", va="bottom", ha="right", color=INK2, fontsize=8)
    ax[3].set_ylabel("ошибки, %"); ax[3].set_title("Доля ошибок (не-2xx и таймауты)", loc="left", color=INK, fontsize=10)
    ax[3].set_xlabel("время от начала теста, мин")
    for a in ax[:2]: a.set_ylim(bottom=0)
    ax[3].set_ylim(-0.05, max(2.0, np.nanmax(s["err"]) * 1.2))
    fig.suptitle(TITLES[profile], x=0.07, y=0.935, ha="left", fontsize=12, color=INK, fontweight="bold")
    fig.savefig(os.path.join(RES, f"{profile}-chart.png"), dpi=170, bbox_inches="tight")
    plt.close(fig)


def per_endpoint(s):
    by = defaultdict(list); errs = defaultdict(int)
    for t, d, sc, name, st in s["reqs"]:
        if sc not in ("browse", "submit"): continue
        by[name].append(d)
        if not st.startswith("2"): errs[name] += 1
    dur_s = (max(r[0] for r in s["reqs"]) - s["t0"]) or 1
    out = []
    for name, v in by.items():
        a = np.array(v)
        out.append(dict(name=name, count=len(a), rps=len(a) / dur_s, avg=a.mean(), p50=np.percentile(a, 50),
                        p95=np.percentile(a, 95), p99=np.percentile(a, 99), max=a.max(), err=errs[name] / len(a) * 100))
    return out


def stage_table(s, stages):
    """Метрики по ступеням stress-теста (берём только фазы удержания)."""
    rows = []
    for label, vu, a, b in stages:
        sel = [r for r in s["reqs"] if a * 60 <= r[0] - s["t0"] < b * 60]
        if not sel: continue
        d = np.array([r[1] for r in sel]); br = np.array([r[1] for r in sel if r[2] == "browse"]); sb = np.array([r[1] for r in sel if r[2] == "submit"])
        lg = np.array([r[1] for r in sel if r[3] == "POST /api/auth/login"])
        e = sum(1 for r in sel if not r[4].startswith("2"))
        rows.append(dict(stage=label, vu=vu, rps=len(sel) / ((b - a) * 60), p95=np.percentile(d, 95), p95_browse=np.percentile(br, 95),
                         p95_submit=np.percentile(sb, 95), p95_login=np.percentile(lg, 95) if len(lg) else float('nan'),
                         err=e / len(sel) * 100))
    return rows


if __name__ == "__main__":
    report = {}
    for p in ("load", "stress", "spike", "stress-async"):
        if not os.path.exists(os.path.join(RES, f"{p}.csv.gz")): continue
        s = series(p); plot(p, s)
        report[p] = {"endpoints": per_endpoint(s)}
        if p.startswith("stress"):
            report[p]["stages"] = stage_table(s, [("×1", 50, 1.2, 2.6), ("×2", 100, 3.2, 4.6), ("×3", 150, 5.2, 6.6), ("×4", 200, 7.2, 8.6), ("×5", 250, 9.2, 10.6)])
        if p == "spike":
            report[p]["stages"] = stage_table(s, [("фон до скачка", 10, 0.6, 1.5), ("пик (250 VU)", 250, 1.8, 2.75), ("восстановление: первые 30 с", 10, 3.1, 3.6), ("восстановление: следующие 55 с", 10, 3.6, 4.5)])
        if p == "load":
            report[p]["stages"] = stage_table(s, [("удержание 50 VU", 50, 1.2, 6.1)])
    json.dump(report, open(os.path.join(RES, "analysis.json"), "w"), ensure_ascii=False, indent=1, default=float)
    print(json.dumps(report, ensure_ascii=False, indent=1, default=float))
