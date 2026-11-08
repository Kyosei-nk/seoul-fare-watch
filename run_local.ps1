# 自宅PCで1回実行する（タスク スケジューラから呼ばれる）
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"
# .env から NTFY_TOPIC を読む
if (Test-Path .env) {
  Get-Content .env | ForEach-Object { if ($_ -match '^\s*([A-Z_]+)\s*=\s*(.+)\s*$') { Set-Item "env:$($matches[1])" $matches[2] } }
}
$log = Join-Path $PSScriptRoot "state\run.log"
"=== $(Get-Date -Format s) ===" | Out-File $log -Append -Encoding utf8
python src\main.py *>> $log
# GitHub に公開している場合だけ push する
if (Test-Path .git) {
  git pull --rebase --autostash -q *>> $log
  git add docs/data state *>> $log
  git commit -q -m "fares (local) $(Get-Date -Format 'MM/dd-HH:mm')" *>> $log
  git push -q *>> $log
}
