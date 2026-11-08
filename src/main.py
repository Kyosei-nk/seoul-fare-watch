"""全体制御：取得 → 保存 → 通知判定 → 通知 → 状態更新
使い方:  python src/main.py            （通常実行）
         python src/main.py --force    （深夜帯でも実行）
         python src/main.py --summary  （毎朝のまとめを今すぐ送る）
"""
from __future__ import annotations

import random
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, __import__("os").path.dirname(__file__))

import fetch_trip  # noqa: E402
import notify  # noqa: E402
import rules  # noqa: E402
from storage import DATA, STATE, load, load_config, save  # noqa: E402

JST = timezone(timedelta(hours=9))


def main(argv: list[str]) -> int:
    cfg = load_config()
    now = datetime.now(JST).replace(microsecond=0)
    q0, q1 = cfg.get("quiet_hours_jst", [1, 7])
    if q0 <= now.hour < q1 and "--force" not in argv:
        print(f"深夜帯（{q0}〜{q1}時）なのでスキップ")
        return 0

    hist = load(DATA / "history.json", {})
    status = load(DATA / "status.json", {})
    nstate = load(STATE / "notify_state.json", {})
    old_routes = {r["id"]: r for r in status.get("routes", [])}
    page_url = cfg.get("page_url", "")

    out_routes, to_send = [], []
    results = {}
    for i, route in enumerate(cfg["routes"]):
        if i:
            time.sleep(random.uniform(5, 15))  # Trip.com への負荷を下げる
        url = fetch_trip.search_url(route, cfg)
        obs, err = None, None
        try:
            obs = fetch_trip.fetch(route, cfg)
            r = cfg["rules"]
            if not (r["sane_min"] <= obs["price"] <= r["sane_max"]):
                raise ValueError(f"異常な価格 {obs['price']}")
            obs["t"] = now.isoformat()
            print(f"[{route['id']}] {rules.yen(obs['price'])} {rules.describe(obs)}")
        except Exception as e:
            err = f"{type(e).__name__}: {e}"[:300]
            obs = None
            print(f"[{route['id']}] 失敗 {err}")
        results[route["id"]] = (obs, err, url)

        h = hist.get(route["id"], [])
        notes, nstate[route["id"]] = rules.evaluate(route, h, nstate.get(route["id"], {}), obs, err, now, cfg["rules"])
        to_send += [(n, url) for n in notes]
        if obs:
            h.append(obs)
            hist[route["id"]] = h

        prev = old_routes.get(route["id"], {})
        out_routes.append({
            "id": route["id"], "name": route["name"], "from": route["from"], "to": route["to"],
            "target_price": route.get("target_price"), "search_url": url,
            "last_ok": now.isoformat() if obs else prev.get("last_ok"),
            "last_error": err if err else prev.get("last_error") if not obs else None,
            "last_error_at": now.isoformat() if err else prev.get("last_error_at"),
        })

    # 毎朝のまとめ（その日の最初の実行で、指定時刻を過ぎていれば1回）
    today = now.date().isoformat()
    g = nstate.setdefault("_global", {})
    if ("--summary" in argv) or (now.hour >= cfg.get("daily_summary_hour_jst", 8) and g.get("summary_date") != today):
        to_send.append((rules.daily_summary(cfg["routes"], hist, now, cfg["depart_date"]), page_url))
        g["summary_date"] = today

    save(DATA / "history.json", hist)
    save(DATA / "status.json", {"updated": now.isoformat(), "depart_date": cfg["depart_date"],
                                "return_date": cfg["return_date"], "routes": out_routes})
    save(STATE / "notify_state.json", nstate)

    for note, url in to_send:
        notify.send(note, page_url=page_url, search_url=url if note["route"] != "*" else "")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
