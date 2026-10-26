; t=0.12s frame 3
(assert (sign "slippery road"))
; t=2.17s frame 52
(assert (sign "no entry"))
; t=3.12s frame 75
(retract-fact sign "slippery road")
; t=4.62s frame 111
(retract-fact sign "no entry")
; t=7.33s frame 176
(assert (traffic-light "red"))
; t=8.83s frame 212
(assert (sign "keep right"))
; t=15.29s frame 367
(retract-fact traffic-light "red")
; t=19.42s frame 466
(retract-fact sign "keep right")
; t=19.54s frame 469
(assert (traffic-light "red"))
; t=20.50s frame 492
(assert (sign "ahead only"))
; t=21.83s frame 524
(retract-fact traffic-light "red")
