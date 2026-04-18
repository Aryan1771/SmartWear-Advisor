def generate_recommendation(weather, is_mask, is_glasses):
    recommendations = []
    temperature = weather.get("temp", 25)
    condition = weather.get("condition", "clear")
    if temperature < 15 or condition in ["smog", "pollution"]:
        if not is_mask:
            recommendations.append("Wear a mask due to cold or polluted weather.")
    else:
        if is_mask:
            recommendations.append("You may remove the mask if comfortable.")
    if condition in ["clear", "sunny"]:
        if not is_glasses:
            recommendations.append("Consider wearing sunglasses.")
    else:
        if is_glasses:
            recommendations.append("Sunglasses may not be necessary now.")
    if not recommendations:
        return ["You are good to go."]
    return recommendations