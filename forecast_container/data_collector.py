from prometheus_api_client import PrometheusConnect

# Connect to Prometheus
prometheus = PrometheusConnect(
    url="http://kube-prometheus-kube-prome-prometheus.monitoring.svc.cluster.local:9090",
    disable_ssl=True
)

# We expect the returned data to be a list of dictionaries
# Example: [{'metric': {'nodename': 'nodename'}, 'value': [timestamp, 'value']}]
def get_data(metric):
    if metric == "cpu":
        query = '100 - (avg by (nodename) (avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[1m])) * on(instance) group_left(nodename) node_uname_info) * 100)'
    return prometheus.custom_query(query)
