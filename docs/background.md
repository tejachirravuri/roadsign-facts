# Background

## The internship

In the summer semester 2021 I did my research internship at the Chair of
Computer Engineering (Prof. Dr. Wolfram Hardt) at TU Chemnitz, supervised by
Julkar Nine. The topic was *Facts generation from multiple image processing
algorithms*: several camera based algorithms run on Raspberry Pis in a car,
their outputs are turned into facts and sent over CAN (PiCAN2 boards) to a
comprehension level, where an expert system fires rules on them.

The sub tasks given by the chair:

1. Collect and analyse the available image processing algorithms
2. Literature survey on existing approaches, expert systems and CAN
   communication via PiCAN2
3. Trigger every algorithm at the same instant of time, optimise the
   algorithms and extract their outputs
4. Convert the outputs into facts and send them to the comprehension level
   via PiCAN2
5. Evaluate the algorithms on a Raspberry Pi 3 B
6. Check and report the performance of the combined algorithm (FPS,
   resources)

## What I did in 2021

I received two Python scripts from earlier student projects: one for
traffic lights and speed signs (colour masks, ellipse fitting, HOG features
with pre-trained SVM classifiers, hand made digit features) and one for
Autobahn signs (contours and arrow / number features). My report was titled
*Optimization of Image Processing Algorithms*.

- **Getting them to run again.** The scripts were written for older Python
  and package versions. They failed on almost every test video with
  `AttributeError: 'NoneType' object has no attribute 'shape'` (frames read
  past the end of the video), `ZeroDivisionError` (FPS computed over zero
  time) and `cv2.error` in `cvtColor` (OpenCV API changes). I found a set of
  package versions that worked with Python 3.7 and guarded the read loop.
- **Making them faster.** Most of the time per frame went into
  `cv2.VideoCapture.read`, which decodes in the same thread as the image
  processing. I moved reading and showing frames into their own threads.
  The traffic sign / light script went from 151.8 s to about 96 s on a 75 s
  test clip.

## What I would measure differently today

The reader thread I used then kept only the newest frame. When the
detection is slower than decoding, frames are skipped without anyone
noticing, so part of the higher "FPS" was simply less work being done, and
the frame counter in the display thread counted repeated frames. My own
numbers show it: on the Autobahn clip the threaded version took longer
(55 s instead of 31 s) but reported a higher frame rate. Accuracy was
judged by watching the output.

## What this repository is

A clean reimplementation of the whole chain, written from scratch, not a
copy of the scripts I was given:

| Sub task | Here |
|---|---|
| 1 algorithms | three detectors with modern OpenCV: traffic lights, traffic signs (GTSRB classifier), direction signs / road type |
| 3 same instant, optimisation | one frame is handed to all detectors at once in a thread pool; decoding runs ahead in its own thread without dropping frames; a separate camera mode that drops frames and counts them |
| 4 facts and CAN | temporal voting turns detections into facts, which are written as CLIPS facts and encoded as 8 byte CAN frames (virtual bus here, python-can / socketcan for a PiCAN2) |
| 5 Raspberry Pi | not done here, no Pi available; the benchmark runs unchanged on a Pi and has a one-thread setting as a rough stand-in |
| 6 performance | benchmark of all pipeline modes with frames processed, frames dropped, latency and CPU use, plus the classifier's accuracy on the GTSRB test set |

The idea of moving `VideoCapture.read` into a thread is well known (Adrian
Rosebrock's posts on faster video FPS with OpenCV and the `imutils` video
classes were my starting point in 2021). The classes in `roadsign/video.py`
are my own and differ in the part that matters for measuring: the queued
source never drops a frame and the latest-frame source counts what it
drops.
