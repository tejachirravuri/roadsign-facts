; t=1.04s frame 25
(assert (road-type "autobahn"))
; t=4.83s frame 116
(assert (sign "slippery road"))
; t=7.50s frame 180
(assert (sign "no entry"))
; t=8.46s frame 203
(retract-fact sign "slippery road")
; t=9.96s frame 239
(retract-fact sign "no entry")
; t=12.67s frame 304
(assert (traffic-light "red"))
; t=14.17s frame 340
(assert (sign "keep right"))
; t=20.62s frame 495
(retract-fact traffic-light "red")
; t=24.75s frame 594
(retract-fact sign "keep right")
; t=24.88s frame 597
(assert (traffic-light "red"))
; t=25.83s frame 620
(assert (sign "ahead only"))
; t=27.17s frame 652
(retract-fact traffic-light "red")
; t=30.54s frame 733
(assert (sign "keep right"))
; t=33.96s frame 815
(retract-fact sign "ahead only")
; t=35.25s frame 846
(assert (sign "ahead only"))
; t=38.33s frame 920
(retract-fact sign "ahead only")
; t=38.88s frame 933
(assert (sign "ahead only"))
; t=45.58s frame 1094
(retract-fact sign "ahead only")
; t=45.92s frame 1102
(retract-fact sign "keep right")
; t=54.58s frame 1310
(assert (sign "ahead only"))
; t=56.62s frame 1359
(retract-fact sign "ahead only")
; t=57.33s frame 1376
(assert (sign "ahead only"))
; t=59.38s frame 1425
(retract-fact sign "ahead only")
; t=67.79s frame 1627
(assert (sign "ahead only"))
; t=70.21s frame 1685
(retract-fact sign "ahead only")
; t=75.29s frame 1807
(assert (sign "ahead only"))
; t=77.33s frame 1856
(retract-fact sign "ahead only")
; t=77.67s frame 1864
(assert (sign "ahead only"))
; t=87.33s frame 2096
(retract-fact sign "ahead only")
; t=88.79s frame 2131
(assert (sign "ahead only"))
; t=92.33s frame 2216
(retract-fact sign "ahead only")
; t=92.96s frame 2231
(assert (sign "ahead only"))
; t=100.92s frame 2422
(retract-fact sign "ahead only")
; t=108.21s frame 2597
(assert (speed-limit 60))
; t=112.00s frame 2688
(assert (sign "slippery road"))
; t=112.92s frame 2710
(assert (sign "road works"))
; t=114.92s frame 2758
(retract-fact sign "slippery road")
; t=115.96s frame 2783
(retract-fact sign "road works")
; t=116.54s frame 2797
(assert (sign "traffic signals"))
; t=117.88s frame 2829
(assert (sign "ahead only"))
; t=119.25s frame 2862
(retract-fact sign "traffic signals")
; t=119.92s frame 2878
(retract-fact sign "ahead only")
; t=120.29s frame 2887
(assert (sign "keep right"))
; t=121.62s frame 2919
(assert (traffic-light "green"))
; t=121.83s frame 2924
(assert (sign "yield"))
; t=123.50s frame 2964
(retract-fact sign "keep right")
; t=123.58s frame 2966
(retract-fact traffic-light "green")
; t=124.42s frame 2986
(assert (sign "keep right"))
; t=126.67s frame 3040
(retract-fact sign "keep right")
; t=127.54s frame 3061
(retract-fact sign "yield")
; t=142.67s frame 3424
(assert (sign "road works"))
; t=145.12s frame 3483
(assert (sign "danger"))
; t=146.46s frame 3515
(assert (sign "stop"))
; t=146.67s frame 3520
(assert (sign "ahead only"))
; t=147.17s frame 3532
(assert (sign "ahead or left"))
; t=147.21s frame 3533
(retract-fact sign "road works")
; t=149.29s frame 3583
(retract-fact sign "ahead or left")
; t=149.58s frame 3590
(retract-fact sign "danger")
; t=149.58s frame 3590
(retract-fact sign "stop")
; t=150.75s frame 3618
(retract-fact sign "ahead only")
; t=155.00s frame 3720
(assert (traffic-light "red"))
; t=156.54s frame 3757
(retract-fact traffic-light "red")
; t=159.25s frame 3822
(retract-fact speed-limit 60)
; t=159.25s frame 3822
(assert (speed-limit 80))
; t=174.38s frame 4185
(assert (sign "no overtaking"))
; t=177.79s frame 4267
(retract-fact sign "no overtaking")
