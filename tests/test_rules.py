import sys, os
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import rules

JST = timezone(timedelta(hours=9))
R = {"drop_yen": 1000, "drop_pct": 3, "rise_yen": 3000, "rise_pct": 10, "cooldown_hours": 6,
     "fail_streak_alert": 3, "min_obs_for_low": 3, "sane_min": 5000, "sane_max": 300000}
ROUTE = {"id": "NGO", "name": "NGO", "target_price": None}
T0 = datetime(2026, 11, 8, 8, tzinfo=JST)


def run(prices, route=ROUTE):
    hist, state, kinds = [], {}, []
    for i, p in enumerate(prices):
        now = T0 + timedelta(hours=2 * i)
        obs = None if p is None else {"price": p, "t": now.isoformat()}
        notes, state = rules.evaluate(route, hist, state, obs, "err" if p is None else None, now, R)
        kinds.append([n["kind"] for n in notes])
        if obs: hist.append(obs)
    return kinds


def test_first_obs_silent():
    assert run([40000]) == [[]]

def test_small_wobble_silent():
    assert run([40000, 39800, 40100, 39900]) == [[], [], [], []]

def test_drop_then_cooldown():
    k = run([40000, 40000, 40000, 38000, 36500])
    assert k[3] == ["low"]          # 最安値更新（3件以上観測後）
    assert k[4] == ["low"]          # さらに更新（最安更新はクールダウン対象外）

def test_drop_before_enough_obs():
    assert run([40000, 38000]) == [[], ["drop"]]

def test_fail_streak_once_then_recover():
    k = run([40000, None, None, None, None, 40000])
    assert k[3] == ["fail"] and k[4] == [] and k[5] == ["recover"]

def test_target():
    r = {**ROUTE, "target_price": 35000}
    k = run([40000, 34000, 34500, 33000], r)
    assert k[1] == ["target"] and k[2] == [] and k[3] == ["target"]

def test_rise_24h():
    k = run([40000] * 12 + [45000])
    assert k[-1] == ["rise"]

if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"): f(); print("ok", n)
