# Context-aware manual: driving simulator

A user study of an AI vehicle manual that teaches a car's features while you
drive, at calm moments, the way a game tutorial does. It runs on the
[CARLA](https://carla.org) simulator: you drive from the driver's seat with a
Logitech G25 wheel, and a second screen shows the car's dashboard, where the
manual's tips appear.

- `manual_control_driver.py`: the drive. The driver's-seat view, the G25,
  drive modes and regen, cruise control, adaptive cruise and an autopilot,
  and the user-test controls.
- `steering_wheel.py`: the G25 (axes, buttons, H-shifter as P/R/N/D) and its
  force feedback.
- `smart_manual_dashboard/`: the second-screen dashboard, the context-aware
  tips (`tips.py`), the drive log and driving score (`drive_log.py`) and the
  participant report (`report.py`).
- `sumo_traffic.py`, `sumo_files/`: traffic from [SUMO](https://eclipse.dev/sumo/)
  that drives like people round your car (below).

## Running it

CARLA 0.9.16 (Windows), with its Python client (the release ships a wheel
for Python 3.12 only) in an environment beside `pygame`, `numpy` and SUMO
(`pip install eclipse-sumo sumolib traci lxml`):

```bash
CarlaUE4.exe -windowed -ResX=1280 -ResY=720
```

If the drive judders while the HUD reads 60 fps, the camera images are
arriving late: the HUD counts the server's ticks, not the images. Close
anything else using the GPU; `-quality-level=Low` is the fallback.

```bash
python manual_control_driver.py --tm-port 8010
```

It loads Town04 (a small town inside a highway loop) unless `--map` names
another. `--participant P07` logs a user test to `study_data/P07/`, and
`python -m smart_manual_dashboard.report P07` writes the report. The script's
`--help` lists every key and option.

## Traffic

SUMO simulates the traffic on the whole map, about 60 cars on Town04
(`--traffic` sets how many enter an hour, 1500 by default; `--traffic 0` for
none). Its drivers follow, brake and change lanes by SUMO's Extended
Intelligent Driver Model, each a little above or below the limit, and your
car is mirrored into SUMO, so they react to you: they slow down behind you
and let you merge. Only the cars within 200 m of you exist in CARLA. SUMO
also runs the traffic lights. The bridge is CARLA's own co-simulation, and
the way it runs and the drivers' parameters follow
[Coupled CARLA](https://github.com/bazilinskyy/coupled-carla).

With traffic, CARLA runs in synchronous mode on a 50 Hz clock that keeps
real time, ticked by a thread of the drive; the window keeps 60 fps. The
autopilot steers once a tick, so this clock also steadies it: on the
asynchronous server at 20 frames a second it weaves (CARLA's Traffic Manager
corrects too late at low rates). The drive prints a line every 10 s saying
how the clock keeps up (`1.00x real time`). A drive that is killed rather
than closed leaves the server in synchronous mode with its traffic frozen;
the next drive puts it back.

## The G25

| Control | Does |
| --- | --- |
| Shifter, 1st / 3rd / 4th | P / D / R; anywhere else N |
| Red buttons, left to right | cruise control, adaptive cruise, autopilot |
| Silver panel, top / bottom | set speed +5 / −5 km/h |
| D-pad up / down | following gap shorter / longer |
| Paddles | drive mode down / up (Eco, Normal, Dynamic) |
| Wheel's top buttons | regen down / up |

An assist's red button switches it on, resumes it after braking, and switches
it off. On the keyboard, B starts the manual, P skips a tip (for testing) and
holding R stops it.
