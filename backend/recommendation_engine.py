# backend/recommendation_engine.py (PRODUCTION READY)

def _normalize(val: str) -> str:
    return str(val).strip().lower()


def generate_recommendation(
    weather: dict,
    mask_status: str,
    glasses_status: str,
    forecast: list = None,
) -> list:

    recs = []
    added = set()  # 🔥 prevent duplicates

    # ── Normalize inputs ────────────────────────────────
    mask_status = _normalize(mask_status)
    glasses_status = _normalize(glasses_status)

    is_mask = "mask" in mask_status
    is_glasses = "glass" in glasses_status

    temp = int(weather.get("temp", 25))
    feels_like = int(weather.get("feels_like", temp))
    condition = _normalize(weather.get("condition", "clear"))
    uv = float(weather.get("uv_index", 0))
    aqi = int(weather.get("aqi", 1))
    aqi_label = weather.get("aqi_label", "Good")

    def add(msg):
        if msg not in added:
            recs.append(msg)
            added.add(msg)

    # ── Temperature & Comfort ───────────────────────────
    if temp < 8:
        add("🧣 It's very cold — wear a scarf, gloves, and warm layers.")
    elif temp < 15:
        add("🧥 Cool weather detected. A light jacket is recommended.")

    if abs(feels_like - temp) >= 4:
        direction = "colder" if feels_like < temp else "warmer"
        add(
            f"🌡️ Feels {direction} than actual ({feels_like}°C vs {temp}°C). Dress accordingly."
        )

    # ── Air Quality / Mask (HIGH PRIORITY) ──────────────
    polluted_conditions = {"smog", "smoke", "haze", "dust", "sand", "ash"}

    if aqi >= 4:
        if not is_mask:
            add(f"😷 Air quality is {aqi_label} (AQI {aqi}) — wear a mask outdoors.")
        else:
            add(f"✅ Mask is recommended today due to {aqi_label} air quality.")

    elif aqi == 3:
        if not is_mask:
            add("😷 Moderate air quality — consider wearing a mask outdoors.")

    elif condition in polluted_conditions and not is_mask:
        add(f"😷 {condition.capitalize()} conditions — mask is advisable.")

    elif temp < 10 and not is_mask:
        add("😷 Cold air can irritate airways — wearing a mask can help.")

    elif is_mask and aqi <= 2 and condition not in polluted_conditions:
        add("✅ Air quality is good — mask is optional today.")

    # ── UV / Glasses (HIGH PRIORITY) ────────────────────
    sunny_conditions = {"clear", "sunny"}

    if uv >= 8:
        if not is_glasses:
            add(f"🕶️ Very high UV ({uv}) — sunglasses strongly recommended.")
        else:
            add(f"✅ Good choice — high UV ({uv}) today.")

    elif uv >= 5:
        if not is_glasses:
            add(f"🕶️ UV is moderate-high ({uv}) — consider sunglasses.")

    elif uv >= 3 and condition in sunny_conditions:
        if not is_glasses:
            add(f"🕶️ Sunny conditions with UV {uv} — sunglasses help.")

    elif uv < 2 and condition not in sunny_conditions and is_glasses:
        add("🕶️ Low UV — sunglasses optional right now.")

    # ── Rain Forecast ───────────────────────────────────
    if forecast:
        max_precip = max((h.get("precip_prob", 0) for h in forecast), default=0)

        if max_precip >= 60:
            add(f"☔ {int(max_precip)}% chance of rain — carry an umbrella.")
        elif max_precip >= 40:
            add(f"🌂 {int(max_precip)}% chance of rain — umbrella might be useful.")

    # ── Default ─────────────────────────────────────────
    if not recs:
        add("✅ Conditions look great — you're all set!")

    return recs
