"""Traffic from SUMO (eclipse.dev/sumo): cars that drive like people round the drive's car.

SUMO simulates the traffic on the whole map: each driver follows, brakes and
changes lanes by SUMO's driver models (traffic/cars.add.xml), and keeps to the
speed limit give or take a tenth. The drive's car is mirrored into SUMO, so the
traffic sees it: cars behind it slow down for it, cars let it merge.

The two simulators run on one clock. A thread here ticks CARLA in synchronous
mode every STEP seconds of real time, and each tick: SUMO takes a step; the
SUMO cars within RADIUS m of the drive's car are placed in CARLA (the rest only
exist in SUMO, which keeps the server's frame time down); the traffic lights
take SUMO's state; CARLA ticks; and the drive's car's pose goes back to SUMO.
The window, wheel and dashboard keep their own 60 frames a second.

CARLA's Traffic Manager (the autopilot of the drive's car) lives in this
process, so it ticks with the world, in step with it: a fixed time step,
instead of whatever time passed since the last frame.

The bridge (traffic/sumo_integration) is CARLA 0.9.16's Co-Simulation/Sumo
(CARLA 1.0 ships none; this one runs unchanged on it, and Town04's road network,
so its SUMO network, is the same in both); the
way it is run (level of detail, one batch of poses per tick) and the drivers'
parameters follow Coupled CARLA (github.com/bazilinskyy/coupled-carla), both MIT.

Needs SUMO for Python: pip install eclipse-sumo sumolib traci lxml.
"""

import logging
import math
import random
import os
import subprocess
import sys
import threading
import time

import carla

HERE = os.path.dirname(os.path.abspath(__file__))
SUMO_DIR = HERE
# The SUMO network of each map CARLA ships one for.
NETS = {'Town04': os.path.join(SUMO_DIR, 'Town04', 'Town04.net.xml')}
CAR_TYPES = os.path.join(SUMO_DIR, 'cars.add.xml')
# Seconds of simulated time per tick, for CARLA and SUMO. The autopilot (the
# Traffic Manager) steers once a tick, and the fewer ticks, the more it weaves:
# on Town04's highway at 90 km/h its yaw wobbled 1.3 deg/s at 20 Hz, 0.6 at
# 50 Hz and 0.2 at the ~160 Hz of an idle server (2026-11-16, CARLA 0.9.16).
# On CARLA 1.0 a synchronous tick takes at least 15 ms, even of an empty world,
# and with the drive's cameras (DLSS on, server -RenderOffScreen) and the
# traffic about 21 ms, so 50 Hz fell to 0.9x real time; 40 Hz keeps it. The
# autopilot weaves no more at 40 than at 50 Hz there (measured 2026-11-17).
STEP = 0.025
# How often the clock prints how it keeps up.
REPORT_SECONDS = 10.0
# The traffic: this share is through traffic on the highway (highway_routes),
# on its roads of at least HIGHWAY_KMH; the rest random trips.
THROUGH_SHARE = 0.9
HIGHWAY_KMH = 80.0
# SUMO cars exist in CARLA within this distance (m) of the drive's car, and
# go again beyond it plus LOD_MARGIN.
RADIUS = 200.0
LOD_MARGIN = 30.0
# How often (ticks) every SUMO car is checked for near and far: half a second,
# in which a car at 90 km/h goes 12.5 m, within the margin.
LOD_TICKS = 25
# SUMO runs this long before the drive starts, so the roads are already full.
WARM_UP_SECONDS = 240.0
# Before the drive's car is put down (at the start, or for the next participant),
# SUMO cars are taken off round the spot, so none is in it or runs into the car
# standing there: any within CLEAR_RADIUS m, and those driving its way from up to
# CLEAR_BEHIND m behind it to CLEAR_RADIUS m ahead, across CLEAR_SIDE m of road
# (the carriageway, not the other one). At 100 km/h a car takes 9 s to cover
# CLEAR_BEHIND, by when SUMO has the drive's car and the traffic brakes for it.
CLEAR_RADIUS = 30.0
CLEAR_BEHIND = 250.0
CLEAR_SIDE = 15.0
# Collisions in SUMO are logged, not "resolved" by teleporting the cars (which in
# CARLA made one vanish); a car stuck for 120 s is taken off.
# A driver waiting at a give-way merge 10 s pushes in (SUMO's default, 180 s, left
# the cloverleaf's ramps queued; no collisions in SUMO either way). A lane change
# takes LANE_CHANGE_SECONDS, sideways bit by bit: without SUMO's sublane model
# (CARLA's bridge runs it, for cyclists sharing lanes; there are none here), which
# took 6-7 ms of a 20 ms tick with ~130 cars on Town04.
LANE_CHANGE_SECONDS = 3.0
SUMO_ARGS = ['--lanechange.duration', str(LANE_CHANGE_SECONDS),
             '--collision.action', 'warn', '--collision.mingap-factor', '0',
             '--time-to-teleport', '120', '--time-to-impatience', '10', '--ignore-route-errors', 'true',
             '--no-step-log', 'true', '--no-warnings', 'true']


