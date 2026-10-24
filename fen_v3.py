"""FEN Piura V3 · optimización cuántico-híbrida en hardware IBM real.

Cambios frente a V2:
  * La QPU decide: búsqueda por vecindarios (zonas) donde QAOA en IBM Quantum
    escoge la combinación de rutas; el MILP clásico queda como referencia.
  * Todas las zonas de una ronda se envían en UN solo job (batch de circuitos).
  * Supresión de errores (dynamical decoupling + twirling) y fidelidad estimada
    del circuito ISA a partir de las calibraciones del backend.
  * Distancias por carretera reales (OSRM / OpenStreetMap) con respaldo Haversine.
  * Lluvia real (Open-Meteo): pronóstico de hoy o un día del Niño Costero 2017.
  * Confiabilidad estocástica de cada ruta (Monte Carlo de tiempos de viaje).

NO apto para despacho real: albergues, demandas y ventanas son ilustrativos.
"""
from __future__ import annotations

import itertools
import json
import math
import time
import zlib
from collections import Counter
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Optional

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp, minimize
from scipy.sparse import lil_matrix

SEED = 20261024
DEPOT = ("D0", -5.1945, -80.6328)
BASE_RAW = [
    ("P1", "Los Algarrobos", "Catacaos", -5.2670, -80.6760, 4, "06:30", "08:00", 3, False),
    ("P2", "Nueva Esperanza", "Cura Mori", -5.3230, -80.6640, 2, "07:00", "09:30", 3, True),
    ("P3", "El Porvenir", "El Tallán", -5.4100, -80.6830, 1, "07:00", "10:30", 2, True),
    ("P4", "Santa Rosa", "La Arena", -5.3440, -80.7110, 3, "08:00", "12:00", 2, False),
    ("P5", "Las Palmeras", "La Unión", -5.3990, -80.7420, 3, "08:00", "13:00", 2, False),
    ("P6", "San Martín", "Vice", -5.4180, -80.7790, 2, "09:00", "15:00", 1, False),
    ("P7", "Los Ceibos", "Bernal", -5.4600, -80.7430, 1, "07:00", "07:45", 3, False),
    ("P8", "Puerto Nuevo", "Sechura", -5.5580, -80.8210, 3, "10:00", "16:00", 1, False),
]
HTTP_TIMEOUT = 25


def minutes(t: str) -> int:
    h, m = map(int, t.split(":"))
    return 60 * h + m


def clock(t: float) -> str:
    if not math.isfinite(t):
        return "--:--"
    t = int(round(t))
    return f"{t // 60:02d}:{t % 60:02d}"


# ----------------------------------------------------------------------------
# Modelo de datos
# ----------------------------------------------------------------------------
@dataclass(frozen=True)
class Stop:
    id: str; name: str; region: str; lat: float; lon: float; demand: int
    start: int; end: int; priority: int; flooded: bool = False; source: str = "ficticio"


@dataclass(frozen=True)
class Vehicle:
    id: str; name: str; capacity: int; speed_kmh: float; offroad: bool


@dataclass(frozen=True)
class TripSlot:
    id: str; vehicle: str; index: int; start: int; end: int


@dataclass
class Scenario:
    name: str
    stops: dict
    vehicles: dict
    slots: list
    detours: dict                       # {(a,b) ordenado: multiplicador}; inf = tramo cerrado
    max_stops: int = 3
    start: int = 360
    end: int = 1080
    route_factor: float = 1.3          # solo para el respaldo Haversine
    priority_weight: float = 1.0
    wait_weight: float = 0.05
    road_km: Optional[dict] = None      # {(a,b): km por carretera (OSRM)}
    distance_source: str = "Haversine x1.3 (respaldo)"
    weather: dict = field(default_factory=dict)       # {punto: {lluvia_mm, mult, sigma, ...}}
    weather_source: str = "sin clima"


@dataclass(frozen=True)
class Route:
    id: str; slot: str; vehicle: str; points: tuple; cost: float
    drive: float; wait: float; return_at: float; load: int; reliability: float = 1.0


