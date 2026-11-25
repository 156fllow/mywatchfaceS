<#
.SYNOPSIS
  Meridian を Pixel Watch に上書きインストールして、スクリーンショットを撮る。

.DESCRIPTION
  先に「adb connect <IP>:<ポート>」でウォッチと接続しておくこと。
  このスクリプトは次を自動で行う:
    1. 接続中のウォッチを探す
    2. ダウンロードフォルダから最新の APK を探す
       (新しい meridian-watchface*.zip があれば自動で展開する)
    3. 上書きインストール (adb install -r)
    4. Meridian をウォッチフェイスに設定 (実行中は画面を点けたままにする)
    5. スクリーンショットを撮ってダウンロードフォルダに保存し、開く

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\watch-install.ps1

.EXAMPLE
  # インストールせずにスクリーンショットだけ撮る
  powershell -ExecutionPolicy Bypass -File .\watch-install.ps1 -ScreenshotOnly
#>
param(
    [string]$Adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe",
    [string]$Device = "",
    [string]$Apk = "",
    [string]$SearchDir = "$env:USERPROFILE\Downloads",
    [string]$OutDir = "$env:USERPROFILE\Downloads",
    [switch]$ScreenshotOnly
)

# Windows PowerShell 5.1 treats stderr from native commands (adb) as errors,
# so keep "Continue" and check results explicitly.
$ErrorActionPreference = "Continue"
$Package = "com.mywatchfaces.meridian"

function Step($msg) { Write-Host "`n== $msg" -ForegroundColor Cyan }
function Fail($msg) {
    Write-Host "エラー: $msg" -ForegroundColor Red
    # 画面を点けたままにする設定を戻してから終了する
    if ($script:Device) { & $Adb -s $script:Device shell svc power stayon false 2>&1 | Out-Null }
    exit 1
}

# ---- adb -----------------------------------------------------------------
if (-not (Test-Path $Adb)) {
    $cmd = Get-Command adb -ErrorAction SilentlyContinue
    if ($cmd) { $Adb = $cmd.Source } else { Fail "adb.exe が見つかりません: $Adb" }
}

# ---- 1. device -----------------------------------------------------------
Step "接続中のウォッチを確認"
if (-not $Device) {
    $lines = & $Adb devices | Select-Object -Skip 1 | Where-Object { $_ -match "\tdevice$" }
    $serials = $lines | ForEach-Object { ($_ -split "\t")[0] }
    # IP:port の形式を優先 (同じウォッチが mDNS 名でも出るため)
    $ipSerial = $serials | Where-Object { $_ -match "^\d+\.\d+\.\d+\.\d+:\d+$" } | Select-Object -First 1
    $Device = if ($ipSerial) { $ipSerial } else { $serials | Select-Object -First 1 }
}
if (-not $Device) { Fail "ウォッチが見つかりません。先に adb connect <IP>:<ポート> を実行してください。" }
$model = "$(& $Adb -s $Device shell getprop ro.product.model)".Trim()
Write-Host "接続先: $Device ($model)"

# スクリプトの実行中は画面を点けたままにする (最後に元に戻す)
function Wake-Watch {
    & $Adb -s $Device shell input keyevent KEYCODE_WAKEUP | Out-Null
    # 画面が実際に点く (Awake になる) まで最大 5 秒待つ
    for ($i = 0; $i -lt 10; $i++) {
        $state = "$(& $Adb -s $Device shell dumpsys power)"
        if ($state -match "mWakefulness=Awake") { return $true }
        Start-Sleep -Milliseconds 500
        & $Adb -s $Device shell input keyevent KEYCODE_WAKEUP | Out-Null
    }
    return $false
}
& $Adb -s $Device shell svc power stayon true 2>&1 | Out-Null
$null = Wake-Watch

if (-not $ScreenshotOnly) {
    # ---- 2. APK ------------------------------------------------------------
    Step "最新の APK を探す"
    if (-not $Apk) {
        $zip = Get-ChildItem $SearchDir -Filter "meridian-watchface*.zip" -File -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending | Select-Object -First 1
        $found = Get-ChildItem $SearchDir -Recurse -Filter "watchface-debug.apk" -File -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if ($zip -and (-not $found -or $zip.LastWriteTime -gt $found.LastWriteTime)) {
            $dest = Join-Path $SearchDir ("meridian-" + $zip.LastWriteTime.ToString("yyyyMMdd_HHmmss"))
            Write-Host "新しい zip を展開: $($zip.Name) -> $dest"
            Expand-Archive -Path $zip.FullName -DestinationPath $dest -Force -ErrorAction Stop
            $found = Get-ChildItem $dest -Recurse -Filter "watchface-debug.apk" -File | Select-Object -First 1
            # 展開したファイルの日時を zip に合わせ、次回も「最新」と判定できるようにする
            if ($found) { $found.LastWriteTime = $zip.LastWriteTime }
        }
        if (-not $found) { Fail "watchface-debug.apk が $SearchDir に見つかりません。GitHub から zip をダウンロードしてください。" }
        $Apk = $found.FullName
    }
    Write-Host "APK: $Apk ($((Get-Item $Apk).LastWriteTime))"

    # ---- 3. install --------------------------------------------------------
    Step "上書きインストール"
    $result = (& $Adb -s $Device install -r $Apk 2>&1) -join "`n"
    Write-Host $result
    if ($result -match "INSTALL_FAILED_UPDATE_INCOMPATIBLE") {
        Write-Host "署名が前の版と違うため上書きできません。" -ForegroundColor Yellow
        $ans = Read-Host "アンインストールしてから入れ直しますか？ テーマなどの設定は消えます (y/N)"
        if ($ans -ne "y") { Fail "中止しました。" }
        & $Adb -s $Device uninstall $Package | Out-Host
        $result = (& $Adb -s $Device install $Apk 2>&1) -join "`n"
        Write-Host $result
    }
    if ($result -notmatch "Success") { Fail "インストールに失敗しました。" }

    # ---- 4. activate -------------------------------------------------------
    Step "Meridian をウォッチフェイスに設定"
    # Wear OS 4 以降のデバッグ用ブロードキャスト。失敗しても続行する
    & $Adb -s $Device shell am broadcast -a com.google.android.wearable.app.DEBUG_SURFACE `
        --es operation set-watchface --es watchFaceId $Package 2>&1 | Out-Null
    Start-Sleep -Seconds 3
}

# ---- 5. screenshot ---------------------------------------------------------
Step "スクリーンショット"
if (Wake-Watch) { Write-Host "画面: 点灯中" } else { Write-Host "画面を点灯できませんでした。ウォッチをタップしてください。" -ForegroundColor Yellow }
# 点灯直後のアニメーションが終わるのを待つ
Start-Sleep -Seconds 2
$remote = "/sdcard/meridian_screenshot.png"
$out = Join-Path $OutDir ("meridian_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".png")
& $Adb -s $Device shell screencap -p $remote | Out-Null
& $Adb -s $Device pull $remote $out 2>&1 | Out-Null
& $Adb -s $Device shell rm $remote | Out-Null
# 画面を点けたままにする設定を元に戻す
& $Adb -s $Device shell svc power stayon false 2>&1 | Out-Null
if (-not (Test-Path $out)) { Fail "スクリーンショットを保存できませんでした。" }

Write-Host "`n保存先: $out" -ForegroundColor Green
Invoke-Item $out
