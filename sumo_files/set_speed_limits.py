"""Writes the roads' speed limits into a SUMO network that CARLA ships for one of its towns.

CARLA 0.9.16's Co-Simulation/Sumo/examples/net/Town04.net.xml has every driving lane at netconvert's
default 50 km/h, so SUMO's cars drove the 90 km/h highway at 50. The town's OpenDRIVE has each road's
limit in mph (Town04: 55 and 65 on the highway, 30 and 35 in the town); they are written in km/h at the
values CARLA's signs show (the drive's speed score reads the signs): SIGN_KMH. A road inside a junction
has no limit of its own and takes the one of the road leading into it. Sidewalks and shoulders are left.

usage (with the CARLA server on the town):
    python sumo_files/set_speed_limits.py sumo_files/Town04/Town04.net.xml
"""
import re
import sys

import carla

# mph in the OpenDRIVE -> km/h on CARLA's signs
SIGN_KMH = {65: 90, 55: 90, 35: 60, 30: 50}


def road_limits(xodr):
    """{OpenDRIVE road id: km/h}."""
    limits, junction_links = {}, {}
    for rid, junc, body in re.findall(r'<road [^>]*id="(\d+)"[^>]*junction="(-?\d+)"[^>]*>(.*?)</road>', xodr, re.S):
        speeds = [float(v) * (1.609344 if u == 'mph' else 1.0)
                  for v, u in re.findall(r'<speed max="([0-9.]+)" unit="([^"]+)"', body)]
        if speeds:
            mph = round(max(speeds) / 1.609344)
            limits[int(rid)] = SIGN_KMH.get(mph, round(max(speeds)))
        else:
            pred = re.search(r'<predecessor elementType="road" elementId="(\d+)"', body)
            succ = re.search(r'<successor elementType="road" elementId="(\d+)"', body)
            junction_links[int(rid)] = [int(m.group(1)) for m in (pred, succ) if m]
    for rid, links in junction_links.items():
        known = [limits[r] for r in links if r in limits]
        if known:
            limits[rid] = known[0]
    return limits


def main(net_path):
    world = carla.Client('localhost', 2000).get_world()
    limits = road_limits(world.get_map().to_opendrive())
    text = open(net_path, encoding='utf-8').read()
    changed = []

    def lane(match):
        tag = match.group(0)
        edge = match.group(1)
        if edge.startswith(':') or 'type="sidewalk"' in tag or 'type="shoulder"' in tag or 'disallow="all"' in tag \
                or 'allow="pedestrian"' in tag:
            return tag
        try:
            road = abs(int(edge.split('.')[0]))
        except ValueError:
            return tag
        if road not in limits:
            return tag
        changed.append(road)
        return re.sub(r'speed="[0-9.]+"', 'speed="%.2f"' % (limits[road] / 3.6), tag)

    text = re.sub(r'<lane id="([^"]+)_\d+"[^>]*>', lane, text)
    open(net_path, 'w', encoding='utf-8', newline='\n').write(text)
    print('%d lanes on %d roads given their limits' % (len(changed), len(set(changed))))


if __name__ == '__main__':
    main(sys.argv[1])