def make_scenario(n: int = 8, seed: int = SEED) -> Scenario:
    """8 = caso heredado de V1; 10/25/50 añaden puntos sintéticos alrededor de los 8."""
    if n not in (8, 10, 25, 50):
        raise ValueError("Tamaños previstos: 8, 10, 25 o 50")
    stops = {}
    for ident, name, region, lat, lon, d, a, b, p, flood in BASE_RAW:
        stops[ident] = Stop(ident, name, region, lat, lon, d, minutes(a), minutes(b), p, flood)
    rng = np.random.default_rng(seed)
    for k in range(9, n + 1):
        _, _, reg, lat, lon, *_ = BASE_RAW[(k - 9) % 8]
        st = Stop(f"S{k:02d}", f"Punto sintético {k}", reg,
                  lat + float(rng.uniform(-0.013, 0.013)), lon + float(rng.uniform(-0.013, 0.013)),
                  int(rng.choice([1, 1, 2])), minutes("06:00"), minutes("18:00"),
                  int(rng.integers(1, 4)), False, "sintético")
        stops[st.id] = st
    base = [Vehicle("V1", "Camión 6 t", 10, 35, False), Vehicle("V2", "Camioneta 4x4", 4, 50, True),
            Vehicle("V3", "Camión 4x4", 7, 40, True)]
    if n == 8:
        v, trips = base, 1
    elif n == 10:
        v, trips = base + [Vehicle("V4", "Camión 4x4 B", 8, 42, True)], 1
    elif n == 25:
        v, trips = base + [Vehicle("V4", "Camión 4x4 B", 8, 42, True), Vehicle("V5", "Camión 6 t B", 10, 38, False)], 2
    else:
        v = base + [Vehicle("V4", "Camión 4x4 B", 8, 42, True), Vehicle("V5", "Camión 6 t B", 10, 38, False),
                    Vehicle("V6", "Camioneta 4x4 B", 5, 50, True), Vehicle("V7", "Camión 4x4 C", 8, 40, True),
                    Vehicle("V8", "Camión 6 t C", 10, 38, False)]
        trips = 3
    slots = [TripSlot(f"{veh.id}:T{j + 1}", veh.id, j, 360 + j * int(720 / trips), 360 + (j + 1) * int(720 / trips))
             for veh in v for j in range(trips)]
    detours = {tuple(sorted(k)): val for k, val in {("P5", "P6"): 3.0, ("D0", "P8"): 1.4}.items()}
    return Scenario(f"Bajo Piura · {n} puntos", stops, {x.id: x for x in v}, slots, detours)


def coords(s: Scenario, p: str) -> tuple:
    return (DEPOT[1], DEPOT[2]) if p == "D0" else (s.stops[p].lat, s.stops[p].lon)


def node_ids(s: Scenario) -> list:
    return ["D0"] + list(s.stops)


# ----------------------------------------------------------------------------
# Datos externos: OpenStreetMap (OSRM) y clima (Open-Meteo)
# ----------------------------------------------------------------------------
def _get_json(url: str, params: Optional[dict] = None) -> dict:
    import requests
    r = requests.get(url, params=params, timeout=HTTP_TIMEOUT,
                     headers={"User-Agent": "FEN-Piura-hackathon/3.0"})
    r.raise_for_status()
    return r.json()


def load_osrm_distances(s: Scenario, server: str = "https://router.project-osrm.org") -> Scenario:
    """Matriz de km por carretera real (red OpenStreetMap) con el servicio /table de OSRM.
    Si el servicio falla, se mantiene Haversine x1.3 y se informa la fuente."""
    ids = node_ids(s)
    coord = ";".join(f"{coords(s, i)[1]:.6f},{coords(s, i)[0]:.6f}" for i in ids)
    try:
        data = _get_json(f"{server}/table/v1/driving/{coord}", {"annotations": "distance,duration"})
        if data.get("code") != "Ok":
            raise RuntimeError(data.get("message", data.get("code")))
        dist = data["distances"]
        road = {}
        for a, i in enumerate(ids):
            for b, j in enumerate(ids):
                if i != j:
                    val = dist[a][b]
                    road[(i, j)] = (val / 1000.0) if val is not None else float("inf")
        s.road_km = road
        s.distance_source = "OSRM / OpenStreetMap (km por carretera)"
    except Exception as exc:  # noqa: BLE001 - se informa al usuario
        s.road_km = None
        s.distance_source = f"Haversine x{s.route_factor} (OSRM no disponible: {type(exc).__name__})"
    return s


def osrm_geometry(s: Scenario, seq: list, server: str = "https://router.project-osrm.org") -> Optional[list]:
    """Trazo real por calles para dibujar una ruta [(lat, lon), ...]; None si falla."""
    coord = ";".join(f"{coords(s, i)[1]:.6f},{coords(s, i)[0]:.6f}" for i in seq)
    try:
        data = _get_json(f"{server}/route/v1/driving/{coord}", {"overview": "full", "geometries": "geojson"})
        return [(lat, lon) for lon, lat in data["routes"][0]["geometry"]["coordinates"]]
    except Exception:  # noqa: BLE001
        return None


def _rain_to_effects(rain_day_mm: float, rain_max_mmh: float, prob: float, flood_mm: float) -> dict:
    """Supuestos (documentados, calibrables con el equipo):
    - lentitud: +50 % del tiempo de viaje con 50 mm/día o más (lineal hasta ese tope);
    - incertidumbre: sigma log-normal 0.10 en seco hasta 0.35 con lluvia intensa;
    - acceso inundado (solo 4x4) si la lluvia del día supera flood_mm."""
    level = min(max(rain_day_mm, 0.0) / 50.0, 1.0)
    return dict(lluvia_mm=round(rain_day_mm, 1), max_mm_h=round(rain_max_mmh, 1), prob=prob,
                mult=1.0 + 0.5 * level, sigma=0.10 + 0.25 * level, inundado=rain_day_mm >= flood_mm)


