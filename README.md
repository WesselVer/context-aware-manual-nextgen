<h1 align="center"><img src="docs/logo.svg" width="48" alt="" align="top">&nbsp;Context-aware manual <sup>next gen</sup></h1>

<p align="center">
  <b>A driving-simulator user study of an AI vehicle manual that teaches you the car while you drive.</b><br>
  Like a game tutorial: each feature is explained at a calm moment, on a second screen, and stays until you have tried it.
</p>

<p align="center">
  <img alt="CARLA 1.0" src="https://img.shields.io/badge/CARLA-1.0%20(UE%205.8)-0f172a">
  <img alt="Python 3.12" src="https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white">
  <img alt="SUMO traffic" src="https://img.shields.io/badge/traffic-SUMO-38bdf8">
  <img alt="Logitech G25" src="https://img.shields.io/badge/wheel-Logitech%20G25-64748b">
  <img alt="Windows" src="https://img.shields.io/badge/platform-Windows-94a3b8">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-22c55e"></a>
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="#running-a-user-test">Running a user test</a> ·
  <a href="#the-tips">The tips</a> ·
  <a href="#how-it-works">How it works</a> ·
  <a href="#the-g25">The G25</a> ·
  <a href="#traffic">Traffic</a> ·
  <a href="#data-and-the-driving-score">Data</a> ·
  <a href="#from-0916-to-10">From 0.9.16 to 1.0</a>
</p>

This is the study's simulator on **CARLA 1.0**, which runs on Unreal Engine 5.8: the same drive, manual, wheel,
dashboard, traffic and driving score as the earlier version of this project
(CARLA 0.9.16, Unreal Engine 4), on the same Town04, with Unreal Engine 5's lighting. The study's project started on
CARLA 0.10.0 (Unreal Engine 5, no Town04) and moved to 0.9.16 for Town04's highway; 1.0 has both.

The study asks **how context-aware personalisation influences the acceptance of an AI-powered vehicle manual**.
A participant drives an electric car they have never driven before in [CARLA](https://carla.org), from the
driver's seat, with a Logitech G25 wheel. A second screen is the car's dashboard. When the researcher starts the
manual, it watches the drive and introduces the car's features one by one (cruise control, adaptive cruise, the
autopilot, drive modes, one-pedal driving), each only when the moment is right: standing still, steady on a
straight, or on a quiet road, never at a junction, in busy traffic or in the middle of a manoeuvre. The drive ends
with a scored minute or two of free driving, and the questionnaires before and after run in MS Forms.

