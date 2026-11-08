"""通知ルールの判定（純粋関数。テストしやすいようにネットワーク処理は持たない）"""
from __future__ import annotations

from datetime import datetime, timedelta

PRIO_HIGH, PRIO_DEFAULT, PRIO_LOW, PRIO_MIN = "high", "default", "low", "min"


def yen(n: int | float) -> str:
    return f"¥{int(round(n)):,}"


def signed_yen(n: int | float) -> str:
    return ("+" if n > 0 else "−" if n < 0 else "±") + f"{abs(int(round(n))):,}"


def _parse(t: str) -> datetime:
    return datetime.fromisoformat(t)


def _in_cooldown(state: dict, kind: str, now: datetime, hours: float) -> bool:
    last = state.get("last_sent", {}).get(kind)
    return bool(last) and now - _parse(last) < timedelta(hours=hours)


def _price_about(history: list[dict], when: datetime) -> dict | None:
    """when 以前で一番新しい観測（例: 24時間前の価格）"""
    older = [h for h in history if _parse(h["t"]) <= when]
    return older[-1] if older else None


def describe(obs: dict) -> str:
    parts = [obs.get("airline") or ""]
    if "stops" in obs:
        parts.append("直行" if obs["stops"] == 0 else f"乗継{obs['stops']}回")
    nb = obs.get("nearby") or {}
    cheaper = {d: p for d, p in nb.items() if p < obs["price"]}
    if cheaper:
        d, p = min(cheaper.items(), key=lambda x: x[1])
        parts.append(f"{d.replace('-', '/')}発なら{yen(p)}")
    if obs.get("out_dep"):
        parts.append(f"往 {obs['out_dep']}発")
    if obs.get("ret_dep"):
        parts.append(f"復 {obs['ret_dep']}発")
    return " / ".join(p for p in parts if p)


def evaluate(route: dict, history: list[dict], state: dict, obs: dict | None,
             error: str | None, now: datetime, rules: dict) -> tuple[list[dict], dict]:
    """1路線ぶんの判定。
    history: これまでの成功観測（obs はまだ含まない）
    返り値: (送る通知のリスト, 更新後の state)
    """
    state = {**state, "last_sent": dict(state.get("last_sent", {}))}
    notes: list[dict] = []
    name = route["name"]

    def send(kind: str, title: str, body: str, prio: str, tags: str):
        notes.append({"kind": kind, "route": route["id"], "title": title,
                      "body": body, "priority": prio, "tags": tags})
        state["last_sent"][kind] = now.isoformat()

    # ---- 失敗 ----
    if obs is None:
        state["fail_streak"] = state.get("fail_streak", 0) + 1
        if state["fail_streak"] >= rules["fail_streak_alert"] and not state.get("fail_alerted"):
            send("fail", f"⚠ 取得失敗が続いています（{name}）",
                 f"{state['fail_streak']}回連続で失敗。最後のエラー: {error}", PRIO_HIGH, "warning")
            state["fail_alerted"] = True
        return notes, state

    # ---- 復旧 ----
    if state.get("fail_alerted"):
        send("recover", f"✅ 取得が復旧しました（{name}）", f"現在 {yen(obs['price'])}", PRIO_DEFAULT, "white_check_mark")
    state["fail_streak"] = 0
    state["fail_alerted"] = False

    price = obs["price"]
    detail = describe(obs)
    prior = [h["price"] for h in history]
    fired = False

    # ---- 目標価格割れ ----
    target = route.get("target_price")
    if target:
        hit = state.get("target_hit_price")
        if price <= target and (hit is None or price < hit):
            send("target", f"🎯 目標価格以下！ {name} {yen(price)}",
                 f"目標 {yen(target)} 以下になりました。{detail}", PRIO_HIGH, "dart")
            state["target_hit_price"] = price
            fired = True
        elif price > target:
            state["target_hit_price"] = None

    # ---- 最安値更新 ----
    if len(prior) >= rules["min_obs_for_low"] and price < min(prior) and not fired:
        send("low", f"🔥 最安値更新 {name} {yen(price)}",
             f"これまでの最安 {yen(min(prior))} → {yen(price)}（{signed_yen(price - min(prior))}）\n{detail}",
             PRIO_HIGH, "fire")
        fired = True

    # ---- 値下がり（前回通知した価格が基準） ----
    base = state.get("base_price")
    if base is None:
        state["base_price"] = price
        base = price
    diff = price - base
    if not fired and diff < 0 and -diff >= rules["drop_yen"] and -diff / base * 100 >= rules["drop_pct"] \
            and not _in_cooldown(state, "drop", now, rules["cooldown_hours"]):
        send("drop", f"▼ 値下がり {name} {yen(price)}",
             f"前回通知 {yen(base)} から {signed_yen(diff)}\n{detail}", PRIO_DEFAULT, "chart_with_downwards_trend")
        fired = True

    # ---- 急騰（24時間前比） ----
    day_ago = _price_about(history, now - timedelta(hours=24))
    if day_ago and not fired:
        d = price - day_ago["price"]
        if d > 0 and (d >= rules["rise_yen"] or d / day_ago["price"] * 100 >= rules["rise_pct"]) \
                and not _in_cooldown(state, "rise", now, rules["cooldown_hours"]):
            send("rise", f"▲ 値上がり {name} {yen(price)}",
                 f"24時間前 {yen(day_ago['price'])} から {signed_yen(d)}。買うなら早めに検討を。", PRIO_LOW, "chart_with_upwards_trend")
            fired = True

    if fired:
        state["base_price"] = price
    return notes, state


def daily_summary(routes: list[dict], histories: dict, now: datetime, depart: str) -> dict:
    days = (datetime.fromisoformat(depart).date() - now.date()).days
    lines = []
    for r in routes:
        h = histories.get(r["id"], [])
        if not h:
            lines.append(f"{r['name']}: データなし")
            continue
        cur = h[-1]["price"]
        low = min(x["price"] for x in h)
        prev = _price_about(h, now - timedelta(hours=24))
        chg = f"（前日比 {signed_yen(cur - prev['price'])}）" if prev else ""
        lines.append(f"{r['name']}: {yen(cur)}{chg} 最安 {yen(low)}")
        hint = describe(h[-1])
        if hint:
            lines.append(f"  └ {hint}")
    return {"kind": "summary", "route": "*", "title": f"☀ 今日の航空券（出発まで{days}日）",
            "body": "\n".join(lines), "priority": PRIO_LOW, "tags": "airplane"}