def _sumo_home():
    if not os.environ.get('SUMO_HOME'):
        import sumo  # the eclipse-sumo package
        os.environ['SUMO_HOME'] = sumo.SUMO_HOME
    return os.environ['SUMO_HOME']


def _heading(shape, at_end):
    (x0, y0), (x1, y1) = (shape[-2], shape[-1]) if at_end else (shape[0], shape[1])
    return math.atan2(y1 - y0, x1 - x0)


def highway_routes(net, rng, count):
    """count routes that follow the highway: from a random stretch of a main
    carriageway (two lanes or more, at least HIGHWAY_KMH), on along it, at each
    junction the way with the most lanes that bends least, for 2-6 km."""
    import sumolib
    sn = sumolib.net.readNet(net)

    def lanes(edge):
        return [l for l in edge.getLanes() if l.allows('passenger')]

    main = [e for e in sn.getEdges() if len(lanes(e)) >= 2 and
            max(l.getSpeed() for l in lanes(e)) * 3.6 >= HIGHWAY_KMH]
    main_ids = set(e.getID() for e in main)
    routes = []
    while len(routes) < count:
        edge = rng.choice(main)
        path, length, goal = [edge], 0.0, rng.uniform(2000.0, 6000.0)
        while length < goal:
            # Only ways on that have the right of way: through traffic does not
            # give way (road 23 joins the highway at a give-way merge, and through
            # traffic routed over it queued there).
            nexts = [to for to, connections in edge.getOutgoing().items()
                     if to.getID() in main_ids and to not in path[-3:]
                     and any(c.getFromLane().allows('passenger') and c.getState() == 'M' for c in connections)]
            if not nexts:
                break
            # The most lanes, then the least bend: by the bend alone, at road 42
            # every route in one direction took road 23, a two-lane connector
            # over to the other carriageway, and that direction's highway was
            # left nearly empty.
            out = _heading(edge.getShape(), True)
            edge = min(nexts, key=lambda e: (-len(lanes(e)),
                                             abs((_heading(e.getShape(), False) - out + math.pi)
                                                 % (2 * math.pi) - math.pi)))
            path.append(edge)
            length += edge.getLength()
        if length >= 1000.0:
            routes.append(' '.join(e.getID() for e in path))
    return routes


