; t=4.54s frame 109
(assert (road-type "autobahn"))
; t=7.29s frame 175
(assert (speed-limit 60))
; t=11.12s frame 267
(assert (sign "slippery road"))
; t=12.38s frame 297
(assert (sign "road works"))
; t=13.62s frame 327
(retract-fact sign "slippery road")
; t=14.67s frame 352
(retract-fact sign "road works")
; t=15.54s frame 373
(assert (sign "traffic signals"))
; t=18.00s frame 432
(retract-fact sign "traffic signals")
; t=19.00s frame 456
(assert (sign "keep right"))
; t=21.71s frame 521
(assert (sign "yield"))
; t=22.21s frame 533
(retract-fact sign "keep right")
; t=23.21s frame 557
(assert (sign "keep right"))
; t=25.38s frame 609
(retract-fact sign "keep right")
; t=26.25s frame 630
(retract-fact sign "yield")
; t=42.62s frame 1023
(assert (sign "road works"))
; t=44.38s frame 1065
(assert (sign "ahead only"))
; t=44.75s frame 1074
(assert (sign "danger"))
; t=45.46s frame 1091
(assert (sign "stop"))
; t=45.83s frame 1100
(assert (sign "ahead or left"))
; t=45.92s frame 1102
(retract-fact sign "road works")
; t=47.96s frame 1151
(retract-fact sign "ahead or left")
; t=48.29s frame 1159
(retract-fact sign "danger")
; t=48.29s frame 1159
(retract-fact sign "stop")
; t=49.46s frame 1187
(retract-fact sign "ahead only")
; t=54.62s frame 1311
(assert (traffic-light "red"))
; t=56.50s frame 1356
(retract-fact traffic-light "red")
; t=58.88s frame 1413
(retract-fact speed-limit 60)
; t=58.88s frame 1413
(assert (speed-limit 80))
; t=73.79s frame 1771
(assert (sign "no overtaking"))