def load_weather(s: Scenario, mode: str = "fen2017", start_date: str = "2017-03-15",
                 end_date: str = "2017-03-31", flood_mm: float = 30.0) -> Scenario:
    """Lluvia por punto con Open-Meteo (sin API key).
    mode='pronostico': pronóstico horario de hoy (hora de Lima).
    mode='fen2017'   : reanálisis histórico; toma el día más lluvioso del rango (Niño Costero 2017).
    Solo cuenta la lluvia entre 06:00 y 18:00 (jornada de reparto)."""
    ids = node_ids(s)
    lat = ",".join(f"{coords(s, i)[0]:.4f}" for i in ids)
    lon = ",".join(f"{coords(s, i)[1]:.4f}" for i in ids)
    try:
        if mode == "pronostico":
            data = _get_json("https://api.open-meteo.com/v1/forecast",
                             dict(latitude=lat, longitude=lon, timezone="America/Lima", forecast_days=1,
                                  hourly="precipitation,precipitation_probability"))
        elif mode == "fen2017":
            data = _get_json("https://archive-api.open-meteo.com/v1/archive",
                             dict(latitude=lat, longitude=lon, timezone="America/Lima",
                                  start_date=start_date, end_date=end_date, hourly="precipitation"))
        else:
            raise ValueError("mode debe ser 'pronostico' o 'fen2017'")
        data = data if isinstance(data, list) else [data]
        times = np.array(data[0]["hourly"]["time"])
        days = np.array([t[:10] for t in times])
        hours = np.array([int(t[11:13]) for t in times])
        rain = np.array([[v or 0.0 for v in d["hourly"]["precipitation"]] for d in data])  # (puntos, horas)
        work = (hours >= 6) & (hours < 18)
        uniq = sorted(set(days))
        if mode == "fen2017":   # día con más lluvia media en la jornada
            day = max(uniq, key=lambda dd: rain[:, (days == dd) & work].sum(axis=1).mean())
        else:
            day = uniq[0]
        mask = (days == day) & work
        weather = {}
        for k, i in enumerate(ids):
            if mode == "pronostico":
                pr = [v or 0 for v, m in zip(data[k]["hourly"]["precipitation_probability"], mask) if m]
                prob = float(max(pr)) if pr else 0.0
            else:
                prob = 100.0 if rain[k, mask].sum() > 0.5 else 0.0
            weather[i] = _rain_to_effects(float(rain[k, mask].sum()), float(rain[k, mask].max(initial=0)), prob, flood_mm)
        s.weather = weather
        s.weather_source = f"Open-Meteo {'pronóstico' if mode == 'pronostico' else 'reanálisis'} · {day}"
        for i, w in weather.items():   # la lluvia puede volver un albergue solo-4x4
            if i != "D0" and w["inundado"] and not s.stops[i].flooded:
                s.stops[i] = replace(s.stops[i], flooded=True)
    except Exception as exc:  # noqa: BLE001
        s.weather = {}
        s.weather_source = f"sin clima (Open-Meteo no disponible: {type(exc).__name__})"
    return s