def write_config(net, work, cars_per_hour, seed=42, duration=4 * 3600):
    """Car traffic at cars_per_hour, and a .sumocfg for it, in the folder work;
    returns the .sumocfg's path.

    Most cars are through traffic on the highway (highway_routes). Random trips
    over the whole map made many cars turn round through Town04's cloverleaf,
    and its give-way merges queued the highway down to a 37 km/h average; the
    rest, THROUGH_SHARE off, are such trips, so the ramps and the town are not
    empty."""
    home = _sumo_home()
    os.makedirs(work, exist_ok=True)
    rng = random.Random(seed)
    through = os.path.join(work, 'through.rou.xml')
    period = 3600.0 / (cars_per_hour * THROUGH_SHARE)
    routes = highway_routes(net, rng, 200)
    with open(through, 'w') as f:
        f.write('<routes>\n')
        t = 0.0
        n = 0
        while t < duration:
            f.write('  <vehicle id="hw%d" type="cars" depart="%.2f" departLane="best" departSpeed="max">'
                    '<route edges="%s"/></vehicle>\n' % (n, t, rng.choice(routes)))
            n += 1
            t += rng.expovariate(1.0 / period)
        f.write('</routes>\n')
    trips = os.path.join(work, 'cars.trips.xml')
    subprocess.check_call(
        [sys.executable, os.path.join(home, 'tools', 'randomTrips.py'), '-n', net, '-o', trips,
         '-b', '0', '-e', str(int(duration)), '-p', '%.3f' % (3600.0 / (cars_per_hour * (1 - THROUGH_SHARE))),
         '--seed', str(seed), '--vclass', 'passenger', '--prefix', 'car', '--min-distance', '300',
         '--trip-attributes', 'type="cars" departLane="best" departSpeed="max"'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=work)  # it also writes routes.rou.xml here
    cfg = os.path.join(work, 'traffic.sumocfg')
    with open(cfg, 'w') as f:
        f.write('<configuration>\n  <input>\n    <net-file value="%s"/>\n    <route-files value="%s,%s"/>\n'
                '    <additional-files value="%s"/>\n  </input>\n'
                '  <random_number><seed value="%d"/></random_number>\n</configuration>\n'
                % (net, through, trips, CAR_TYPES, seed))
    return cfg


class SumoTraffic(object):
    """SUMO's traffic in CARLA round the car hero() returns, on a clock of its own."""

    def __init__(self, client, traffic_manager, hero, map_name, cars_per_hour, work, pump=None):
        _sumo_home()
        sys.path.insert(0, SUMO_DIR)
        from sumo_integration.bridge_helper import BridgeHelper
        from sumo_integration.constants import INVALID_ACTOR_ID
        from sumo_integration.sumo_simulation import SumoSimulation
        self._bridge, self._invalid = BridgeHelper, INVALID_ACTOR_ID
        net = NETS.get(map_name)
        if net is None:
            raise ValueError('no SUMO network for %s (there is one for %s)' % (map_name, ', '.join(NETS)))
        self._client = client
        self._world = client.get_world()
        self._tm = traffic_manager
        self._hero = hero
        self.cars_per_hour = cars_per_hour
        print('SUMO traffic: %d cars an hour on %s ...' % (cars_per_hour, map_name))
        cfg = write_config(net, work, cars_per_hour)
        self.sumo = SumoSimulation(cfg, STEP, extra_args=SUMO_ARGS, lateral_resolution=None)
        BridgeHelper.blueprint_library = self._world.get_blueprint_library()
        BridgeHelper.offset = self.sumo.get_net_offset()
        import traci
        # Ahead of the drive, so there is traffic from the start: a second at a
        # time inside SUMO, and between them pump() (the drive's window answers
        # Windows, which otherwise calls it not responding and may close it).
        for second in range(1, int(WARM_UP_SECONDS) + 1):
            traci.simulationStep(float(second))
            if pump is not None:
                pump()
        self._traci = traci
        self._subscribed = set()   # SUMO ids with a subscription of any kind
        self.laps, self._lap_at = {}, 0.0   # seconds spent in each part of the ticks
        self._live = set(traci.vehicle.getIDList())
        for actor_id in self._live:
            self._watch_from_afar(actor_id)
        # CARLA's traffic lights: those SUMO also has follow SUMO's programmes,
        # so the traffic and the lights agree.
        self._lights = {}
        for landmark in self._world.get_map().get_all_landmarks_of_type('1000001'):
            if landmark.id:
                light = self._world.get_traffic_light(landmark)
                if light is not None:
                    self._lights[landmark.id] = light
        self._common_lights = self.sumo.traffic_light_ids & set(self._lights)
        for light in self._lights.values():
            light.freeze(True)
        self._in_carla = {}       # SUMO id -> CARLA id
        self._twin = None         # (CARLA id of the drive's car, its SUMO id)
        self._tick_no = 0
        self.frame_ms = 0.0       # how long the last tick took
        self.world_ms = 0.0       # of which CARLA's own tick
        self.twin_ok = False      # whether the drive's car is in SUMO
        self.behind_s = 0.0       # how far the clock has fallen behind real time
        self._running = False
        self._thread = None
        self._lock = threading.Lock()   # a tick, or clear_around, at a time
        self._original = self._world.get_settings()

    # -- the clock -------------------------------------------------------------

    def start(self):
        settings = self._world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = STEP
        self._world.apply_settings(settings)
        self._tm.set_synchronous_mode(True)
        # The clock thread shares Python with the drive's window; by default Python
        # switches threads every 5 ms, and a tick has a dozen calls that wait on it.
        sys.setswitchinterval(0.0005)
        self._running = True
        self._thread = threading.Thread(target=self._run, name='sumo-traffic', daemon=True)
        self._thread.start()
        print('SUMO traffic: %d cars on the network, those within %d m of the car in CARLA'
              % (len(self._live), RADIUS))

    def _run(self):
        due = time.perf_counter()
        report, ticks, worked, slowest, in_world = due + REPORT_SECONDS, 0, 0.0, 0.0, 0.0
        while self._running:
            began = time.perf_counter()
            try:
                with self._lock:
                    self._tick()
                self._lap('your car')
            except Exception:  # noqa: BLE001 - the traffic must not end the drive
                logging.exception('SUMO traffic: tick failed')
            now = time.perf_counter()
            self.frame_ms = 1000.0 * (now - began)
            ticks, worked, slowest = ticks + 1, worked + self.frame_ms, max(slowest, self.frame_ms)
            in_world += self.world_ms
            if now >= report:
                # How the clock keeps up: simulated seconds per real one, and
                # how much of a tick is CARLA's own (the server's frame).
                print('SUMO traffic: %.2fx real time, tick %.1f ms (CARLA %.1f, slowest %.0f), %d cars in CARLA, '
                      'your car in SUMO: %s'
                      % (ticks * STEP / (now - report + REPORT_SECONDS), worked / ticks, in_world / ticks,
                         slowest, len(self._in_carla),
                         self._twin_report()), flush=True)
                print('    ms a tick: ' + ', '.join('%s %.1f' % (k, 1000.0 * v / ticks) for k, v in self.laps.items()),
                      flush=True)
                self.laps = {}
                report, ticks, worked, slowest, in_world = now + REPORT_SECONDS, 0, 0.0, 0.0, 0.0
            due += STEP
            if now < due:
                time.sleep(due - now)
                self.behind_s = 0.0
            else:
                # Slower than real time: carry on from now rather than rushing to catch up.
                self.behind_s = now - due
                if self.behind_s > 0.25:
                    due = now

    def _tick(self):
        bridge, sumo = self._bridge, self.sumo
        lap = self._lap
        lap(None)
        sumo.tick()
        lap('sumo')
        for actor_id in sumo.spawned_actors:
            if self._twin is None or actor_id != self._twin[1]:
                self._watch_from_afar(actor_id)
                self._live.add(actor_id)
        for actor_id in sumo.destroyed_actors:
            self._live.discard(actor_id)
            self._subscribed.discard(actor_id)
            carla_id = self._in_carla.pop(actor_id, None)
            if carla_id is not None:
                self._client.apply_batch([carla.command.DestroyActor(carla_id)])
        if self._twin is not None and self._twin[1] in sumo.destroyed_actors:
            self._twin = None  # SUMO took it off (teleported); it gets a new one below

        lap('arrivals')
        hero = self._hero()
        try:
            here = hero.get_location() if hero is not None else None
        except RuntimeError:
            here = None

        # Level of detail: every LOD_TICKS ticks, and for cars just in, spawn what
        # is near the drive's car (in one batch) and remove what has gone far.
        self._tick_no += 1
        check = self._live if self._tick_no % LOD_TICKS == 0 else (sumo.spawned_actors & self._live)
        poses, spawns, gone = {}, [], []
        position = self._traci.constants.VAR_POSITION
        offset_x, offset_y = bridge.offset
        for actor_id in list(check):
            if here is None:
                break
            if actor_id in self._in_carla:
                try:
                    d = bridge.get_carla_transform(sumo.get_actor(actor_id).transform,
                                                   carla.Vector3D()).location.distance(here)
                except (KeyError, TypeError):
                    continue
                if d > RADIUS + LOD_MARGIN:
                    gone.append(carla.command.DestroyActor(self._in_carla.pop(actor_id)))
                    self._watch_from_afar(actor_id)
                continue
            # From afar SUMO sends only the position (of the front bumper, which
            # is near enough here).
            xy = (self._traci.vehicle.getSubscriptionResults(actor_id) or {}).get(position)
            if xy is None or math.hypot(xy[0] - offset_x - here.x, -(xy[1] - offset_y) - here.y) > RADIUS:
                continue
            self._traci.vehicle.unsubscribe(actor_id)   # SUMO adds to a subscription: drop it first
            sumo.subscribe(actor_id)                    # everything, at once, without a step
            self._subscribed.add(actor_id)
            try:
                actor = sumo.get_actor(actor_id)
            except (KeyError, TypeError):
                self._watch_from_afar(actor_id)
                continue
            transform = bridge.get_carla_transform(actor.transform, actor.extent)
            poses[actor_id] = (actor, transform)
            blueprint = bridge.get_carla_blueprint(actor, False)
            if blueprint is None:
                self._watch_from_afar(actor_id)
                continue
            spawn = carla.Transform(transform.location + carla.Location(z=25.0), transform.rotation)
            spawns.append((actor_id, carla.command.SpawnActor(blueprint, spawn).then(
                carla.command.SetSimulatePhysics(carla.command.FutureActor, False))))
        if spawns:
            responses = self._client.apply_batch_sync([command for _, command in spawns], False)
            for (actor_id, _), response in zip(spawns, responses):
                if not response.error:
                    self._in_carla[actor_id] = response.actor_id
                else:
                    self._watch_from_afar(actor_id)
        if gone:
            self._client.apply_batch(gone)

        lap('near/far')
        # Every SUMO car in CARLA to SUMO's pose, in one batch.
        batch = []
        for actor_id, carla_id in self._in_carla.items():
            if actor_id in poses:
                transform = poses[actor_id][1]
            else:
                try:
                    actor = sumo.get_actor(actor_id)
                except (KeyError, TypeError):
                    continue
                transform = bridge.get_carla_transform(actor.transform, actor.extent)
            batch.append(carla.command.ApplyTransform(carla_id, transform))
        if batch:
            self._client.apply_batch(batch)

        lap('poses')
        for landmark_id in self._common_lights:
            state = bridge.get_carla_traffic_light_state(sumo.get_traffic_light_state(landmark_id))
            if state is not None and self._lights[landmark_id].state != state:
                self._lights[landmark_id].set_state(state)

        lap('lights')
        world_began = time.perf_counter()
        self._world.tick()
        self.world_ms = 1000.0 * (time.perf_counter() - world_began)

        lap('carla')
        # The drive's car into SUMO, so the traffic sees it.
        if hero is None or here is None:
            return
        try:
            if self._twin is not None and self._twin[0] != hero.id:
                self._remove_twin()
            if self._twin is None:
                type_id = bridge.get_sumo_vtype(hero)
                sumo_id = sumo.spawn_actor(type_id) if type_id else self._invalid
                if sumo_id == self._invalid:
                    return
                self._twin = (hero.id, sumo_id)
                sumo.subscribe(sumo_id)
            pose = bridge.get_sumo_transform(hero.get_transform(), hero.bounding_box.extent)
            self._traci.vehicle.moveToXY(self._twin[1], '', 0, pose.location.x, pose.location.y,
                                         angle=pose.rotation.yaw, keepRoute=2)
            self.twin_ok = True
        except (RuntimeError, self._traci.exceptions.TraCIException) as error:
            # Until SUMO has put it on the road, a tick or two after it is added.
            self.twin_ok = False
            logging.debug('SUMO traffic: the drive\'s car: %s', error)

    def clear_around(self, transform):
        """Takes the SUMO cars off that are in, or coming at, the place transform
        (CARLA's) where the drive's car is about to be put down (CLEAR_RADIUS);
        returns how many. Safe while the clock runs: it waits for the tick."""
        with self._lock:
            bridge, traci = self._bridge, self._traci
            offset_x, offset_y = bridge.offset
            yaw = math.radians(transform.rotation.yaw)
            fx, fy = math.cos(yaw), math.sin(yaw)
            here = transform.location
            twin = self._twin[1] if self._twin is not None else None
            removed = 0
            for actor_id in list(self._live):
                if actor_id == twin:
                    continue
                try:
                    xy = (traci.vehicle.getSubscriptionResults(actor_id) or {}).get(traci.constants.VAR_POSITION)
                    if xy is None:
                        xy = traci.vehicle.getPosition(actor_id)
                    dx, dy = xy[0] - offset_x - here.x, -(xy[1] - offset_y) - here.y
                    along, side = dx * fx + dy * fy, -dx * fy + dy * fx
                    if math.hypot(dx, dy) > CLEAR_RADIUS:
                        if not (-CLEAR_BEHIND < along < CLEAR_RADIUS and abs(side) < CLEAR_SIDE):
                            continue
                        # SUMO's angle: clockwise from north; CARLA's yaw is it less 90.
                        heading = traci.vehicle.getAngle(actor_id) - 90.0
                        if abs((heading - transform.rotation.yaw + 180.0) % 360.0 - 180.0) > 60.0:
                            continue   # the other way, on the other carriageway
                    traci.vehicle.remove(actor_id)
                except self._traci.exceptions.TraCIException:
                    continue
                removed += 1
                self._live.discard(actor_id)
                self._subscribed.discard(actor_id)
                carla_id = self._in_carla.pop(actor_id, None)
                if carla_id is not None:
                    self._client.apply_batch_sync([carla.command.DestroyActor(carla_id)], False)
            return removed

    def _twin_report(self):
        if not self.twin_ok:
            return 'no'
        try:
            return '%.0f km/h' % (3.6 * self._traci.vehicle.getSpeed(self._twin[1]))
        except (TypeError, self._traci.exceptions.TraCIException):
            return 'no'

    def _lap(self, name):
        """Adds the time since the last lap to name's total (None starts a tick)."""
        now = time.perf_counter()
        if name is not None:
            self.laps[name] = self.laps.get(name, 0.0) + now - self._lap_at
        self._lap_at = now

    def _watch_from_afar(self, actor_id):
        """Only the car's position each step: SUMO sends, and Python reads, all
        of a car's details only for the few near the drive's car (Coupled
        CARLA's level of detail); for every car it cost the clock ~10 ms a tick."""
        try:
            if actor_id in self._subscribed:
                self._traci.vehicle.unsubscribe(actor_id)   # SUMO adds to a subscription
            self._traci.vehicle.subscribe(actor_id, [self._traci.constants.VAR_POSITION])
            self._subscribed.add(actor_id)
        except self._traci.exceptions.TraCIException:
            self._subscribed.discard(actor_id)

    def _remove_twin(self):
        try:
            self.sumo.destroy_actor(self._twin[1])
        except self._traci.exceptions.TraCIException:
            pass
        self._twin = None

    def cars_in_carla(self):
        return len(self._in_carla)

    # -- the end ---------------------------------------------------------------

    def close(self):
        """Stops the clock, takes the traffic out of CARLA, ends SUMO, and gives
        the world back in asynchronous mode."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        try:
            self._client.apply_batch_sync([carla.command.DestroyActor(i) for i in self._in_carla.values()], False)
            for light in self._lights.values():
                light.freeze(False)
            self._tm.set_synchronous_mode(False)
            self._world.apply_settings(self._original)
        except RuntimeError as error:
            logging.warning('SUMO traffic: closing CARLA: %s', error)
        self._in_carla = {}
        try:
            self.sumo.close()
        except Exception:  # noqa: BLE001
            pass