![The participant's view: Town04's highway from the driver's seat of the Lincoln on CARLA 1.0, with SUMO traffic ahead](docs/img/driver_view.jpg)

*Screen 1: the participant's view on Town04's highway on CARLA 1.0, from the driver's seat, with SUMO traffic ahead.
While driving, the door and interior mirrors show the road behind (this picture is the driver's camera alone).*

---

## Contents
- [What you get](#what-you-get) · [Screenshots](#screenshots) · [How it works](#how-it-works)
- [Quick start](#quick-start): [what you need](#what-you-need), [install](#install), [drive](#drive)
- [Running a user test](#running-a-user-test): [the protocol](#the-protocol), [the researcher's keys](#the-researchers-keys), [the tips](#the-tips)
- [The G25](#the-g25) · [Traffic](#traffic) · [Data and the driving score](#data-and-the-driving-score)
- [From 0.9.16 to 1.0](#from-0916-to-10) · [Known limits](#known-limits) · [Project layout](#project-layout) · [Credits and licences](#credits-and-licences)

## What you get

| | |
|---|---|
| **Driver's seat** | CARLA's `manual_control.py`, rebuilt for a study: a driver's-eye camera tuned per car (Lincoln MKZ by default), interior and door mirrors, a steering wheel that turns in the cabin, full screen on screen 1. |
| **Sound that doesn't stutter** | A sporty electric drive tone that grows with speed, load and drive mode, with road and wind noise, made and played by the drive itself so a late server can't interrupt it. It steps back when the dashboard chimes. |
| **Unreal Engine 5 look** | Lumen lighting and ray-traced shadows at Epic quality, through CARLA 1.0's `Cinematic` camera profile, with NVIDIA DLSS keeping the frame time down. |
| **A real car's features** | Drive modes (Eco, Normal, Dynamic), regenerative braking down to one-pedal driving, cruise control, adaptive cruise with a following gap, and an autopilot on CARLA's Traffic Manager that you can override with the pedals and wheel. |
| **Logitech G25** | Steering, pedals and the H-shifter as an automatic's P/R/N/D, with force feedback; the shifter's red buttons are cruise, adaptive cruise and autopilot. The keyboard works beside it. |
| **Second-screen dashboard** | A production-style dashboard in a browser window on screen 2: speed, gear, assists with a lane view of the car ahead, and the manual's tips with a drawing of the button to press. |
| **Context-aware manual** | 12 tips from the basics up, the same order for every driver. Each one waits for a safe moment and stays until the driver has done it; one already known is skipped. The dashboard says why it picked, or is waiting for, a moment. |
| **Traffic that reacts** | SUMO drives ~110 cars on Town04 with human-like car following and lane changes; the participant's car is in SUMO too, so traffic slows behind them and lets them merge. |
| **Driving score** | The drive is logged at 10 Hz, and the free drive at the end is scored on safety, lane keeping, speed, smoothness and use of the features, with an explainable report per participant and one CSV for all. |

## Screenshots

| A tip at a calm moment | Adaptive cruise, with the manual waiting |
|---|---|
| ![The dashboard with the cruise-control tip: a drawing of the shifter with the CC button, and why now](docs/img/dashboard_tip.jpg) | ![The dashboard with adaptive cruise on, following a car at 42 m, and the manual holding back the next tip because of traffic](docs/img/dashboard_acc.jpg) |
| *The first tip: on a quiet road the manual shows where CC is on the shifter. The grey lines say why it picked this moment.* | *Adaptive cruise follows the car ahead. Four cars are close by, so the next tip waits.* |

![An example driving report, with made-up numbers: driving score of the free drive and the guided part, with the rule behind each part](docs/img/driving_report.jpg)

*The driving report of a pilot participant (`python -m manual.report`): the score of the free drive beside the
guided part, every part with the rule behind it, and the driving metrics below.*

## How it works

![How it works: the G25 and the two screens, the drive, the context-aware manual, CARLA, SUMO and the drive log](docs/how_it_works.svg)

`drive.py` runs the car on the CARLA server and draws screen 1. Each frame it measures the context (speed, the
road's speed limit, a junction ahead, cars and people nearby, turning, braking) and passes it with the
car's state to the manual (`manual/tips.py`), which decides whether a tip is due and whether now is a good moment.
The dashboard on screen 2 is a web page (`manual/dashboard.html`) in an Edge or Chrome app window, fed by
server-sent events from the drive, so it needs nothing beyond Python's standard library. SUMO runs the traffic in
co-simulation, and the drive log (`manual/drive_log.py`) records what happens for the driving score.

The manual is Wizard-of-Oz in one sense: participants judge the explanation and its timing; the features
themselves are simulated (CARLA has no regen or cruise control, so the drive script builds them).

## Quick start

### What you need
- **Windows 11** with an NVIDIA RTX GPU (CARLA 1.0 runs at Epic quality with ray tracing, and the drive uses DLSS;
  developed on an RTX 5090). About 50 GB free for CARLA and its maps.
- **Two screens**: screen 1 for the road, screen 2 for the dashboard. One screen works too, with the dashboard in
  a window.
- **A Logitech G25** with its drivers installed (optional: without one, the keyboard drives the car).
- **Microsoft Edge or Google Chrome** for the dashboard window.

### Install
1. Download CARLA 1.0 for Windows from its [release page](https://github.com/carla-simulator/carla/releases/tag/1.0):
   `CARLA_1.0.zip` (14 GB) and the `AdditionalMaps_1.0.tar.gz` content pack (7 GB), which holds Town04. Unpack the
   zip, e.g. to `C:\CARLA\CARLA_1.0`, and install the pack into it:

   ```bash
   cd C:\CARLA\CARLA_1.0
   python Tools\carla_pack.py install AdditionalMaps_1.0.tar.gz --server .
   ```

2. Clone this repository and make a Python environment (CARLA 1.0 ships a client wheel for Python 3.10 to 3.15;
   3.12 is what this was built with):

   ```bash
   git clone https://github.com/WesselVer/context-aware-manual-nextgen.git
   cd context-aware-manual-nextgen
   py -3.12 -m venv .venv
   .venv\Scripts\activate
   pip install C:\CARLA\CARLA_1.0\PythonAPI\carla\dist\carla-1.0-cp312-cp312-win_amd64.whl
   pip install -r requirements.txt
   ```

   `eclipse-sumo` brings SUMO itself, so no separate SUMO install is needed.

### Drive
Start the server. It runs without a window of its own (the participant only sees the drive's window), and is
ready when port 2000 answers, about 20 s:

```bash
C:\CARLA\CARLA_1.0\CarlaUnreal.exe -RenderOffScreen -nosound
```

The first time, Windows Firewall asks whether CarlaUnreal may use the network: the drive talks to it on this PC
only, so Cancel is enough. Then the drive, from this folder:

```bash
python drive.py --tm-port 8010
```

It loads Town04 (once, if another map is up), puts the car on the highway, opens the dashboard full screen on
screen 2 and starts SUMO traffic. `--tm-port 8010` moves CARLA's Traffic Manager off port 8000, which Windows often
reserves. Esc ends the drive. Useful options (`python drive.py --help` lists all of them, and every key):

| Option | Does |
|---|---|
| `--participant P07` | log a user test to `study_data/P07/` |
| `--traffic 0` | no traffic (default: 2000 cars an hour entering the map) |
| `--windowed --res 1920x1080` | the road in a window instead of full screen |
| `--free-drive-seconds 120` | the longest the scored free drive runs |
| `--record` | also record the drive with CARLA's recorder |
| `--dlss 0` | the driver's view without DLSS (default: rendered at 67% and upscaled) |
| `--sound-volume 0.5` | how loud the car is, 0 for silent (default: 1.0) |
| `--no-wheel`, `--no-dashboard` | ignore the G25, or run without the dashboard |
| `--dashboard-layout full` | the older, fuller dashboard (J swaps them while driving) |

`python -m manual` shows the dashboard on its own with a demo drive, without CARLA, to check screen 2.

## Running a user test

### The protocol
1. **Before**: the participant fills in the pre-questionnaire (MS Forms): driving experience, which car features
   they know and how confident they are with them.
2. **Introduction**: the researcher explains the simulator and the wheel with the [A3 handout](#the-g25)
   ([`study/`](study/)), which also carries the questionnaires' QR codes.
3. **Getting used to the car**: `python drive.py --tm-port 8010 --participant P07`. The participant drives on the
   highway for a few minutes; the manual is off.
4. **Guided drive**: the researcher presses **B**. The manual starts and so does the log. The participant keeps
   driving; tips appear when the moment is right, and each stays until they have done it.
5. **Free drive**: the researcher presses **F**. The tips pause for up to `--free-drive-seconds` (120 s) while the
   participant drives as they like; then the drive is scored and the score shows on the dashboard as a last tip.
6. **After**: the post-questionnaire (MS Forms): the confidence and knowledge questions again, to measure what was
   learned, and the Van der Laan acceptance scale.
7. **Report**: `python -m manual.report P07` writes `study_data/P07/report.html` and updates
   `study_data/summary.csv`, one row per participant, to join with the questionnaires on the participant id.

### The researcher's keys

| Key | Does |
|---|---|
| **B** | start the manual (and, with `--participant`, the test and its log) |
| **F** | start the scored free drive; F again ends it early |
| **P** | skip the tip on screen (for testing) |
| hold **R** | stop the manual |
| hold **Z** (5 s) | reset for the next participant: closes the test, resets the assists, puts the car at a new place and starts a new log folder |
| **J** | swap the dashboard layout |
| **F1** | hide or show CARLA's debug HUD |
| **Esc** | end the drive |

### The tips
Every participant gets the same 12 tips, in this order. A tip comes up when its turn has come, some seconds after
the last one, and only at a safe moment; it is done when the driver does what it teaches.

| # | Tip | Teaches |
|---|---|---|
| 1 | Let cruise control hold your speed | cruise control on |
| 2 | Tap the brake to switch cruise control off | braking hands control back |
| 3 | Pick up your speed again after braking | resume |
| 4 | Change your cruise speed in 5 km/h steps | set speed +/- |
| 5 | Adaptive cruise keeps your distance for you | adaptive cruise on |
| 6 | Tune the speed adaptive cruise aims for | its set speed |
| 7 | Choose how close adaptive cruise follows | the following gap |
| 8 | Let the car drive itself for a while | autopilot on |
| 9 | Set how fast the autopilot drives | its speed |
| 10 | Speed past the autopilot with the accelerator | overriding it with the pedal |
| 11 | Wake the car up with Dynamic mode | drive modes |
| 12 | Drive with one pedal | maximum regen |

A good moment is standing still, steady on a straight, or a quiet road; a bad one is a junction ahead, several
cars or people close by, or a manoeuvre (turning, reversing, braking hard) in the last few seconds.
Highway ramps count as junctions. The rules and the tips' wording are in [`manual/tips.py`](manual/tips.py).

When a user tries a feature themselves before the car recommends it, it is assumed as 'known' and will be excluded from the manual for that session.

## The G25

| Control | Does |
|---|---|
| Shifter, 1st / 3rd / 4th | P / D / R; anywhere else N |
| Red buttons, left to right | cruise control, adaptive cruise, autopilot |
| Silver panel, top / bottom | set speed +5 / -5 km/h |
| D-pad up / down | following gap longer / shorter |
| Paddles | drive mode down / up (Eco, Normal, Dynamic) |
| Wheel's top buttons | regen down / up |
| Clutch | cuts the power (CARLA has no clutch) |

An assist's red button switches it on, resumes it after braking, and switches it off. Braking, leaving D, or
turning the wheel firmly against the autopilot hands the car back. The steering ratio is 13:1, close to a real
car's, with the wheel at 900 degrees in G HUB. Without a G25 the keyboard drives the car (WASD or the arrows; K for
the autopilot).

![The A3 controls handout: the steering wheel, the shifter with its red assist buttons, the pedals, and how to use cruise control, adaptive cruise and the autopilot](docs/img/controls_handout.jpg)

*The A3 handout participants keep beside the wheel ([`study/controls-handout-a3.pdf`](study/controls-handout-a3.pdf),
editable as [SVG](study/controls-handout-a3.svg); add your questionnaires' QR codes in the dashed boxes).*

## Traffic

SUMO simulates the traffic on the whole map: on Town04 nine in ten cars are through traffic on the highway and the
rest go anywhere, about 110 at once, some 30 within 200 m of you on the highway (`--traffic` sets how many enter an
hour, 2000 by default; `--traffic 0` for none). The roads' speed limits are written into SUMO's network from the
town's map ([`traffic/set_speed_limits.py`](traffic/set_speed_limits.py); CARLA ships it at 50 km/h everywhere).
Its drivers follow, brake and change lanes by SUMO's Extended Intelligent Driver Model, each a little above or below
the limit, and your car is mirrored into SUMO, so they react to you. Only the cars within 200 m of you exist in
CARLA, drawn from CARLA 1.0's cars, a van and a truck ([`traffic/cars.add.xml`](traffic/cars.add.xml)). SUMO also
runs the traffic lights. The bridge is CARLA 0.9.16's co-simulation (1.0 ships none; it runs unchanged), and the way
it runs and the drivers' parameters follow [Coupled CARLA](https://github.com/bazilinskyy/coupled-carla).

With traffic, CARLA runs in synchronous mode on a 40 Hz clock that keeps real time, ticked by a thread of the
drive; the window keeps 60 fps. The autopilot steers once a tick, so this clock also steadies it. The drive prints
a line every 10 s saying how the clock keeps up (`1.00x real time`). A drive that is killed rather than closed
leaves the server in synchronous mode with its traffic frozen; the next drive puts it back.

## Data and the driving score

With `--participant P07`, `study_data/P07/` gets:

| File | Holds |
|---|---|
| `drive-<time>.csv` | 10 times a second: speed, speed limit, lane position, the car ahead, acceleration, steering, pedals, assists |
| `events-<time>.csv` | phases, tips shown and done, features used, assists handed back, collisions and lane crossings |
| `drive.json` | the metrics of the guided and the free drive, and the score, with what each means |
| `report.html` | the explainable report (`python -m manual.report P07`; `--all` for everyone) |

`study_data/summary.csv` has one row per participant. The score has five parts of 0 to 100, each a plain rule over
CARLA's measurements, and the total is their mean:

| Part | Rule |
|---|---|
| Safety | 100, less 40 per collision and 15 per close call (time to collision under 1.5 s) each minute, and up to 50 for tailgating |
| Lane keeping | 100 at an SDLP of 20 cm or less, 0 at 50 cm |
| Speed | the share of the moving time at or under the limit (+5 km/h) |
| Smoothness | 100, less 25 per harsh brake each minute |
| Features | the share of the features the tips showed that were used again |

`study_data/` is in `.gitignore`: participant data stays on the lab PC.

## From 0.9.16 to 1.0

| CARLA 0.9.16 (Unreal Engine 4) | CARLA 1.0 (Unreal Engine 5.8) |
|---|---|
| ![The driver's view on CARLA 0.9.16](docs/img/driver_view_0916.jpg) | ![The driver's view on CARLA 1.0](docs/img/driver_view.jpg) |

Town04's road network is the same file in both, byte for byte, so the start, the speed limits and SUMO's network
carry over. What changed, each measured on the Lincoln (2026-11-17) and set to drive like the 0.9.16 version:

| | 0.9.16 | 1.0 | So |
|---|---|---|---|
| Cars | `vehicle.lincoln.mkz_2020`, ... | `vehicle.lincoln.mkz`, ... (0.10.0's) | names and driver's eyes from 0.10.0, seat 6 cm higher, 84° view; mirrors placed anew |
| Camera look | gamma 2.2, +1 stop exposure | no gamma or exposure setting; camera profiles | the `Cinematic` profile (the default looks grey and grainy) |
| Coasting, throttle released | 3.5 m/s² | 0.5 m/s² | regen back to 0.10.0's levels: 1.3, 2.1, 3.8 m/s² |
| Jolt at the end of a stop | near 2 g, so tyre stiffness was capped | none: braking stays smooth to a standstill | no cap (Chaos has no such setting) |
| Yaw at 50 km/h per steer | 8.2 °/s at 0.03 | 7.3 °/s at 0.03 | steering ratio 13:1 instead of 14:1 |
| 0-50 / 0-100 km/h, full throttle | 2.9 / 7.5 s | 2.1 / 8.6 s | left as is |
| A synchronous tick | ~8 ms with the cameras and traffic | at least 15 ms, ~21 ms with them | server `-RenderOffScreen`, DLSS on the driver's view, traffic clock 40 Hz |

## Known limits
- **A short stall about once a minute** on CARLA 1.0: the server freezes for 0.4-1 s every 60 s. What is known
  (2026-11-17, RTX 5090): it happens on Town04 even with every map layer unloaded and no client at all, weaker on
  Town03 and not on Town10HD, nor on CARLA 0.10.0 or 0.9.16, and not with `-nullrhi`. In it the server uses no CPU
  and the GPU idles: Unreal's RHI threads wait inside NVIDIA's Direct3D 12 driver (in `ExecuteCommandLists`,
  command-list resets, texture commits), and the game thread waits for them. Not garbage collection (its interval
  changes nothing), not the sky light's capture, the street or traffic lights, or Windows' power throttling; a
  visible server window helps an idle server but not the drive. Unreal's console variables could not be set on
  the shipping build to test more. Not solved; worth reporting to CARLA with these findings.
- **The autopilot in town can wait for good** behind a SUMO car at a junction, which waits too, probably for the
  copy of your car in SUMO. Seen once, with the autopilot on in town; not looked into yet.
- **Port 8000** is reserved by Windows on many PCs, hence `--tm-port 8010`.
- **Traffic on Town04 only**: the SUMO network in `traffic/Town04/` is the only one shipped. Other maps (`--map`)
  drive with `--traffic 0`.

## Project layout

```
drive.py                 the drive: driver's seat, the car's features, the user-test keys
manual/                  the context-aware manual
  tips.py                  the 12 tips and when each may show
  dashboard.html           screen 2, served by __init__.py
  drive_log.py             the drive log and the driving score
  report.py                the per-participant report and summary.csv
hardware/
  steering_wheel.py        the G25: axes, buttons, H-shifter, force feedback
  cabin_wheel.py           the steering wheel that turns in the cabin
traffic/
  sumo_traffic.py          SUMO traffic round the car, on a 40 Hz clock
  sumo_integration/        CARLA 0.9.16's SUMO co-simulation bridge
  Town04/, cars.add.xml    the SUMO network and the drivers' models
study/                   the controls handout for participants (A3, SVG and PDF)
docs/                    the images in this README
```

The history of the project is in this repository's commits: it started on CARLA 0.10.0, moved to 0.9.16, and came to
1.0 here. The tuning
comments in the code say which version a value was measured on.

## Credits and licences
The code in this repository is released under the [MIT License](LICENSE). `drive.py` started from CARLA's
`manual_control.py` (MIT, © Computer Vision Center), and `traffic/sumo_integration/` is CARLA's co-simulation
bridge (MIT, © CVC). The traffic set-up follows [Coupled CARLA](https://github.com/bazilinskyy/coupled-carla)
by Pavlo Bazilinskyy. [CARLA](https://carla.org) (MIT; its assets CC-BY) and
[Eclipse SUMO](https://eclipse.dev/sumo/) (EPL-2.0) are installed separately. The dashboard's Barlow fonts are
under the SIL Open Font License ([`manual/fonts/OFL.txt`](manual/fonts/OFL.txt)).
