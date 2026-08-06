#!/usr/bin/env python3
"""
把 COROS Training Hub 匯出的一整包 .fit 檔，壓縮成一個小 CSV。

用途：177 筆活動的原始 FIT 檔可能有數百 MB，難以搬動或分享。
這支腳本把每筆活動濃縮成一列摘要（約 40 個欄位），
輸出的 CSV 通常只有幾十 KB，方便丟給別人分析或自己畫圖。

用法：
    pip install fitdecode
    python3 coros_summary.py <FIT檔資料夾> -o coros_summary.csv

選項：
    -o, --output    輸出 CSV 路徑（預設 coros_summary.csv）
    --tz            本地時區相對 UTC 的時差，台灣是 8（預設 8）
    --quiet         不要印出逐筆進度
"""

import argparse
import csv
import datetime
import gzip
import os
import statistics
import sys
import tempfile
from collections import Counter

try:
    import fitdecode
except ImportError:
    sys.exit("需要 fitdecode，請先執行：pip install fitdecode")


# 心率分箱：每 10 bpm 一格，記錄各格停留秒數
HR_BINS = list(range(80, 200, 10))

FIELDNAMES = [
    "activity_id",
    "date",
    "time",
    "weekday",
    "sport",
    "sub_sport",
    "distance_km",
    "duration_s",
    "duration_hms",
    "elapsed_s",
    "avg_pace_s_per_km",
    "avg_pace",
    "best_pace",
    "avg_hr",
    "max_hr",
    "min_hr",
    "avg_cadence_spm",
    "max_cadence_spm",
    "avg_step_length_mm",
    "avg_power_w",
    "calories",
    "ascent_m",
    "descent_m",
    "temp_c",
    "avg_stance_time_ms",
    "avg_vertical_oscillation_mm",
    "avg_vertical_ratio_pct",
    "efficiency_index",
    "hr_drift_bpm",
    "decoupling_pct",
    "n_laps",
    "n_records",
    "has_gps",
    "start_lat",
    "start_lon",
    "device",
] + [f"hr_{b}_{b + 9}_s" for b in HR_BINS]


def fmt_pace(mps):
    """速度 (m/s) 轉成 分:秒 /km。"""
    if not mps or mps <= 0:
        return ""
    s = 1000 / mps
    return f"{int(s // 60)}:{int(s % 60):02d}"


def fmt_hms(seconds):
    if not seconds:
        return ""
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def mean_or_none(values):
    vals = [v for v in values if isinstance(v, (int, float))]
    return statistics.mean(vals) if vals else None


def read_fit(path):
    """回傳 (records, laps, session, file_id)。支援 .fit 與 .fit.gz。"""
    records, laps, session, file_id = [], [], None, None

    if path.lower().endswith(".gz"):
        with gzip.open(path, "rb") as fh:
            data = fh.read()
        tmp = tempfile.NamedTemporaryFile(suffix=".fit", delete=False)
        try:
            tmp.write(data)
            tmp.close()
            return read_fit(tmp.name)
        finally:
            os.unlink(tmp.name)

    with fitdecode.FitReader(path) as reader:
        for frame in reader:
            if frame.frame_type != fitdecode.FIT_FRAME_DATA:
                continue
            row = {f.name: f.value for f in frame.fields}
            if frame.name == "record":
                records.append(row)
            elif frame.name == "lap":
                laps.append(row)
            elif frame.name == "session":
                # 多節活動（如三鐵）會有多個 session，取距離最長的那個
                if session is None or (row.get("total_distance") or 0) > (
                    session.get("total_distance") or 0
                ):
                    session = row
            elif frame.name == "file_id":
                file_id = row
    return records, laps, session, file_id


