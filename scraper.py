#!/usr/bin/env python3
"""
Fuente confiable de resultados del Mundial 2026 para el Prode "Segurola y Habana".

Toma los resultados de football-data.org (API publica con key) y los entrega
mapeados a los IDs de partido del Prode (M01..M104), listos para que el dev
los consuma.

Reglas de resultado (segun pide la consigna del Prode):
  - Partido FINALIZADO  -> resultado final (en eliminatorias, tras los 120').
  - Partido EN JUEGO     -> marcador parcial, se va actualizando.
  - Partido NO JUGADO     -> goles vacios (null).

Mapeo a M01..M104:
  - Fase de grupos (M01-M72): por el par de equipos (cada cruce es unico).
  - Eliminatorias (M73-M104): por fecha+hora de inicio en horario de Buenos Aires
    (cada partido de KO tiene un horario unico).

Uso:
    python3 scraper.py        # genera la tabla; corre cada 5 min por cron
    python3 scraper.py -v     # ademas imprime la tabla en pantalla

Salidas en ./data:
    resultados.json  -> dict keyed por match_id (M01..M104)  [fuente para el dev]
    resultados.csv   -> una fila por partido
    resultados.txt   -> tabla legible
    historial.csv    -> log de cada lectura (evolucion de marcadores en vivo)
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

TOKEN = os.environ.get("FOOTBALL_DATA_TOKEN")
if not TOKEN:
    raise SystemExit(
        "Falta la API key. Seteá la variable de entorno FOOTBALL_DATA_TOKEN.\n"
        "  Local:  export FOOTBALL_DATA_TOKEN=tu_token\n"
        "  GitHub: Settings > Secrets and variables > Actions > FOOTBALL_DATA_TOKEN"
    )
API_URL = "https://api.football-data.org/v4/competitions/WC/matches"
LOCAL_TZ = timezone(timedelta(hours=-3))  # Buenos Aires

FINISHED = {"FINISHED", "AWARDED"}
LIVE = {"IN_PLAY", "PAUSED", "SUSPENDED"}

# --- Diccionario: nombre en la API (ingles) -> (codigo FIFA, nombre en espanol)
TEAMS = {
    "Algeria": ("ALG", "Argelia"),
    "Argentina": ("ARG", "Argentina"),
    "Australia": ("AUS", "Australia"),
    "Austria": ("AUT", "Austria"),
    "Belgium": ("BEL", "Bélgica"),
    "Bosnia-Herzegovina": ("BIH", "Bosnia y Herzegovina"),
    "Brazil": ("BRA", "Brasil"),
    "Canada": ("CAN", "Canadá"),
    "Cape Verde Islands": ("CPV", "Cabo Verde"),
    "Colombia": ("COL", "Colombia"),
    "Congo DR": ("COD", "RD del Congo"),
    "Croatia": ("CRO", "Croacia"),
    "Curaçao": ("CUW", "Curazao"),
    "Czechia": ("CZE", "República Checa"),
    "Ecuador": ("ECU", "Ecuador"),
    "Egypt": ("EGY", "Egipto"),
    "England": ("ENG", "Inglaterra"),
    "France": ("FRA", "Francia"),
    "Germany": ("GER", "Alemania"),
    "Ghana": ("GHA", "Ghana"),
    "Haiti": ("HAI", "Haití"),
    "Iran": ("IRN", "Irán"),
    "Iraq": ("IRQ", "Irak"),
    "Ivory Coast": ("CIV", "Costa de Marfil"),
    "Japan": ("JPN", "Japón"),
    "Jordan": ("JOR", "Jordania"),
    "Mexico": ("MEX", "México"),
    "Morocco": ("MAR", "Marruecos"),
    "Netherlands": ("NED", "Países Bajos"),
    "New Zealand": ("NZL", "Nueva Zelanda"),
    "Norway": ("NOR", "Noruega"),
    "Panama": ("PAN", "Panamá"),
    "Paraguay": ("PAR", "Paraguay"),
    "Portugal": ("POR", "Portugal"),
    "Qatar": ("QAT", "Catar"),
    "Saudi Arabia": ("KSA", "Arabia Saudita"),
    "Scotland": ("SCO", "Escocia"),
    "Senegal": ("SEN", "Senegal"),
    "South Africa": ("RSA", "Sudáfrica"),
    "South Korea": ("KOR", "Corea del Sur"),
    "Spain": ("ESP", "España"),
    "Sweden": ("SWE", "Suecia"),
    "Switzerland": ("SUI", "Suiza"),
    "Tunisia": ("TUN", "Túnez"),
    "Turkey": ("TUR", "Turquía"),
    "United States": ("USA", "Estados Unidos"),
    "Uruguay": ("URU", "Uruguay"),
    "Uzbekistan": ("UZB", "Uzbekistán"),
}

# --- Fixture de referencia del Prode -----------------------------------------
# Fase de grupos: M## -> (codigo_local, codigo_visitante). El cruce define el partido.
GROUP_FIXTURE = {
    "M01": ("MEX", "RSA"), "M02": ("KOR", "CZE"), "M03": ("CAN", "BIH"),
    "M04": ("USA", "PAR"), "M05": ("QAT", "SUI"), "M06": ("BRA", "MAR"),
    "M07": ("HAI", "SCO"), "M08": ("AUS", "TUR"), "M09": ("ESP", "CPV"),
    "M10": ("GER", "CUW"), "M11": ("NED", "JPN"), "M12": ("CIV", "ECU"),
    "M13": ("SWE", "TUN"), "M14": ("BEL", "EGY"), "M15": ("KSA", "URU"),
    "M16": ("IRN", "NZL"), "M17": ("FRA", "SEN"), "M18": ("IRQ", "NOR"),
    "M19": ("ARG", "ALG"), "M20": ("AUT", "JOR"), "M21": ("POR", "COD"),
    "M22": ("ENG", "CRO"), "M23": ("GHA", "PAN"), "M24": ("UZB", "COL"),
    "M25": ("CZE", "RSA"), "M26": ("SUI", "BIH"), "M27": ("CAN", "QAT"),
    "M28": ("MEX", "KOR"), "M29": ("USA", "AUS"), "M30": ("SCO", "MAR"),
    "M31": ("BRA", "HAI"), "M32": ("TUN", "JPN"), "M33": ("NED", "SWE"),
    "M34": ("GER", "CIV"), "M35": ("ECU", "CUW"), "M36": ("NZL", "EGY"),
    "M37": ("ESP", "KSA"), "M38": ("BEL", "IRN"), "M39": ("URU", "CPV"),
    "M40": ("ARG", "AUT"), "M41": ("FRA", "IRQ"), "M42": ("NOR", "SEN"),
    "M43": ("JOR", "ALG"), "M44": ("POR", "UZB"), "M45": ("ENG", "GHA"),
    "M46": ("PAN", "CRO"), "M47": ("COL", "COD"), "M48": ("SUI", "CAN"),
    "M49": ("BIH", "QAT"), "M50": ("MAR", "HAI"), "M51": ("SCO", "BRA"),
    "M52": ("RSA", "KOR"), "M53": ("CZE", "MEX"), "M54": ("CUW", "CIV"),
    "M55": ("ECU", "GER"), "M56": ("TUN", "NED"), "M57": ("JPN", "SWE"),
    "M58": ("TUR", "USA"), "M59": ("PAR", "AUS"), "M60": ("NOR", "FRA"),
    "M61": ("SEN", "IRQ"), "M62": ("CPV", "KSA"), "M63": ("URU", "ESP"),
    "M64": ("NZL", "BEL"), "M65": ("EGY", "IRN"), "M66": ("PAN", "ENG"),
    "M67": ("CRO", "GHA"), "M68": ("COL", "POR"), "M69": ("COD", "UZB"),
    "M70": ("ALG", "AUT"), "M71": ("JOR", "ARG"), "M72": ("TUR", "PAR"),
}

# Eliminatorias: M## -> "DD/MM HH:MM" (horario Buenos Aires, unico por partido).
KO_FIXTURE = {
    "M73": "28/06 16:00", "M74": "29/06 14:00", "M75": "29/06 17:30",
    "M76": "29/06 22:00", "M77": "30/06 14:00", "M78": "30/06 18:00",
    "M79": "30/06 22:00", "M80": "01/07 13:00", "M81": "01/07 17:00",
    "M82": "01/07 21:00", "M83": "02/07 16:00", "M84": "02/07 20:00",
    "M85": "03/07 00:00", "M86": "03/07 15:00", "M87": "03/07 19:00",
    "M88": "03/07 22:30", "M89": "04/07 14:00", "M90": "04/07 18:00",
    "M91": "05/07 17:00", "M92": "05/07 21:00", "M93": "06/07 16:00",
    "M94": "06/07 21:00", "M95": "07/07 13:00", "M96": "07/07 17:00",
    "M97": "09/07 17:00", "M98": "10/07 16:00", "M99": "11/07 18:00",
    "M100": "11/07 22:00", "M101": "14/07 16:00", "M102": "15/07 16:00",
    "M103": "18/07 18:00", "M104": "19/07 16:00",
}

# Indices invertidos para lookup rapido.
_GROUP_BY_PAIR = {frozenset(p): mid for mid, p in GROUP_FIXTURE.items()}
_KO_BY_TIME = {t: mid for mid, t in KO_FIXTURE.items()}

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
OUT_JSON = DATA_DIR / "resultados.json"
OUT_CSV = DATA_DIR / "resultados.csv"
OUT_TXT = DATA_DIR / "resultados.txt"
HISTORY_CSV = DATA_DIR / "historial.csv"
LOG_FILE = DATA_DIR / "scraper.log"


def log(msg: str) -> None:
    line = f"{datetime.now().isoformat(timespec='seconds')}  {msg}"
    print(line)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def fetch_matches(retries: int = 3, backoff: float = 3.0) -> tuple[list[dict], dict]:
    last_err = None
    for intento in range(1, retries + 1):
        try:
            req = urllib.request.Request(API_URL, headers={"X-Auth-Token": TOKEN})
            with urllib.request.urlopen(req, timeout=25) as resp:
                rate = {
                    "available_min": resp.headers.get("x-requests-available-minute"),
                    "reset_s": resp.headers.get("x-requestcounter-reset"),
                }
                data = json.loads(resp.read().decode("utf-8"))
            return data.get("matches", []), rate
        except Exception as e:  # noqa: BLE001 -- reintenta ante hipos de red/API
            last_err = e
            if intento < retries:
                log(f"  intento {intento}/{retries} fallo ({e}); reintento en {backoff}s")
                time.sleep(backoff)
    raise last_err


def ba_dt(utc_iso: str) -> datetime | None:
    try:
        return datetime.strptime(utc_iso, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        ).astimezone(LOCAL_TZ)
    except (ValueError, TypeError):
        return None


def team_info(api_name: str | None) -> tuple[str | None, str | None]:
    if not api_name:
        return None, None
    code, es = TEAMS.get(api_name, (None, api_name))
    return code, es


def match_to_mid(m: dict, home_code: str | None, away_code: str | None,
                 dt: datetime | None) -> str | None:
    """Resuelve el ID del Prode (M##) para un partido de la API."""
    if m.get("stage") == "GROUP_STAGE":
        if home_code and away_code:
            return _GROUP_BY_PAIR.get(frozenset((home_code, away_code)))
        return None
    if dt is not None:
        return _KO_BY_TIME.get(dt.strftime("%d/%m %H:%M"))
    return None


def build_table(matches: list[dict]) -> dict:
    """Devuelve dict M## -> fila. Arranca con todos los M## conocidos vacios."""
    all_ids = list(GROUP_FIXTURE) + list(KO_FIXTURE)
    table = {mid: None for mid in all_ids}

    for m in matches:
        status = m.get("status")
        if status in FINISHED:
            categoria = "finalizado"
        elif status in LIVE:
            categoria = "en_juego"
        else:
            categoria = "no_jugado"

        h_code, h_es = team_info((m.get("homeTeam") or {}).get("name"))
        a_code, a_es = team_info((m.get("awayTeam") or {}).get("name"))
        dt = ba_dt(m.get("utcDate"))
        mid = match_to_mid(m, h_code, a_code, dt)
        if not mid:
            continue  # partido aun sin asignar (p.ej. KO con horario movido)

        full = (m.get("score") or {}).get("fullTime") or {}
        gl = gv = None
        if categoria in ("finalizado", "en_juego"):
            gl = full.get("home")
            gv = full.get("away")

        table[mid] = {
            "match_id": mid,
            "fecha_ba": dt.strftime("%d/%m/%Y %H:%M") if dt else "",
            "etapa": m.get("stage"),
            "grupo": (m.get("group") or "").replace("GROUP_", "") or None,
            "local_code": h_code,
            "local": h_es,
            "visitante_code": a_code,
            "visitante": a_es,
            "goles_local": gl,
            "goles_visitante": gv,
            "estado": status,
            "categoria": categoria,
            "minuto": m.get("minute") or None,
            "api_match_id": m.get("id"),
        }
    return table


def mid_num(mid: str) -> int:
    return int(mid[1:])


def save_outputs(table: dict) -> None:
    OUT_JSON.write_text(
        json.dumps(table, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    order = sorted(table.keys(), key=mid_num)
    fields = [
        "match_id", "fecha_ba", "etapa", "grupo",
        "local_code", "local", "goles_local",
        "goles_visitante", "visitante", "visitante_code",
        "estado", "minuto",
    ]
    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for mid in order:
            row = table[mid] or {"match_id": mid}
            w.writerow(row)

    lines = [f"{'ID':<5} {'FECHA':<16} {'PARTIDO':<40} {'RES':<7} ESTADO"]
    lines.append("-" * 88)
    for mid in order:
        r = table[mid]
        if not r:
            lines.append(f"{mid:<5} {'(sin asignar)':<16}")
            continue
        res = ""
        if r["goles_local"] is not None or r["goles_visitante"] is not None:
            gl = r["goles_local"] if r["goles_local"] is not None else ""
            gv = r["goles_visitante"] if r["goles_visitante"] is not None else ""
            res = f"{gl}-{gv}"
        partido = f"{r['local']} vs {r['visitante']}"
        estado = r["estado"] or ""
        if r["categoria"] == "en_juego" and r["minuto"]:
            estado += f" {r['minuto']}'"
        lines.append(
            f"{mid:<5} {r['fecha_ba']:<16} {partido:<40} {res:<7} {estado}"
        )
    OUT_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def append_history(table: dict) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    fields = [
        "timestamp", "match_id", "local", "visitante",
        "goles_local", "goles_visitante", "estado", "minuto",
    ]
    rows = [
        r for r in table.values()
        if r and r["categoria"] != "no_jugado"
    ]
    if not rows:
        return
    nuevo = not HISTORY_CSV.exists()
    with HISTORY_CSV.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if nuevo:
            w.writeheader()
        for r in rows:
            w.writerow({"timestamp": ts, **r})


def main() -> int:
    try:
        matches, rate = fetch_matches()
    except Exception as e:  # noqa: BLE001
        log(f"ERROR al consultar la API: {e}")
        return 1

    table = build_table(matches)
    save_outputs(table)
    append_history(table)

    asignados = sum(1 for r in table.values() if r)
    fin = sum(1 for r in table.values() if r and r["categoria"] == "finalizado")
    live = sum(1 for r in table.values() if r and r["categoria"] == "en_juego")
    log(
        f"OK: {asignados}/104 partidos asignados "
        f"(fin={fin}, en_juego={live}). Rate restante: {rate['available_min']}."
    )
    if "-v" in sys.argv:
        print("\n" + OUT_TXT.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
