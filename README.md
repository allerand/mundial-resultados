# Resultados del Mundial 2026 — fuente para el Prode "Segurola y Habana"

Feed de resultados del Mundial mapeado a los IDs de partido del Prode (`M01`–`M104`).
Se actualiza **cada 5 minutos** vía GitHub Actions. Fuente de datos:
[football-data.org](https://www.football-data.org/).

## Para el dev: cómo consumirlo

Leé este archivo (se regenera solo):

```
https://raw.githubusercontent.com/USUARIO/REPO/main/data/resultados.json
```

> Reemplazá `USUARIO/REPO` por el repo real. El raw de GitHub tiene cache de
> ~5 min; si necesitás algo más fresco, usá jsDelivr:
> `https://cdn.jsdelivr.net/gh/USUARIO/REPO@main/data/resultados.json`

### Esquema

Es un objeto keyed por `match_id` (`M01`..`M104`):

```json
"M19": {
  "match_id": "M19",
  "fecha_ba": "16/06/2026 22:00",     // horario Buenos Aires
  "etapa": "GROUP_STAGE",             // GROUP_STAGE | LAST_32 | LAST_16 | QUARTER_FINALS | SEMI_FINALS | THIRD_PLACE | FINAL
  "grupo": "J",                        // null en eliminatorias
  "local_code": "ARG", "local": "Argentina",
  "visitante_code": "ALG", "visitante": "Argelia",
  "goles_local": null, "goles_visitante": null,
  "estado": "TIMED",                   // estado crudo de la API
  "categoria": "no_jugado",            // no_jugado | en_juego | finalizado
  "minuto": null,                      // minuto de juego si está en vivo
  "api_match_id": 537397
}
```

### Reglas de uso

1. **Empareja por `match_id`** con tus partidos (`M01`..`M104`).
2. **Solo escribí el resultado si `categoria != "no_jugado"`** — así no pisás con `null`
   los partidos que todavía no se jugaron.
   - `finalizado` → resultado final (en eliminatorias, marcador tras los 120').
   - `en_juego`   → marcador parcial; conviene refrescar cada pocos minutos.
3. **Eliminatorias (M73–M104):** al principio vienen con `local`/`visitante` en `null`
   (aún no se sabe quién las juega). Se completan solas a medida que avanza el torneo.
   Los penales **no** se reflejan en el marcador (como pide el reglamento del Prode).

## Cómo está mapeado (confiabilidad)

- **Grupos (M01–M72):** por el par de equipos (cada cruce es único en todo el torneo).
- **Eliminatorias (M73–M104):** por fecha + hora de inicio en horario de Buenos Aires
  (cada partido de KO tiene un horario único, verificado contra el fixture del Prode).

## Operación

- El scraper es [`scraper.py`](scraper.py). La API key se pasa por la variable de
  entorno `FOOTBALL_DATA_TOKEN` (en GitHub, como *Secret* del repo — **nunca** commiteada).
- El workflow está en [`.github/workflows/update.yml`](.github/workflows/update.yml).
- Disparo manual: pestaña **Actions** → *Actualizar resultados del Mundial* → *Run workflow*.

### Correrlo localmente

```bash
export FOOTBALL_DATA_TOKEN=tu_token
python3 scraper.py -v
```
