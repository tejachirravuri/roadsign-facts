; t=4.42s frame 106
(assert (road-type "autobahn"))
; t=6.88s frame 165
(assert (speed-limit 60))
; t=10.67s frame 256
(assert (sign "slippery road"))
; t=11.58s frame 278
(assert (sign "road works"))
; t=13.58s frame 326
(retract-fact sign "slippery road")
; t=14.62s frame 351
(retract-fact sign "road works")
; t=15.21s frame 365
(assert (sign "traffic signals"))
; t=16.54s frame 397
(assert (sign "ahead only"))
; t=17.92s frame 430
(retract-fact sign "traffic signals")
; t=18.58s frame 446
(retract-fact sign "ahead only")
; t=18.96s frame 455
(assert (sign "keep right"))
; t=20.29s frame 487
(assert (traffic-light "green"))
; t=20.50s frame 492
(assert (sign "yield"))
; t=22.17s frame 532
(retract-fact sign "keep right")
; t=22.25s frame 534
(retract-fact traffic-light "green")
; t=23.08s frame 554
(assert (sign "keep right"))
; t=25.33s frame 608
(retract-fact sign "keep right")
; t=26.21s frame 629
(retract-fact sign "yield")
; t=41.33s frame 992
(assert (sign "road works"))
; t=43.79s frame 1051
(assert (sign "danger"))
; t=45.12s frame 1083
(assert (sign "stop"))
; t=45.33s frame 1088
(assert (sign "ahead only"))
; t=45.83s frame 1100
(assert (sign "ahead or left"))
; t=45.88s frame 1101
(retract-fact sign "road works")
; t=47.96s frame 1151
(retract-fact sign "ahead or left")
; t=48.25s frame 1158
(retract-fact sign "danger")
; t=48.25s frame 1158
(retract-fact sign "stop")
; t=49.42s frame 1186
(retract-fact sign "ahead only")
; t=53.67s frame 1288
(assert (traffic-light "red"))
; t=55.21s frame 1325
(retract-fact traffic-light "red")
; t=57.92s frame 1390
(retract-fact speed-limit 60)
; t=57.92s frame 1390
(assert (speed-limit 80))
; t=73.04s frame 1753
(assert (sign "no overtaking"))
