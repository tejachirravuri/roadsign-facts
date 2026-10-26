; t=2.52s frame 63
(assert (road-type "road"))
; t=3.40s frame 85
(assert (speed-limit 70))
; t=6.04s frame 151
(assert (sign "yield"))
; t=7.28s frame 182
(retract-fact speed-limit 70)
; t=7.28s frame 182
(assert (speed-limit 50))
; t=8.40s frame 210
(retract-fact sign "yield")
