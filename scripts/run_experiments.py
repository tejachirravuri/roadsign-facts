#!/usr/bin/env python3
"""Reproduces results/: facts for every clip, figures and the benchmark.

    python scripts/run_experiments.py [--bench] [--videos data/videos]
"""
import argparse
import csv
import json
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
warnings.filterwarnings("ignore")

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from roadsign.can import Comprehension, VirtualBus, encode  # noqa: E402
from roadsign.facts import write_clips, write_jsonl  # noqa: E402
from roadsign.pipeline import Pipeline, default_detectors  # noqa: E402
from roadsign.viz import draw  # noqa: E402

MODEL = ROOT / "models" / "signs_hog_svm.npz"


def scale_for(path):
    """Full HD clips are processed at half size (960x540)."""
    cap = cv2.VideoCapture(str(path))
    w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    cap.release()
    return 0.5 if w >= 1600 else 1.0


def facts_for_all(videos, out):
    (out / "facts").mkdir(parents=True, exist_ok=True)
    pipeline = Pipeline(default_detectors(MODEL))
    summary, sheets = [], []
    for path in videos:
        bus, rx = VirtualBus(), Comprehension()
        best = {}       # one example frame per detection kind for the contact sheet
        evidence = []   # crop of the detection behind every asserted fact

        def on_frame(frame, detections, events, facts):
            for d in detections:
                key = (d.kind, d.label)
                if key not in best or d.score > best[key][0]:
                    best[key] = (d.score, frame.index, draw(frame.image, detections, facts))
            for ev in events:
                if ev.action != "assert":
                    continue
                match = [d for d in detections if KIND[ev.name] == d.kind and d.label == ev.value]
                crop = evidence_crop(frame.image, max(match, key=lambda d: d.score).box) if match else None
                evidence.append(("%.1fs %s %s" % (ev.t, ev.name, ev.value), crop))

        stats, facts = pipeline.run(path, "parallel", scale_for(path), on_frame=on_frame,
                                    on_event=lambda ev: bus.send(encode(ev)))
        rx.drain(bus)
        stem = path.stem
        write_jsonl(out / "facts" / ("%s.jsonl" % stem), facts.events)
        write_clips(out / "facts" / ("%s.clp" % stem), facts.events)
        (out / "facts" / ("%s_can.log" % stem)).write_text("\n".join(f.candump() for f in bus.log) + "\n")
        s = stats.summary()
        s["events"] = [e.as_dict() for e in facts.events]
        s["received"] = {k: sorted(v) for k, v in rx.facts.items() if v}
        summary.append(s)
        print("%-20s %5d frames %6.1f fps  facts %3d  %s" % (stem, s["frames_processed"], s["processed_fps"],
                                                           len(facts.events), s["detections"]))
        for (kind, label), (_, idx, img) in sorted(best.items()):
            sheets.append(("%s  f%d  %s %s" % (stem, idx, kind, label), img))
        if evidence:
            evidence_sheet(evidence, out / "evidence" / ("%s.jpg" % stem))
    (out / "facts_summary.json").write_text(json.dumps(summary, indent=1))
    return summary, sheets


KIND = {"speed-limit": "speed_limit", "traffic-light": "traffic_light",
        "road-type": "direction_sign", "sign": "sign"}


def evidence_crop(image, box, size=150):
    x, y, w, h = box
    m = max(w, h)
    pad = max(m, 40)                    # small lights need context to be judged
    H, W = image.shape[:2]
    crop = image[max(0, y - pad):min(H, y + h + pad), max(0, x - pad):min(W, x + w + pad)]
    return cv2.resize(crop, (size, size), interpolation=cv2.INTER_NEAREST)


def evidence_sheet(items, path, cols=8, size=150):
    path.parent.mkdir(parents=True, exist_ok=True)
    tiles = []
    for title, crop in items:
        t = crop.copy() if crop is not None else np.zeros((size, size, 3), np.uint8)
        cv2.rectangle(t, (0, 0), (size, 14), (0, 0, 0), -1)
        cv2.putText(t, title[:28], (2, 10), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (255, 255, 255), 1, cv2.LINE_AA)
        tiles.append(t)
    while len(tiles) % cols:
        tiles.append(np.zeros((size, size, 3), np.uint8))
    cv2.imwrite(str(path), np.vstack([np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)]),
                [cv2.IMWRITE_JPEG_QUALITY, 85])


def contact_sheet(sheets, path, cols=4, tile=(480, 270)):
    tiles = []
    for title, img in sheets:
        t = cv2.resize(img, tile, interpolation=cv2.INTER_AREA)
        cv2.rectangle(t, (0, tile[1] - 20), (tile[0], tile[1]), (0, 0, 0), -1)
        cv2.putText(t, title, (4, tile[1] - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)
        tiles.append(t)
    while len(tiles) % cols:
        tiles.append(np.zeros_like(tiles[0]))
    rows = [np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)]
    cv2.imwrite(str(path), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 85])


