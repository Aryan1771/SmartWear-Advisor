# backend/recommendation_engine.py
# Generates accessory recommendations based on weather, AQI, UV, and rain forecast.

def generate_recommendation(weather: dict, mask_status: str, glasses_status: str,
                             forecast: list = None) -> list:
    recs = []

    temp       = weather.get("temp", 25)
    feels_like = weather.get("feels_like", temp)
    condition  = weather.get("condition", "clear").lower()
    uv         = float(weather.get("uv_index", 0))
    aqi        = int(weather.get("aqi", 1))
    aqi_label  = weather.get("aqi_label", "Good")

    is_mask    = (mask_status    == "Mask")
    is_glasses = (glasses_status == "Glasses")

    # ── Temperature & Feels-Like ──────────────────────────────────
    if temp < 8:
        recs.append("🧣 It's very cold — wear a scarf, gloves, and warm layers.")
    elif temp < 15:
        recs.append("🧥 Cool weather detected. A light jacket is recommended.")

    if abs(feels_like - temp) >= 4:
        direction = "colder" if feels_like < temp else "warmer"
        recs.append(
            f"🌡️ It feels {direction} than it looks: {feels_like}°C vs actual {temp}°C. "
            "Dress for how it feels."
        )

    # ── Mask / Air Quality ────────────────────────────────────────
    polluted_conditions = {"smog", "smoke", "haze", "dust", "sand", "ash"}

    if aqi >= 4:
        if not is_mask:
            recs.append(
                f"😷 Air quality is {aqi_label} (AQI {aqi}). "
                "Wear a mask outdoors to protect your airways."
            )
        else:
            recs.append(
                f"✅ Good call wearing a mask — air quality is {aqi_label} today."
            )
    elif aqi == 3:
        if not is_mask:
            recs.append(
                f"😷 Air quality is Moderate (AQI {aqi}). "
                "Consider wearing a mask, especially if outdoors for a long time."
            )
    elif condition in polluted_conditions:
        if not is_mask:
            recs.append(
                f"😷 {condition.capitalize()} conditions detected. "
                "A mask is advisable for outdoor activity."
            )
    elif temp < 10:
        if not is_mask:
            recs.append(
                "😷 Cold air can irritate airways — a mask can help keep them warm."
            )
    elif is_mask and aqi <= 2 and condition not in polluted_conditions:
        recs.append(
            "✅ Air quality is good today — you may remove the mask if you like."
        )

    # ── Glasses / UV ─────────────────────────────────────────────
    sunny_conditions = {"clear", "sunny"}

    if uv >= 8:
        if not is_glasses:
            recs.append(
                f"🕶️ UV index is very high ({uv}) — sunglasses are strongly recommended "
                "to protect your eyes."
            )
        else:
            recs.append(f"✅ Smart choice — UV index is high ({uv}) today.")
    elif uv >= 5:
        if not is_glasses:
            recs.append(
                f"🕶️ UV index is moderate-high ({uv}). "
                "Consider wearing sunglasses if you'll be outside."
            )
    elif uv >= 3 and condition in sunny_conditions:
        if not is_glasses:
            recs.append(
                f"🕶️ It's sunny with UV index {uv} — sunglasses are a good idea."
            )
    elif uv < 2 and condition not in sunny_conditions and is_glasses:
        recs.append(
            "🕶️ Low UV and overcast sky — sunglasses are optional right now."
        )

    # ── Rain Probability (from Open-Meteo forecast) ───────────────
    if forecast:
        max_precip = max((h.get("precip_prob", 0) for h in forecast), default=0)
        if max_precip >= 60:
            recs.append(
                f"☔ {int(max_precip)}% chance of rain in the next few hours. "
                "Carry an umbrella before heading out."
            )
        elif max_precip >= 40:
            recs.append(
                f"🌂 {int(max_precip)}% chance of rain — an umbrella might be handy."
            )

    if not recs:
        recs.append("✅ Conditions look great. You're all set — enjoy your day!")

    return recs