def summarise(path, tz_offset):
    records, laps, session, file_id = read_fit(path)
    if session is None:
        return None

    start = session.get("start_time") or (file_id or {}).get("time_created")
    if start is None:
        return None
    local = start + datetime.timedelta(hours=tz_offset)

    dist = session.get("total_distance") or 0
    dur = session.get("total_timer_time") or 0
    avg_hr = session.get("avg_heart_rate")
    cadence = session.get("avg_running_cadence")
    max_cadence = session.get("max_running_cadence")

    # 效率指數：每一次心跳前進幾公尺。跨時期比較有氧體能最公平的指標。
    ei = None
    if dist > 100 and dur > 0 and avg_hr:
        ei = round((dist / dur) * 60 / avg_hr, 4)

    # 心率漂移與脫鉤：把逐秒資料切前後半段比較
    hr_series = [r["heart_rate"] for r in records if r.get("heart_rate")]
    drift = None
    if len(hr_series) >= 120:
        half = len(hr_series) // 2
        drift = round(
            statistics.mean(hr_series[half:]) - statistics.mean(hr_series[:half]), 1
        )

    paired = [
        (r["speed"], r["heart_rate"])
        for r in records
        if r.get("speed") and r.get("heart_rate")
    ]
    decoupling = None
    if len(paired) >= 120:
        half = len(paired) // 2
        first = statistics.mean(s for s, _ in paired[:half]) / statistics.mean(
            h for _, h in paired[:half]
        )
        second = statistics.mean(s for s, _ in paired[half:]) / statistics.mean(
            h for _, h in paired[half:]
        )
        decoupling = round((second - first) / first * 100, 1)

    # 心率分箱停留秒數（逐秒紀錄，一筆約等於一秒）
    bins = Counter()
    for hr in hr_series:
        edge = min(HR_BINS, key=lambda b: abs(b - (hr // 10) * 10))
        if (hr // 10) * 10 in HR_BINS:
            edge = (hr // 10) * 10
        elif hr < HR_BINS[0]:
            edge = HR_BINS[0]
        else:
            edge = HR_BINS[-1]
        bins[edge] += 1

    # 溫度優先取 session，沒有就用各圈平均
    temp = session.get("avg_temperature")
    if temp is None:
        temp = mean_or_none([lap.get("avg_temperature") for lap in laps])
        if temp is not None:
            temp = round(temp)

    gps = [r for r in records if r.get("position_lat") is not None]
    semicircle = 180 / 2**31

    row = {
        "activity_id": os.path.basename(path).split("-")[-1].split(".")[0],
        "date": local.strftime("%Y-%m-%d"),
        "time": local.strftime("%H:%M"),
        "weekday": "一二三四五六日"[local.weekday()],
        "sport": session.get("sport"),
        "sub_sport": session.get("sub_sport"),
        "distance_km": round(dist / 1000, 3) if dist else 0,
        "duration_s": round(dur),
        "duration_hms": fmt_hms(dur),
        "elapsed_s": round(session.get("total_elapsed_time") or 0),
        "avg_pace_s_per_km": round(dur / (dist / 1000)) if dist > 100 and dur else "",
        "avg_pace": fmt_pace(session.get("avg_speed")),
        "best_pace": fmt_pace(session.get("max_speed")),
        "avg_hr": avg_hr,
        "max_hr": session.get("max_heart_rate"),
        "min_hr": session.get("min_heart_rate"),
        "avg_cadence_spm": cadence * 2 if cadence else "",
        "max_cadence_spm": max_cadence * 2 if max_cadence else "",
        "avg_step_length_mm": session.get("avg_step_length") or "",
        "avg_power_w": session.get("avg_power") or "",
        "calories": session.get("total_calories") or "",
        "ascent_m": session.get("total_ascent") or 0,
        "descent_m": session.get("total_descent") or 0,
        "temp_c": temp if temp is not None else "",
        "avg_stance_time_ms": session.get("avg_stance_time") or "",
        "avg_vertical_oscillation_mm": session.get("avg_vertical_oscillation") or "",
        "avg_vertical_ratio_pct": session.get("avg_vertical_ratio") or "",
        "efficiency_index": ei if ei else "",
        "hr_drift_bpm": drift if drift is not None else "",
        "decoupling_pct": decoupling if decoupling is not None else "",
        "n_laps": len(laps),
        "n_records": len(records),
        "has_gps": 1 if gps else 0,
        "start_lat": round(gps[0]["position_lat"] * semicircle, 5) if gps else "",
        "start_lon": round(gps[0]["position_long"] * semicircle, 5) if gps else "",
        "device": (file_id or {}).get("product_name") or "",
    }
    for b in HR_BINS:
        row[f"hr_{b}_{b + 9}_s"] = bins.get(b, 0)
    return row


def main():
    parser = argparse.ArgumentParser(
        description="把 COROS 匯出的 FIT 檔壓縮成一個 CSV 摘要"
    )
    parser.add_argument("folder", help="放 .fit 檔的資料夾（會遞迴搜尋子資料夾）")
    parser.add_argument("-o", "--output", default="coros_summary.csv")
    parser.add_argument("--tz", type=int, default=8, help="本地時區時差，台灣是 8")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    paths = []
    for root, _dirs, files in os.walk(args.folder):
        for name in files:
            if name.lower().endswith((".fit", ".fit.gz")):
                paths.append(os.path.join(root, name))
    paths.sort()

    if not paths:
        sys.exit(f"在 {args.folder} 底下找不到任何 .fit 檔")

    print(f"找到 {len(paths)} 個 FIT 檔，開始解析…")

    rows, seen, failed = [], set(), []
    for i, path in enumerate(paths, 1):
        try:
            row = summarise(path, args.tz)
        except Exception as exc:  # 單一壞檔不該中斷整批
            failed.append((os.path.basename(path), str(exc)))
            continue
        if row is None:
            failed.append((os.path.basename(path), "沒有 session 資料"))
            continue
        # 同一筆活動重複匯出時去重
        key = (row["date"], row["time"], row["duration_s"], row["distance_km"])
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)
        if not args.quiet:
            print(
                f"  [{i}/{len(paths)}] {row['date']} {row['sport'] or '?':<12} "
                f"{row['distance_km']:>6.2f}km  {row['duration_hms']}"
            )

    rows.sort(key=lambda r: (r["date"], r["time"]))

    with open(args.output, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    size_kb = os.path.getsize(args.output) / 1024
    print(f"\n完成：{len(rows)} 筆活動 → {args.output} ({size_kb:.0f} KB)")
    if len(paths) - len(rows) - len(failed):
        print(f"  （去除重複 {len(paths) - len(rows) - len(failed)} 筆）")
    if failed:
        print(f"  {len(failed)} 個檔案解析失敗：")
        for name, reason in failed[:10]:
            print(f"    {name}: {reason}")
        if len(failed) > 10:
            print(f"    …以及其他 {len(failed) - 10} 個")

    # 印出一份快速總覽，不傳檔案給任何人也看得到重點
    runs = [r for r in rows if r["distance_km"] and r["efficiency_index"]]
    if runs:
        print(f"\n期間：{rows[0]['date']} ～ {rows[-1]['date']}")
        print(f"總距離：{sum(r['distance_km'] for r in rows):.1f} km")
        print(f"總時數：{sum(r['duration_s'] for r in rows) / 3600:.1f} 小時")
        by_sport = Counter(r["sport"] for r in rows)
        print("運動類型：" + "、".join(f"{k} {v}次" for k, v in by_sport.most_common()))
        best = max(runs, key=lambda r: r["efficiency_index"])
        print(
            f"效率指數最高：{best['date']} "
            f"{best['distance_km']}km {best['avg_pace']}/km "
            f"HR{best['avg_hr']} → EI {best['efficiency_index']}"
        )


if __name__ == "__main__":
    main()
