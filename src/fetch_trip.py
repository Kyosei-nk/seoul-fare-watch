"""Trip.com の「価格カレンダー」から往復最安値を取る（ブラウザ不要・1路線1リクエスト）

注意:
- 公開APIではなく、Trip.com のサイトが日付選択カレンダー用に使っている取得口です。
  仕様は予告なく変わる可能性があります。
- カレンダーの値はキャッシュされた最安値なので、実際の検索結果と数百〜千円ほどずれることがあります。
  正確な価格・便は通知やページの「Trip.comで開く」で確認してください。
- 身元を偽らない（ブラウザのふりをしない）User-Agent で、低頻度にアクセスします。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import requests

API = "https://jp.trip.com/restapi/soa2/14427/GetLowPriceInCalender"
UA = "trip-watch/1.0 (personal low-frequency fare tracker)"
JST = timezone(timedelta(hours=9))


def search_url(route: dict, cfg: dict) -> str:
    return ("https://jp.trip.com/flights/showfarefirst?"
            f"dcity={route['from'].lower()}&acity={route['to'].lower()}"
            f"&ddate={cfg['depart_date']}&rdate={cfg['return_date']}"
            f"&triptype=rt&class={cfg.get('cabin', 'y')}&quantity={cfg.get('adults', 1)}"
            "&locale=ja-JP&curr=JPY")


def _jst_date(unix_sec: int) -> str:
    return datetime.fromtimestamp(unix_sec, JST).date().isoformat()


def fetch(route: dict, cfg: dict) -> dict:
    """返り値: {"price", "source", "nearby": {"12-19": 30000, ...}}。取れなければ例外"""
    dd, rd = cfg["depart_date"], cfg["return_date"]
    nights = (date.fromisoformat(rd) - date.fromisoformat(dd)).days
    body = {
        "dCity": route["from"], "aCity": route["to"], "dDate": dd, "aDate": rd,
        "flightWayType": "RT", "departureAirport": "", "arrivalAirport": "",
        "cabinClass": "Economy",
        "transferType": "DIRECT" if cfg.get("direct_only") else "ANY",
        "searchInfo": {"travelerNum": {"adult": cfg.get("adults", 1), "child": 0, "infant": 0}},
        "abtList": [], "offSet": 30, "startInterval": nights, "endInterval": nights,
        "Head": {"Currency": "JPY", "Locale": "ja-JP", "Group": "Trip", "Source": "ONLINE", "Version": "3"},
    }
    r = requests.post(API, json=body, timeout=30, headers={
        "User-Agent": UA, "Content-Type": "application/json",
        "Origin": "https://jp.trip.com", "Referer": "https://jp.trip.com/flights/",
        "currency": "JPY", "locale": "ja-JP",
    })
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} {r.text[:80]!r}")
    j = r.json()
    ack = (j.get("ResponseStatus") or {}).get("Ack")
    if ack != "Success":
        raise RuntimeError(f"Ack={ack}")
    if j.get("currency") not in (None, "JPY"):
        raise RuntimeError(f"通貨が {j.get('currency')}")

    by_date = {}
    for e in j.get("lowPriceInCalenderDtoInfoList") or []:
        p = e.get("currencyPrice")
        if p:
            by_date[(_jst_date(e["dDate"]), _jst_date(e["aDate"]))] = round(p)
    price = by_date.get((dd, rd))
    if not price:
        raise LookupError("指定日の価格が見つかりません（便なし or 未掲載）")

    # 前後2日ずらした場合の価格（同じ泊数）も参考に保存
    d0 = date.fromisoformat(dd)
    nearby = {}
    for k in range(-2, 3):
        a = (d0 + timedelta(days=k)).isoformat()
        b = (d0 + timedelta(days=k + nights)).isoformat()
        if (a, b) in by_date:
            nearby[a[5:]] = by_date[(a, b)]
    return {"price": price, "source": "calendar", "nearby": nearby}


if __name__ == "__main__":
    import json
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    from storage import load_config
    cfg = load_config()
    for rt in cfg["routes"]:
        try:
            print(rt["id"], json.dumps(fetch(rt, cfg), ensure_ascii=False))
        except Exception as e:
            print(rt["id"], "ERROR", e)
