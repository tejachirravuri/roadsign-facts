; t=4.88s frame 117
(assert (road-type "autobahn"))
; t=7.58s frame 182
(assert (speed-limit 60))
; t=11.33s frame 272
(assert (sign "slippery road"))
; t=12.58s frame 302
(assert (sign "road works"))
; t=13.62s frame 327
(retract-fact sign "slippery road")
; t=14.67s frame 352
(retract-fact sign "road works")
; t=19.92s frame 478
(assert (sign "keep right"))
; t=22.17s frame 532
(retract-fact sign "keep right")
; t=22.25s frame 534
(assert (sign "yield"))
; t=26.25s frame 630
(retract-fact sign "yield")
; t=43.00s frame 1032
(assert (sign "road works"))
; t=45.29s frame 1087
(assert (sign "ahead only"))
; t=45.46s frame 1091
(assert (sign "danger"))
; t=45.92s frame 1102
(retract-fact sign "road works")
; t=46.00s frame 1104
(assert (sign "stop"))
; t=48.25s frame 1158
(retract-fact sign "danger")
; t=48.29s frame 1159
(retract-fact sign "stop")
; t=49.46s frame 1187
(retract-fact sign "ahead only")
; t=65.12s frame 1563
(retract-fact speed-limit 60)
; t=65.12s frame 1563
(assert (speed-limit 80))
; t=74.38s frame 1785
(assert (sign "no overtaking"))
