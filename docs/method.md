# Method

## Detectors

All three detectors take a BGR frame and return a list of detections
(kind, label, box, score). Full HD clips are processed at half size
(960 x 540); the detectors work with sizes relative to the frame.

### Traffic lights (`detect/lights.py`)

1. Upper 65 % of the frame, HSV.
2. Lit red lamps: red hue (both ends of the hue circle), saturation >= 110,
   value >= 170. Lit green lamps: hue 55 to 100 (traffic light green is
   bluish), value >= 170.
3. Blobs between 6e-6 and 1.5e-3 of the frame area, aspect 0.55 to 1.8,
   circularity >= 0.45.
4. The housing check: the area of two lamp diameters below a red lamp (or
   above a green one) must be dark (mean value <= 110) and unsaturated
   (mean saturation <= 100), the strips left and right of the lamp dark too,
   and the lamp at least 75 levels brighter than the housing.
5. The ring around the lamp (leaving out the glow right next to it) must not
   have the lamp's colour: a red lamp is not set in a red car or an orange
   wall. For red the ring check uses red to orange (hue up to 22), the lamp
   itself only true red (hue up to 7), so amber lamps are not reported as
   red.

### Traffic signs (`detect/signs.py`, `classifier.py`)

1. Candidates from a red mask (prohibition and warning signs have a red
   border) and a blue mask (mandatory signs), lower 25 % of the frame
   ignored. Bounding box between 2.5 % and 35 % of the frame height, aspect
   0.7 to 1.4, and either round (circularity of the hull > 0.6) or a
   triangle (fill of the box 0.4 to 0.65). Blue candidates must be round.
2. Each candidate is cropped with a 12 % margin and classified.
3. Classifier: 40 x 40 pixels, CLAHE on the grey image, HOG (10 x 10
   blocks, 5 x 5 cells, 9 bins, 1764 values) plus a 12 x 3 hue/saturation
   histogram, standardised, PCA to 400 dimensions, linear SVM (C = 0.05).
   44 classes: the 43 GTSRB classes and "background".
4. The background class is made of random crops (16 to 90 px) from the clips
   of drives B and D (`trafficLight1B`, `auto2`), so the other drives stay
   unseen. Candidates classified as background, or with a decision margin
   (best minus second best score) below 0.4, are dropped.
5. The inside of the candidate has to have the colour of the predicted class:
   white for speed limits and warning signs, yellow for priority road, blue
   for mandatory signs, red for stop and no entry. This removes red cars,
   lamps and posters the classifier happens to like.
6. Solid red regions that are not round are dropped before classification
   (stripes of red/white warning beacons), and blue candidates must be discs
   (circularity >= 0.84, filling at most 0.88 of their box; a square sign
   fills almost all of it).
7. Speed limit classes become `speed_limit` with the number as label, all
   other classes `sign` with the class name.

### Direction signs and road type (`detect/direction.py`)

German direction signs are blue on the Autobahn and yellow on other roads.

1. Upper 60 % of the frame. Blue panel: hue 100 to 125, tried with
   saturation >= 130 and >= 100 (the strict one keeps a pale blue sky from
   merging with the panel, the loose one finds panels in flat light).
   Yellow panel: hue 18 to 32, saturation and value >= 130.
2. Closed mask, contours of at least 0.6 % of the frame area,
   rectangularity (area / minimum area rectangle) >= 0.65, aspect 0.6 to 6,
   and not round (hull circularity <= 0.85, round blue signs are mandatory
   signs).
3. There has to be lettering on the panel: 1 % to 45 % of the filled
   outline must be white text (unsaturated, value > 110) on blue, or dark
   text on yellow. This is what rejects sky, water and buildings.

## Pipeline (`pipeline.py`, `video.py`)

| Mode | Reading | Detectors |
|---|---|---|
| sequential | in the main thread | one after the other |
| threaded | reader thread, queue of 64 frames, blocking | one after the other |
| parallel | reader thread, queue of 64 frames, blocking | all on the same frame in a thread pool |
| live | reader thread at the video frame rate, newest frame only | all on the same frame in a thread pool |

OpenCV releases the GIL during decoding and most image operations, so
threads are enough; no processes and no copies of frames are needed.

Measured per run: frames read, processed and dropped, wall time, processed
frames per second, CPU time of the process, time per detector and per frame,
and latency from decoding a frame to having its facts updated.

## Facts (`facts.py`)

For every fact type the values seen in the last 12 frames are counted, a
value needs at least 4 hits to be asserted.

| Fact | Asserted | Retracted |
|---|---|---|
| `speed-limit` | 4 of 12 frames | when a different limit is asserted |
| `traffic-light` | 4 of 12 frames | 1.5 s after it was last confirmed |
| `road-type` | 4 of 12 frames, autobahn = blue panel, road = yellow panel | when the other type is asserted |
| `sign` | 4 of 12 frames | 2 s after it was last confirmed |

Output: JSON lines, CLIPS `assert` commands and a final `deffacts` block.

## CAN (`can.py`)

Classic CAN frames with 8 data bytes:

| Byte | Content |
|---|---|
| 0 | 1 assert, 0 retract |
| 1 | value: km/h, light 1 red / 2 green, road 1 autobahn / 2 road, sign: GTSRB class id |
| 2 | source algorithm: 1 lights, 2 signs, 3 direction signs |
| 3 | reserved |
| 4-7 | video time in ms, uint32 little endian |

Ids 0x110 speed-limit, 0x120 traffic-light, 0x130 road-type, 0x140 sign
(lower id = higher priority on the bus). `VirtualBus` is used for runs on
one machine; `PythonCanBus("socketcan", "can0")` sends the same frames
through a PiCAN2. `Comprehension` is the receiving side: it decodes the
frames and keeps the current fact set.
