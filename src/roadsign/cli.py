"""Command line interface.

    roadsign run VIDEO [--mode parallel] [--out DIR] [--annotate] [--can-log]
    roadsign bench VIDEO... [--modes sequential,threaded,parallel,live] [--scales 1,0.5]
    roadsign train GTSRB_DIR [--background-videos ...] [--model models/signs_hog_svm.joblib]
    roadsign eval GTSRB_DIR [--model ...]
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from pathlib import Path

from . import __version__

log = logging.getLogger("roadsign")
DEFAULT_MODEL = str(Path(__file__).resolve().parents[2] / "models" / "signs_hog_svm.joblib")


def cmd_run(args):
    import cv2
    from .can import Comprehension, VirtualBus, encode
    from .facts import write_clips, write_jsonl
    from .pipeline import Pipeline, default_detectors
    from .viz import draw

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = Path(args.video).stem
    bus = VirtualBus()
    receiver = Comprehension()
    writer = None
    detections_log = open(out / ("%s_detections.jsonl" % stem), "w", encoding="utf-8")

    def on_event(ev):
        bus.send(encode(ev))
        log.info("%7.2fs  %-7s %s %s", ev.t, ev.action, ev.name, ev.value)

    def on_frame(frame, detections, events, facts):
        nonlocal writer
        if detections:
            detections_log.write(json.dumps({"frame": frame.index, "t": round(frame.t, 3),
                                             "detections": [d.as_dict() for d in detections]}) + "\n")
        if args.annotate:
            image = draw(frame.image, detections, facts)
            if writer is None:
                h, w = image.shape[:2]
                writer = cv2.VideoWriter(str(out / ("%s_annotated.mp4" % stem)),
                                         cv2.VideoWriter_fourcc(*"mp4v"), 25, (w, h))
            writer.write(image)

    pipeline = Pipeline(default_detectors(args.model))
    stats, facts = pipeline.run(args.video, args.mode, args.scale, args.max_frames,
                                on_frame=on_frame, on_event=on_event)
    detections_log.close()
    if writer is not None:
        writer.release()
    receiver.drain(bus)

    write_jsonl(out / ("%s_facts.jsonl" % stem), facts.events)
    write_clips(out / ("%s_facts.clp" % stem), facts.events)
    (out / ("%s_final.clp" % stem)).write_text(facts.deffacts())
    if args.can_log:
        (out / ("%s_can.log" % stem)).write_text("\n".join(f.candump() for f in bus.log) + "\n")
    (out / ("%s_stats.json" % stem)).write_text(json.dumps(stats.summary(), indent=1))
    s = stats.summary()
    print("%s: %d frames in %.1fs (%.1f fps), %d dropped, %d fact events, %d CAN frames"
          % (stem, s["frames_processed"], s["wall_s"], s["processed_fps"], s["frames_dropped"],
             len(facts.events), len(bus.log)))
    print("received:", {k: sorted(v) for k, v in receiver.facts.items() if v})
    return 0


def cmd_bench(args):
    from .bench import run_bench
    rows = run_bench(args.videos, args.modes.split(","), [float(s) for s in args.scales.split(",")],
                     args.model, args.max_frames, args.repeat, args.opencv_threads)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print("%-20s %-10s x%.2f  %6.1f fps  %5d/%5d frames  dropped %5d  frame %6.1f ms  cpu %s%%"
              % (r["video"], r["mode"], r["scale"], r["processed_fps"], r["frames_processed"],
                 r["frames_in_video"], r["frames_dropped"], r["frame_ms_mean"], r["cpu_percent"]))
    print("written", out)
    return 0


def cmd_train(args):
    from .classifier import evaluate, train
    clf = train(args.gtsrb, args.background_videos, args.n_background, args.C, args.limit,
                Path(args.cache) if args.cache else None)
    clf.save(args.model)
    report = evaluate(clf, args.gtsrb)
    clf.meta["test_accuracy"] = report["accuracy"]
    clf.save(args.model)
    Path(args.model).with_suffix(".eval.json").write_text(json.dumps(report, indent=1))
    print("test accuracy %.4f, speed limits %.4f" % (report["accuracy"], report["speed_limit_accuracy"]))
    return 0


def cmd_eval(args):
    from .classifier import SignClassifier, evaluate
    report = evaluate(SignClassifier.load(args.model), args.gtsrb, args.limit)
    print(json.dumps({k: v for k, v in report.items() if k != "confusion"}, indent=1))
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="roadsign", description="Traffic sign and light facts from dashcam video")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("run", help="detect, build facts, send them over a virtual CAN bus")
    sp.add_argument("video")
    sp.add_argument("--mode", default="parallel", choices=["sequential", "threaded", "parallel", "live"])
    sp.add_argument("--scale", type=float, default=1.0)
    sp.add_argument("--max-frames", type=int)
    sp.add_argument("--model", default=DEFAULT_MODEL)
    sp.add_argument("--out", default="runs")
    sp.add_argument("--annotate", action="store_true", help="write an annotated video")
    sp.add_argument("--can-log", action="store_true", help="write the CAN frames in candump format")
    sp.set_defaults(func=cmd_run)

    sp = sub.add_parser("bench", help="compare pipeline modes and frame sizes")
    sp.add_argument("videos", nargs="+")
    sp.add_argument("--modes", default="sequential,threaded,parallel,live")
    sp.add_argument("--scales", default="1.0")
    sp.add_argument("--repeat", type=int, default=1)
    sp.add_argument("--max-frames", type=int)
    sp.add_argument("--opencv-threads", type=int, help="cv2.setNumThreads, e.g. 1 to mimic a small board")
    sp.add_argument("--model", default=DEFAULT_MODEL)
    sp.add_argument("--out", default="results/bench.csv")
    sp.set_defaults(func=cmd_bench)

    sp = sub.add_parser("train", help="train the sign classifier on GTSRB")
    sp.add_argument("gtsrb", help="folder with Train.csv, Test.csv, Train/ and Test/")
    sp.add_argument("--background-videos", nargs="+", required=True)
    sp.add_argument("--n-background", type=int, default=6000)
    sp.add_argument("--C", type=float, default=0.05)
    sp.add_argument("--limit", type=int)
    sp.add_argument("--cache", help="npz file to keep the extracted features in")
    sp.add_argument("--model", default=DEFAULT_MODEL)
    sp.set_defaults(func=cmd_train)

    sp = sub.add_parser("eval", help="accuracy of the sign classifier on the GTSRB test set")
    sp.add_argument("gtsrb")
    sp.add_argument("--model", default=DEFAULT_MODEL)
    sp.add_argument("--limit", type=int)
    sp.set_defaults(func=cmd_eval)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(message)s")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