def timeline(summary, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    colors = {"speed-limit": "#e69f00", "traffic-light": "#d62728", "road-type": "#1f77b4", "sign": "#7f7f7f"}
    fig, axes = plt.subplots(len(summary), 1, figsize=(12, 0.9 * len(summary) + 1), sharex=False)
    for ax, s in zip(axes, summary):
        duration = s["frames_in_video"] / 25.0
        open_ = {}
        lanes = {"speed-limit": 3, "traffic-light": 2, "road-type": 1, "sign": 0}
        for ev in s["events"]:
            key = (ev["name"], ev["value"])
            if ev["action"] == "assert":
                open_[key] = ev["t"]
            elif key in open_:
                start = open_.pop(key)
                ax.barh(lanes[ev["name"]], ev["t"] - start, left=start, color=colors[ev["name"]], height=0.7)
                ax.text(start, lanes[ev["name"]], " " + ev["value"], va="center", fontsize=6)
        end = max([duration] + [e["t"] for e in s["events"]])
        for (name, value), start in open_.items():
            ax.barh(lanes[name], end - start, left=start, color=colors[name], height=0.7)
            ax.text(start, lanes[name], " " + value, va="center", fontsize=6)
        ax.set_yticks(list(lanes.values()))
        ax.set_yticklabels(list(lanes.keys()), fontsize=6)
        ax.set_xlim(0, end)
        ax.set_title(s["video"], fontsize=8, loc="left")
        ax.tick_params(axis="x", labelsize=6)
    axes[-1].set_xlabel("video time [s]")
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def consistency(summary, out, ref="both1d.mp4", tolerance=1.5):
    """The both1* clips are one drive at four resolutions and autobahn5a1
    contains the same drive again. Facts found at one resolution should be
    found at the others; this measures how much the resolution matters."""
    S = {s["video"]: s for s in summary}
    if ref not in S:
        return None

    def asserts(video, offset=0.0, lo=None, hi=None):
        return [(e["name"], e["value"], e["t"] - offset) for e in S[video]["events"]
                if e["action"] == "assert" and (lo is None or lo <= e["t"] <= hi)]

    def first(video, value, after=0.0):
        return next(e["t"] for e in S[video]["events"]
                    if e["action"] == "assert" and e["value"] == value and e["t"] > after)

    reference = asserts(ref)
    cases = [(v, 0.0, None, None) for v in ("both1a.mp4", "both1b.mp4", "both1c.mp4") if v in S]
    if "autobahn5a1.mp4" in S:
        offset = first("autobahn5a1.mp4", "slippery road", 100) - first(ref, "slippery road")
        cases.append(("autobahn5a1.mp4", offset, offset, offset + 75))
    rows = []
    for video, offset, lo, hi in cases:
        other = asserts(video, offset, lo, hi)
        same = lambda a, b: a[0] == b[0] and a[1] == b[1] and abs(a[2] - b[2]) <= tolerance
        rows.append({
            "video": video, "offset_s": round(offset, 1),
            "facts": len(other),
            "also_in_reference": sum(any(same(o, r) for r in reference) for o in other),
            "reference_facts": len(reference),
            "reference_found": sum(any(same(o, r) for o in other) for r in reference),
        })
    (out / "consistency.json").write_text(json.dumps({"reference": ref, "tolerance_s": tolerance,
                                                     "rows": rows}, indent=1))
    return rows


def bench(videos, out):
    from roadsign.bench import run_bench
    rows = []
    for threads in (None, 1):
        for path in videos:
            scales = [1.0, 0.5] if scale_for(path) == 0.5 else [1.0]
            rows += run_bench([path], ["sequential", "threaded", "parallel", "live"], scales,
                              MODEL, max_frames=600, opencv_threads=threads)
            print("bench", path.name, "threads", threads, "done")
    with (out / "bench.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return rows


def bench_figure(rows, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    modes = ["sequential", "threaded", "parallel", "live"]
    groups = sorted({(r["video"], r["scale"], r["opencv_threads"]) for r in rows},
                    key=lambda g: (g[2] != 1, g[0], -g[1]))
    fig, ax = plt.subplots(figsize=(12, 4.5))
    width = 0.2
    for i, mode in enumerate(modes):
        vals = []
        for g in groups:
            r = [x for x in rows if (x["video"], x["scale"], x["opencv_threads"]) == g and x["mode"] == mode]
            vals.append(r[0]["processed_fps"] if r else 0)
        ax.bar(np.arange(len(groups)) + (i - 1.5) * width, vals, width, label=mode)
    ax.set_xticks(np.arange(len(groups)))
    ax.set_xticklabels(["%s\nx%.1f, %s thr" % (v.replace(".mp4", ""), s, t) for v, s, t in groups],
                       fontsize=7)
    ax.set_ylabel("frames processed per second")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--videos", type=Path, default=ROOT / "data" / "videos")
    p.add_argument("--out", type=Path, default=ROOT / "results")
    p.add_argument("--bench", action="store_true")
    p.add_argument("--only-bench", action="store_true", help="skip the facts runs")
    p.add_argument("--bench-videos", nargs="+",
                   default=["video1.mp4", "trafficLight1.mp4", "both1d.mp4", "auto2.mp4"])
    args = p.parse_args()
    (args.out / "figures").mkdir(parents=True, exist_ok=True)
    videos = sorted(p for p in args.videos.iterdir() if p.suffix in (".mp4", ".avi"))
    if not args.only_bench:
        summary, sheets = facts_for_all(videos, args.out)
        contact_sheet(sheets, args.out / "figures" / "detections.jpg")
        timeline(summary, args.out / "figures" / "facts_timeline.png")
        consistency(summary, args.out)
    if args.bench or args.only_bench:
        rows = bench([args.videos / v for v in args.bench_videos], args.out)
        bench_figure(rows, args.out / "figures" / "bench.png")


if __name__ == "__main__":
    main()
