# ソウル航空券ウォッチ（Trip.com 価格監視）

12/20 発 → 12/22 帰着の往復（大人1名・エコノミー）について、次の2路線の最安値を2時間おきに取得します。
- 中部国際空港（NGO）⇄ ソウル
- 静岡空港（FSZ）⇄ ソウル

値下がりしたときはスマホに通知が届きます。

## しくみ
```
定期実行（GitHub Actions か 自宅PC）→ src/main.py
  ├ Trip.com の価格カレンダーから最安値を取得（src/fetch_trip.py）
  ├ docs/data/*.json に記録 → スマホ用ページ（docs/index.html）で表示
  └ 通知ルールで判定（src/rules.py）→ ntfy でスマホに通知（src/notify.py）
```
- **価格の出どころ**：Trip.com の日付選択カレンダーが使っている最安値です。実際の検索結果とは数百〜千円ほどずれることがあります。予約前は通知のボタンから Trip.com を開いて確認してください。
- 取得は 7時〜25時の2時間おきで、1回につき1路線1リクエストだけです。ブラウザのふりはしません。

## 通知のルール（config.json の rules で変更できます）
| 通知 | 条件 |
|---|---|
| 🎯 目標価格以下 | `routes[].target_price` を入れたとき、その金額以下になった |
| 🔥 最安値更新 | 3回以上観測したあとで、これまでの最安値を下回った |
| ▼ 値下がり | 前回通知した価格から 1,000円以上 かつ 3%以上 下がった（6時間に1回まで） |
| ▲ 値上がり | 24時間前より 3,000円以上 または 10%以上 上がった |
| ☀ 毎朝のまとめ | 8時以降の最初の実行で、両路線の現在値・最安値・安い日付 |
| ⚠ 取得失敗 | 3回連続で失敗したら1回だけ通知し、直ったら復旧を通知 |

## スマホの準備（ntfy）
1. Google Play で「ntfy」アプリを入れる
2. ＋ボタン → トピック名に `.env` の `NTFY_TOPIC=` の右側を入力 → 購読
   - トピック名を知っている人は誰でも通知を読めるので、他人に教えないでください

## 動かし方
### A. GitHub で動かす（PCの電源が切れていても動く・おすすめ）
1. GitHub で新しいリポジトリを作り、このフォルダを push する
2. Settings → Secrets and variables → Actions → `NTFY_TOPIC` を登録する
3. Settings → Pages → Branch: `main` / Folder: `/docs` → 表示されたURLをスマホで開き、「ホーム画面に追加」する
4. そのURLを config.json の `page_url` に入れる（通知をタップするとページが開くようになる）
5. Actions タブ → watch-fares → Run workflow で手動実行し、成功するか確認する
   - GitHub のサーバー（海外のIP）からだと Trip.com に拒否される可能性があります。その場合は B に切り替えます。

### B. 自宅PCで動かす
```
powershell -ExecutionPolicy Bypass -File setup_task.ps1
```
- 2時間おきに `run_local.ps1` が動きます（PCが起動している間だけ）。ログは `state/run.log` に出ます
- GitHub に push してある場合は、PCで取ったデータも自動で push され、ページに反映されます
- 止めるとき：`Unregister-ScheduledTask -TaskName TripFareWatch`

## そのほか
- テスト：`python tests/test_rules.py`
- 手動で1回実行：`python src/main.py --force`（`--summary` を付けると、まとめを今すぐ送る）
- 旅行が終わったら、Actions を無効にするか、タスクを削除してください
