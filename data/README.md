# Data

## Test videos (`videos/`)

Dashcam clips handed out with the project at the Chair of Computer
Engineering, TU Chemnitz, as test material for the earlier student projects.
I do not know who recorded each of them. They are kept in this private
repository for testing and are not mine to redistribute.

They come from four drives; several clips are the same drive at a
different resolution, which is used in the results to see how much the
resolution matters.

| Drive | Clips | Resolution | Content |
|---|---|---|---|
| A | `autobahn5a1` (180 s), `both1a`-`both1d` (75 s), `3.avi` (29 s) | 1920x1080 down to 640x360 | federal road to a motorway junction: blue direction signs, roadworks, traffic lights, many warning and mandatory signs |
| B | `trafficLight1`, `1a`, `1B`, `1c` (23 s) | 1920x1080 down to 640x360 | junctions with traffic lights in front of a shopping centre |
| C | `video1`-`video4` (5 to 10 s) | 640x360 | country roads: 30, 50, 70 limits, yellow direction and town signs |
| D | `auto2` (30 s) | 1920x1080 | Autobahn near Kassel with an overhead sign gantry |

`both1a`-`both1d` are the same 75 s at 720x406, 1280x720, 640x360 and
1920x1080. `autobahn5a1` contains the same stretch from 101 s on. `3.avi` is
the start of drive A with a converter watermark. `auto2` has the dashcam's
speed and GPS overlay at the bottom.

## GTSRB (not included)

The sign classifier is trained on the German Traffic Sign Recognition
Benchmark (Stallkamp et al., 2011/2012): 39 209 training and 12 630 test
images in 43 classes. It is not part of this repository. Get it from the
benchmark site or the Kaggle mirror ("GTSRB - German Traffic Sign
Recognition Benchmark") and point `roadsign train` / `roadsign eval` at the
folder that contains `Train.csv`, `Test.csv`, `Train/` and `Test/`.

The trained model (`models/signs_hog_svm.joblib`, 3 MB) is included.