# ----------------------------------------------------------------------------
# Tiempos, simulación de rutas y confiabilidad estocástica
# ----------------------------------------------------------------------------
def km(s: Scenario, a: str, b: str) -> float:
    if a == b:
        return 0.0
    if s.road_km is not None and (a, b) in s.road_km:
        return s.road_km[(a, b)]
    lat1, lon1 = map(math.radians, coords(s, a))
    lat2, lon2 = map(math.radians, coords(s, b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * math.asin(min(1, math.sqrt(h))) * s.route_factor


def weather_mult(s: Scenario, a: str, b: str) -> float:
    if not s.weather:
        return 1.0
    return max(s.weather.get(a, {}).get("mult", 1.0), s.weather.get(b, {}).get("mult", 1.0))


def leg_sigma(s: Scenario, a: str, b: str) -> float:
    if not s.weather:
        return 0.10
    return max(s.weather.get(a, {}).get("sigma", 0.10), s.weather.get(b, {}).get("sigma", 0.10))


def travel(s: Scenario, a: str, b: str, veh: str) -> float:
    return km(s, a, b) * 60 / s.vehicles[veh].speed_kmh * s.detours.get(tuple(sorted((a, b))), 1.0) * weather_mult(s, a, b)


def close_link(s: Scenario, a: str, b: str) -> Scenario:
    """Evento: tramo intransitable (puente caído, huaico). Copia el escenario."""
    out = replace(s, detours=dict(s.detours), stops=dict(s.stops))
    out.detours[tuple(sorted((a, b)))] = float("inf")
    return out


def simulate(s: Scenario, slot: TripSlot, points) -> Optional[Route]:
    """Ruta factible (tiempos esperados) o None. Ventana dura = inicio de atención <= cierre."""
    if len(points) > s.max_stops or len(set(points)) != len(points):
        return None
    v = s.vehicles[slot.vehicle]
    load = sum(s.stops[p].demand for p in points)
    if load > v.capacity or any(s.stops[p].flooded and not v.offroad for p in points):
        return None
    t = float(slot.start); dr = wait = prio = 0.0; prev = "D0"
    for p in points:
        st = s.stops[p]; dt = travel(s, prev, p, v.id)
        if not math.isfinite(dt):
            return None
        t += dt; dr += dt; wait += max(0.0, st.start - t); t = max(t, st.start)
        if t > st.end + 1e-7:
            return None
        prio += s.priority_weight * (st.priority - 1) * max(0, t - s.start) / 60
        t += 15 + 5 * st.demand; prev = p
    dt = travel(s, prev, "D0", v.id) if points else 0.0
    if not math.isfinite(dt):
        return None
    t += dt; dr += dt
    if t > slot.end + 1e-7:
        return None
    return Route(f'{slot.id}|{"-".join(points)}', slot.id, slot.vehicle, tuple(points),
                 dr + s.wait_weight * wait + prio, dr, wait, t, load)


def reliability(s: Scenario, slot: TripSlot, points, draws: int = 200, seed: int = SEED) -> float:
    """P(cumplir todas las ventanas y volver a tiempo) con tiempos de viaje log-normales
    de media igual al tiempo esperado y dispersión creciente con la lluvia."""
    rng = np.random.default_rng(seed + zlib.crc32((slot.id + "|" + "-".join(points)).encode()))
    v = slot.vehicle
    t = np.full(draws, float(slot.start)); ok = np.ones(draws, bool); prev = "D0"
    for p in list(points) + ["D0"]:
        mu, sg = travel(s, prev, p, v), leg_sigma(s, prev, p)
        t = t + mu * rng.lognormal(-sg * sg / 2, sg, draws)
        if p == "D0":
            ok &= t <= slot.end + 1e-7
        else:
            st = s.stops[p]; t = np.maximum(t, st.start); ok &= t <= st.end + 1e-7
            t = t + 15 + 5 * st.demand
        prev = p
    return float(ok.mean())


def route_pool(s: Scenario, seed: int = SEED, min_reliability: float = 0.0,
               risk_weight: float = 0.0, draws: int = 200) -> list:
    """Rutas candidatas factibles. Con risk_weight>0 se suma (1-confiabilidad)*risk_weight
    al costo y se descartan rutas con confiabilidad < min_reliability (restricción de azar)."""
    ids = list(s.stops); out = {}
    rng = np.random.default_rng(seed)
    for ix, slot in enumerate(s.slots):
        eligible = [p for p in ids if not (s.stops[p].flooded and not s.vehicles[slot.vehicle].offroad)]
        if not eligible:
            continue
        if len(ids) <= 10:
            focused = eligible
        else:
            anchors = list(s.stops)
            center = anchors[(ix * 7 + ix // len(s.vehicles)) % len(anchors)]
            nearest = sorted(eligible, key=lambda p: km(s, center, p))[:11]
            extra = list(rng.choice(eligible, size=min(4, len(eligible)), replace=False))
            focused = list(dict.fromkeys(nearest + extra))
        cands = [(p,) for p in eligible]
        for size in range(2, s.max_stops + 1):
            for group in itertools.combinations(focused, size):
                cands.extend(itertools.permutations(group))
        for pts in cands:
            r = simulate(s, slot, pts)
            if r is None:
                continue
            if risk_weight > 0 or min_reliability > 0:
                rel = reliability(s, slot, pts, draws, seed)
                if rel < min_reliability:
                    continue
                r = replace(r, reliability=rel, cost=r.cost + risk_weight * (1 - rel))
            out[r.id] = r
    return list(out.values())


def unreachable(s: Scenario, pool: list) -> list:
    covered = {p for r in pool for p in r.points}
    return [p for p in s.stops if p not in covered]


# ----------------------------------------------------------------------------
# Validación y MILP de referencia
# ----------------------------------------------------------------------------
def validate(s: Scenario, chosen: list, required=None) -> dict:
    required = set(s.stops) if required is None else set(required)
    served = list(itertools.chain.from_iterable(r.points for r in chosen))
    slots = [r.slot for r in chosen]
    slot_by_id = {sl.id: sl for sl in s.slots}
    tests = {
        "cobertura_exacta": len(served) == len(required) and set(served) == required,
        "sin_repetidos": len(served) == len(set(served)),
        "un_viaje_por_slot": len(slots) == len(set(slots)),
        "capacidad_ventanas_acceso_retorno": all(simulate(s, slot_by_id[r.slot], r.points) is not None for r in chosen),
    }
    return {"ok": all(tests.values()), "checks": tests, "atendidos": len(set(served)), "solicitudes": len(required)}


def solve_master(s: Scenario, routes: list, time_limit: float = 30.0, required=None,
                 cost_of=None) -> dict:
    """Set partitioning: cada punto exactamente una vez, cada slot <= 1 ruta.
    cost_of(route) permite otro objetivo (p. ej. 0 = solo factibilidad, o mínimo cambio)."""
    t0 = time.perf_counter()
    required = set(s.stops) if required is None else set(required)
    rr = [r for r in routes if set(r.points) <= required]
    stop_ids = sorted(required); slot_ids = sorted({r.slot for r in rr})
    if not rr or any(not any(p in r.points for r in rr) for p in stop_ids):
        return dict(status="infeasible_pool", ok=False, optimal=False, obj=None, routes=[], elapsed=time.perf_counter() - t0)
    A = lil_matrix((len(stop_ids) + len(slot_ids), len(rr)))
    si = {p: i for i, p in enumerate(stop_ids)}; sl = {x: len(stop_ids) + j for j, x in enumerate(slot_ids)}
    for j, r in enumerate(rr):
        for p in r.points:
            A[si[p], j] = 1
        A[sl[r.slot], j] = 1
    lb = np.r_[np.ones(len(stop_ids)), np.zeros(len(slot_ids))]
    c = np.asarray([(cost_of(r) if cost_of else r.cost) for r in rr], float)
    out = milp(c, integrality=np.ones(len(rr), int), bounds=Bounds(0, 1),
               constraints=LinearConstraint(A.tocsr(), lb, np.ones(len(lb))),
               options={"time_limit": time_limit, "mip_rel_gap": 0.001})
    chosen = [r for j, r in enumerate(rr) if out.x is not None and out.x[j] > 0.5]
    checks = validate(s, chosen, required)
    return dict(status=out.message, optimal=out.status == 0, ok=checks["ok"],
                obj=sum(r.cost for r in chosen) if checks["ok"] else None,
                elapsed=time.perf_counter() - t0, pool_size=len(rr), routes=chosen, validation=checks)


def plan_cost(plan: list) -> float:
    return float(sum(r.cost for r in plan))


def summary(s: Scenario, plan: list) -> dict:
    hi = [x for x in s.stops.values() if x.priority == 3]
    return dict(rutas=len(plan), costo=round(plan_cost(plan), 2),
                km=round(sum(km(s, a, b) for r in plan for a, b in zip(("D0",) + r.points, r.points + ("D0",))), 1),
                minutos_viaje=round(sum(r.drive for r in plan), 1),
                confiabilidad_min=round(min((r.reliability for r in plan), default=1.0), 3),
                prioridad_alta_atendida=f"{sum(s.stops[p].priority == 3 for r in plan for p in r.points)}/{len(hi)}")


# ----------------------------------------------------------------------------
# Vecindarios (zonas) para la QPU
# ----------------------------------------------------------------------------
def _neighborhood(pool: list, slots: tuple, req: set, incumbent: list, max_variables: int,
                  max_combos: int = 20000):
    """Opciones = rutas de los slots de la zona cuyas combinaciones (una ruta o ninguna por slot)
    cubren exactamente los puntos req. El incumbente siempre está incluido (garantiza factibilidad)."""
    per_slot = []
    for sid in slots:
        d = {}
        for r in pool:
            if r.slot == sid and set(r.points) <= req:
                d.setdefault(frozenset(r.points), []).append(r)
        per_slot.append(d)
    combos = []

    def rec(k, remaining, chosen):
        if len(combos) >= max_combos:
            return
        if k == len(slots):
            if not remaining:
                combos.append(tuple(chosen))
            return
        rec(k + 1, remaining, chosen)                       # este slot queda libre
        for key, routes in per_slot[k].items():
            if key <= remaining:
                for r in routes:
                    rec(k + 1, remaining - key, chosen + [r])

    rec(0, frozenset(req), [])
    inc_ids = {r.id for r in incumbent}
    options = list(incumbent)
    for combo in sorted(combos, key=lambda cb: sum(r.cost for r in cb)):
        have = {z.id for z in options}
        fresh = [r for r in combo if r.id not in have]
        if fresh and len(options) + len(fresh) <= max_variables:
            options.extend(fresh)
    alternatives = sum(1 for cb in combos if {r.id for r in cb} != inc_ids)
    return options, alternatives


def select_neighborhoods(s: Scenario, plan: list, pool: list, max_variables: int = 12,
                         max_neighborhoods: int = 4, slots_per_zone: int = 3, exclude=()) -> list:
    """Zonas disjuntas de `slots_per_zone` viajes (al menos uno usado) con alternativas reales.
    Cada zona es un QUBO de <= max_variables qubits; todas van en un solo job.
    `exclude`: zonas ya probadas sin mejora (para explorar otras en la siguiente ronda)."""
    used = {r.slot: r for r in plan}
    all_slots = [sl.id for sl in s.slots]
    k = min(slots_per_zone, len(all_slots))
    excl = {tuple(sorted(z)) for z in exclude}
    cands = []
    for combo in itertools.combinations(all_slots, k):
        if tuple(sorted(combo)) in excl or not any(x in used for x in combo):
            continue
        inc = [used[x] for x in combo if x in used]
        req = set(itertools.chain.from_iterable(r.points for r in inc))
        # zonas geográficamente coherentes: descarta mezclas muy dispersas en instancias grandes
        options, alt = _neighborhood(pool, combo, req, inc, max_variables)
        if alt == 0 or len(options) < 3:
            continue
        cands.append(dict(slots=combo, required=req, incumbent=inc, routes=options, alternatives=alt,
                          score=(min(alt, 50), len(req), plan_cost(inc))))
    cands.sort(key=lambda z: z["score"], reverse=True)
    chosen, taken = [], set()
    for z in cands:
        if taken.isdisjoint(z["slots"]):
            chosen.append(z); taken.update(z["slots"])
        if len(chosen) >= max_neighborhoods:
            break
    for i, z in enumerate(chosen):
        z["name"] = f"Zona {i + 1} · " + " + ".join(z["slots"])
    return chosen


# ----------------------------------------------------------------------------
# QUBO, QAOA (entrenamiento de ángulos) y circuito Qiskit
# ----------------------------------------------------------------------------
def make_qubo(neigh: dict, penalty_factor: float = 1.2) -> dict:
    """E(x) = sum c_r x_r + P sum_i (cobertura_i - 1)^2 + P sum_{mismo slot} x_r x_t.
    P = penalty_factor * costo del incumbente: cualquier cadena inválida queda por encima
    del óptimo factible (cuya existencia garantiza el incumbente), sin aplastar los costos."""
    routes = neigh["routes"]; req = neigh["required"]; n = len(routes)
    costs = np.array([r.cost for r in routes], float)
    pen = penalty_factor * max(1.0, plan_cost(neigh["incumbent"]))
    lin = costs.copy(); pair = np.zeros((n, n)); const = pen * len(req)
    for p in req:
        members = [i for i, r in enumerate(routes) if p in r.points]
        for i in members:
            lin[i] -= pen
        for i, j in itertools.combinations(members, 2):
            pair[i, j] += 2 * pen
    for i, j in itertools.combinations(range(n), 2):
        if routes[i].slot == routes[j].slot:
            pair[i, j] += pen
    scale = max(1.0, float(np.max(np.abs(lin))), float(np.max(np.abs(pair))))
    return dict(name=neigh.get("name", "zona"), routes=routes, required=req, n=n, c=const / scale,
                linear=lin / scale, pairs=pair / scale, scale=scale, penalty=pen)


def all_bits(n: int) -> np.ndarray:
    return ((np.arange(2 ** n, dtype=np.int64)[:, None] >> np.arange(n, dtype=np.int64)) & 1).astype(np.uint8)


def qubo_energy(q: dict, bits) -> np.ndarray:
    B = np.atleast_2d(bits).astype(float)
    return q["c"] + B @ q["linear"] + np.einsum("bi,ij,bj->b", B, q["pairs"], B)


def qubo_decode(q: dict, bitvec) -> dict:
    picked = [r for i, r in enumerate(q["routes"]) if bitvec[i] == 1]
    cnt = Counter(p for r in picked for p in r.points)
    ok = (all(cnt[p] == 1 for p in q["required"]) and sum(cnt.values()) == len(q["required"])
          and len({r.slot for r in picked}) == len(picked))
    return {"ok": ok, "routes": picked, "obj": sum(r.cost for r in picked) if ok else None}


def exact_subproblem(q: dict) -> float:
    vals = [d["obj"] for d in (qubo_decode(q, b) for b in all_bits(q["n"])) if d["ok"]]
    return min(vals)


def _qaoa_probs(energy, params, n, p):
    state = np.full(2 ** n, 1 / np.sqrt(2 ** n), dtype=complex)
    idx = np.arange(2 ** n)
    for layer in range(p):
        g, b = params[2 * layer: 2 * layer + 2]
        state = state * np.exp(-1j * g * energy)
        cc, ss = np.cos(b), -1j * np.sin(b)
        for bit in range(n):
            zero = idx[(idx & (1 << bit)) == 0]; one = zero + (1 << bit)
            va, vb = state[zero].copy(), state[one].copy()
            state[zero] = cc * va + ss * vb; state[one] = ss * va + cc * vb
    return np.abs(state) ** 2


def _cvar(probs, energy, alpha):
    order = np.argsort(energy); p = probs[order]; e = energy[order]
    cum = np.cumsum(p); k = min(int(np.searchsorted(cum, alpha)) + 1, len(p))
    taken = p[:k].copy(); taken[-1] -= max(0.0, cum[k - 1] - alpha)
    return float(taken @ e[:k] / alpha)


def train_angles(q: dict, p: int = 1, alpha: float = 0.25, restarts: int = 4, seed: int = SEED,
                 maxiter: int = 120) -> dict:
    """Optimiza (gamma, beta) con CVaR evaluando el estado exacto en CPU (<= 14 qubits).
    No es una corrida de prueba: solo fija los parámetros que luego muestrea la QPU,
    para no gastar minutos de hardware en el bucle variacional."""
    if q["n"] > 14:
        raise ValueError("Zona demasiado grande: usa max_variables <= 14")
    E = qubo_energy(q, all_bits(q["n"]))
    rng = np.random.default_rng(seed); best = None
    for _ in range(restarts):
        x0 = rng.uniform(0, np.pi, 2 * p)
        res = minimize(lambda a: _cvar(_qaoa_probs(E, a, q["n"], p), E, alpha), x0, method="COBYLA",
                       options={"maxiter": maxiter, "rhobeg": 0.5})
        if best is None or res.fun < best.fun:
            best = res
    return dict(params=[float(v) for v in best.x], p=p, cvar=float(best.fun))


def qaoa_circuit(q: dict, params, p: int = 1):
    """Circuito QAOA del QUBO (x = (1 - z)/2): RZ + RZZ para el costo, RX como mezclador."""
    from qiskit import QuantumCircuit
    n = q["n"]; qc = QuantumCircuit(n, name=q["name"])
    qc.h(range(n))
    P = q["pairs"]
    h = -q["linear"] / 2 - P.sum(axis=1) / 4 - P.sum(axis=0) / 4
    for layer in range(p):
        gamma, beta = params[2 * layer: 2 * layer + 2]
        for j in range(n):
            if abs(h[j]) > 1e-12:
                qc.rz(2 * gamma * h[j], j)
        for i, j in zip(*np.nonzero(np.triu(P, k=1))):
            qc.rzz(2 * gamma * P[i, j] / 4, int(i), int(j))
        for j in range(n):
            qc.rx(2 * beta, j)
    qc.measure_all()
    return qc


# ----------------------------------------------------------------------------
# IBM Quantum: conexión, ejecución por lotes y métricas de hardware
# ----------------------------------------------------------------------------
def connect_ibm(token: str, instance: Optional[str] = None, backend_name: Optional[str] = None,
                min_qubits: int = 20):
    from qiskit_ibm_runtime import QiskitRuntimeService
    service = QiskitRuntimeService(channel="ibm_quantum_platform", token=token, instance=instance or None)
    backend = (service.backend(backend_name) if backend_name
               else service.least_busy(operational=True, simulator=False, min_num_qubits=min_qubits))
    return service, backend


def two_qubit_gates(isa) -> int:
    return sum(1 for ins in isa.data if ins.operation.num_qubits == 2 and ins.operation.name != "barrier")


def estimated_fidelity(isa, backend) -> Optional[float]:
    """Probabilidad estimada de una ejecución sin errores (producto de 1 - error de cada
    compuerta y medición según la calibración actual del backend)."""
    try:
        target = backend.target
    except Exception:  # noqa: BLE001
        return None
    f = 1.0
    for ins in isa.data:
        name = ins.operation.name
        if name in ("barrier", "delay"):
            continue
        qargs = tuple(isa.find_bit(qb).index for qb in ins.qubits)
        try:
            err = target[name][qargs].error
        except Exception:  # noqa: BLE001
            err = None
        if err:
            f *= max(0.0, 1.0 - err)
    return f


def run_on_qpu(backend, circuits: list, shots: int = 4000, label: str = "", dd: bool = True,
               twirling: bool = True, opt_level: int = 3, seed: int = SEED) -> dict:
    """Transpila a ISA (circuitos nativos del equipo) y envía TODAS las zonas en un solo job."""
    from qiskit.transpiler import generate_preset_pass_manager
    from qiskit_ibm_runtime import SamplerV2 as Sampler
    pm = generate_preset_pass_manager(optimization_level=opt_level, backend=backend, seed_transpiler=seed)
    isa = [pm.run(c) for c in circuits]
    sampler = Sampler(mode=backend)
    sampler.options.default_shots = shots
    if dd:
        sampler.options.dynamical_decoupling.enable = True
        sampler.options.dynamical_decoupling.sequence_type = "XpXm"
    if twirling:
        sampler.options.twirling.enable_gates = True
        sampler.options.twirling.num_randomizations = "auto"
    t0 = time.time()
    job = sampler.run(isa)
    job_id = job.job_id()
    print(f"[{label}] job enviado a {backend.name}: {job_id} · {len(isa)} circuito(s) · esperando…")
    result = job.result()
    wall = time.time() - t0
    try:
        usage = job.usage()
    except Exception:  # noqa: BLE001
        usage = None
    counts = [r.data.meas.get_counts() for r in result]
    circ_info = [dict(qubits=c.num_qubits, prof_logica=c.depth(), prof_isa=i.depth(), puertas_2q=two_qubit_gates(i),
                      fidelidad_estimada=estimated_fidelity(i, backend)) for c, i in zip(circuits, isa)]
    print(f"[{label}] listo en {wall:.0f} s (cola + ejecución) · uso QPU: {usage} s")
    return dict(job_id=job_id, backend=backend.name, shots=shots, wall_s=round(wall, 1), qpu_s=usage,
                counts=counts, isa=isa, circuits=circ_info, label=label)


def analyze_counts(q: dict, counts: dict) -> dict:
    """Decodifica cada cadena medida (qubit 0 a la derecha) y elige la mejor combinación válida."""
    total = sum(counts.values()); valid = 0; best = None; opt = exact_subproblem(q); at_opt = 0
    for bits, ct in counts.items():
        x = np.array([int(ch) for ch in bits.replace(" ", "")[::-1]], dtype=int)
        d = qubo_decode(q, x)
        if d["ok"]:
            valid += ct
            if abs(d["obj"] - opt) < 1e-9:
                at_opt += ct
            if best is None or d["obj"] < best["obj"]:
                best = d
    return dict(pct_valid=100 * valid / total, pct_optimo=100 * at_opt / total, best=best, optimo_zona=opt,
                brecha_zona_pct=None if best is None else 100 * (best["obj"] - opt) / max(abs(opt), 1e-9))


def uniform_baseline(q: dict, shots: int, seed: int = SEED) -> dict:
    """Comparador justo: mismas cadenas posibles, mismo número de muestras, al azar."""
    rng = np.random.default_rng(seed)
    bits = rng.integers(0, 2, size=(shots, q["n"]))
    dec = [qubo_decode(q, b) for b in bits]
    ok = [d for d in dec if d["ok"]]
    opt = exact_subproblem(q)
    return dict(pct_valid=100 * len(ok) / shots,
                pct_optimo=100 * sum(abs(d["obj"] - opt) < 1e-9 for d in ok) / shots,
                best=min((d["obj"] for d in ok), default=None))


def apply_neighborhoods(s: Scenario, plan: list, zones: list, picks: list) -> list:
    """Reemplaza las rutas de cada zona por lo que eligió la QPU (si fue válido) y valida todo."""
    new = list(plan)
    for z, pick in zip(zones, picks):
        if pick is None:
            continue
        new = [r for r in new if r.slot not in z["slots"]] + list(pick["routes"])
    if not validate(s, new)["ok"]:
        return plan
    return sorted(new, key=lambda r: r.slot)


def qpu_round(s: Scenario, plan: list, pool: list, backend, label: str, shots: int = 4000, p: int = 1,
              max_variables: int = 12, max_neighborhoods: int = 4, slots_per_zone: int = 3,
              exclude=(), seed: int = SEED):
    """Una ronda cuántica: elegir zonas -> QUBO -> ángulos -> UN job en la QPU -> decodificar -> aplicar.
    Devuelve (plan_nuevo, filas_de_metricas, info_del_job, zonas_sin_mejora)."""
    zones = select_neighborhoods(s, plan, pool, max_variables, max_neighborhoods, slots_per_zone, exclude)
    if not zones:
        print(f"[{label}] no hay zonas con alternativas: el plan es un óptimo local para estas zonas.")
        return plan, [], None, []
    qubos = [make_qubo(z) for z in zones]
    angles = [train_angles(q, p, seed=seed) for q in qubos]
    circuits = [qaoa_circuit(q, a["params"], p) for q, a in zip(qubos, angles)]
    run = run_on_qpu(backend, circuits, shots, label)
    rows, picks, tried = [], [], []
    for z, q, cnt, ci in zip(zones, qubos, run["counts"], run["circuits"]):
        an = analyze_counts(q, cnt); ub = uniform_baseline(q, shots, seed)
        picks.append(an["best"])
        inc = plan_cost(z["incumbent"])
        if an["best"] is None or an["best"]["obj"] >= inc - 1e-9:
            tried.append(z["slots"])
        rows.append({"etapa": label, "zona": z["name"], "qubits": q["n"], "alternativas": z["alternatives"],
                     "prof_isa": ci["prof_isa"], "puertas_2q": ci["puertas_2q"],
                     "fidelidad_estimada": None if ci["fidelidad_estimada"] is None else round(ci["fidelidad_estimada"], 3),
                     "% válidas QPU": round(an["pct_valid"], 2), "% válidas azar": round(ub["pct_valid"], 2),
                     "% óptimo QPU": round(an["pct_optimo"], 2), "% óptimo azar": round(ub["pct_optimo"], 2),
                     "costo antes": round(inc, 1),
                     "costo QPU": None if an["best"] is None else round(an["best"]["obj"], 1),
                     "óptimo zona": round(an["optimo_zona"], 1), "job_id": run["job_id"]})
    new_plan = apply_neighborhoods(s, plan, zones, picks)
    return new_plan, rows, run, tried


def repair_minimal_change(s: Scenario, plan: list, pool: list, time_limit: float = 30.0) -> dict:
    """Tras un evento: plan factible que conserva el máximo de viajes ya planificados
    (costo 0 a la ruta idéntica a la anterior, 1 a cualquier cambio)."""
    keep = {(r.slot, r.points) for r in plan}
    required = set(s.stops) - set(unreachable(s, pool))
    return solve_master(s, pool, time_limit, required, cost_of=lambda r: 0.0 if (r.slot, r.points) in keep else 1.0)


def export_json(path, s: Scenario, plan: list, metadata: Optional[dict] = None) -> Path:
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    body = {"escenario": s.name, "datos": "ilustrativos", "distancias": s.distance_source, "clima": s.weather_source,
            "resumen": summary(s, plan), "rutas": [asdict(r) for r in plan], "validacion": validate(s, plan),
            "metadata": metadata or {}}
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path
