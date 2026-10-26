; t=5.79s frame 139
(assert (road-type "autobahn"))
; t=8.50s frame 204
(assert (speed-limit 60))
; t=12.29s frame 295
(assert (sign "slippery road"))
; t=13.46s frame 323
(assert (sign "road works"))
; t=14.88s frame 357
(retract-fact sign "slippery road")
; t=15.92s frame 382
(retract-fact sign "road works")
; t=17.17s frame 412
(assert (sign "traffic signals"))
; t=19.25s frame 462
(retract-fact sign "traffic signals")
; t=20.54s frame 493
(assert (sign "keep right"))
; t=23.12s frame 555
(assert (sign "yield"))
; t=23.46s frame 563
(retract-fact sign "keep right")
; t=27.50s frame 660
(retract-fact sign "yield")
