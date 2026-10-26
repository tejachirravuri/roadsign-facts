; t=4.67s frame 112
(assert (road-type "autobahn"))
; t=7.62s frame 183
(assert (speed-limit 60))
; t=11.42s frame 274
(assert (sign "slippery road"))
; t=13.62s frame 327
(retract-fact sign "slippery road")
; t=22.79s frame 547
(assert (sign "yield"))
; t=26.25s frame 630
(retract-fact sign "yield")
; t=43.08s frame 1034
(assert (sign "road works"))
; t=45.33s frame 1088
(assert (sign "danger"))
; t=45.38s frame 1089
(assert (sign "stop"))
; t=45.58s frame 1094
(assert (sign "ahead only"))
; t=45.92s frame 1102
(retract-fact sign "road works")
; t=48.29s frame 1159
(retract-fact sign "danger")
; t=48.29s frame 1159
(retract-fact sign "stop")
; t=49.50s frame 1188
(retract-fact sign "ahead only")
; t=74.12s frame 1779
(assert (sign "no overtaking"))
