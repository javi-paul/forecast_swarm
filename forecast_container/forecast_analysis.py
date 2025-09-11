from typing import List, Dict, Any
from collections import defaultdict


def analyze_forecast(
    forecast_holt: List[float],
    forecast_karima: List[float],
    *,
    step_seconds: float = 15.0,
    saturation_threshold: float = 90.0,
    ramp_info_threshold: float = 5.0,
    ramp_warning_threshold: float = 10.0,
    ramp_error_threshold: float = 20.0,
    high_usage_threshold: float = 80.0,
    disagreement_threshold: float = 10.0
) -> List[Dict[str, Any]]:
    """
    Analyze two forecasts.
    Returns a list of alert dicts:
      { type, method, step/start_step/end_step, value, minutes, level, msg, ... }
    Alert types:
      - saturation: hits saturation_threshold
      - ramp: total increase >= ramp thresholds
      - persistent_high: consecutive steps >= high_usage_threshold for 80% of forecast
      - model_disagreement: holt vs karima differ by >= disagreement_threshold at a step
    """
    n = len(forecast_holt)
    if n == 0:
        return []

    raw_alerts: List[Dict[str, Any]] = []

    def emit(a: Dict[str, Any]):
        # level must be already set in 'a' when calling emit
        raw_alerts.append(a)

    # per-method checks
    for method_name, forecast in (("holt", forecast_holt), ("karima", forecast_karima)):
        # saturation: first step reaching saturation_threshold -> warning
        for i, v in enumerate(forecast):
            if v >= saturation_threshold:
                emit({
                    "type": "saturation",
                    "method": method_name,
                    "step": i,
                    "value": v,
                    "seconds": i * step_seconds,
                    "level": "warning",
                })
                break

        # ramp: ramp detection across entire forecast
        if n >= 2:
            total_ramp = forecast[-1] - forecast[0]

            # We care only about increasing ramps (total_ramp > 0)
            if total_ramp > 0.0:
                # decide level by explicit thresholds on total_ramp (transparent mapping)
                if total_ramp >= ramp_error_threshold:
                    ramp_level = "error"
                elif total_ramp >= ramp_warning_threshold:
                    ramp_level = "warning"
                elif total_ramp >= ramp_info_threshold:
                    ramp_level = "info"
                else:
                    ramp_level = None

                if ramp_level is not None:
                    emit({
                        "type": "ramp",
                        "method": method_name,
                        "total_ramp": total_ramp,
                        "level": ramp_level,
                    })

        # persistent high usage: consecutive steps >= high_usage_threshold -> warning
        high_usage = 0
        for i, v in enumerate(forecast):
            if v >= high_usage_threshold:
                high_usage += 1
        if high_usage >= 0.8 * n:
            emit({
                "type": "persistent_high",
                "method": method_name,
                "level": "warning",
            })

    # cross-model disagreement (average difference) -> info
    avg_diff = sum(abs(forecast_holt[i] - forecast_karima[i]) for i in range(n)) / n
    if avg_diff >= disagreement_threshold:
        emit({
            "type": "model_disagreement",
            "method": "holt_vs_karima",
            "level": "info",
            "msg": f"holt vs karima average difference is {avg_diff:.1f} the next {n*step_seconds:.1f}s"
        })


    final_alerts = []
    alerts_by_type = defaultdict(list)
    for alert in raw_alerts:
        alerts_by_type[alert["type"]].append(alert)

    for alert_type, alerts in alerts_by_type.items():
        if alert_type == "model_disagreement":
            # keep them separate or aggregate here
            for a in alerts:
                final_alerts.append({"level": a["level"], "msg": a["msg"]})
        elif alert_type == "saturation":
            final_alerts.append({
                "level": "error" if len(alerts) > 1 else alerts[0]["level"],
                "msg": f"High peak detected above {saturation_threshold}% -> " + " and ".join(f"{a['method'].upper()}: {a['value']:.1f}% in {a['seconds']:.1f}s" for a in alerts)
            })
        elif alert_type == "persistent_high":
            final_alerts.append({
                "level": "error" if len(alerts) > 1 else alerts[0]["level"],
                "msg": f"Persistent high usage >= {high_usage_threshold}% during the next {n*step_seconds:.1f}s -> " + " and ".join(f"{a['method'].upper()}" for a in alerts)
            })
        elif alert_type == "ramp":
            max_level = max(alerts, key=lambda a: ["info", "warning", "error"].index(a["level"]))["level"]
            final_alerts.append({
                "level": max_level,
                "msg": "Detected increasing ramp -> " + " and ".join(f"{a['method'].upper()}: {a['total_ramp']:.1f}%" for a in alerts)
            })

    return final_alerts
