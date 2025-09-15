from prometheus_api_client import PrometheusConnect
from datetime import datetime, timedelta

# Connect to Prometheus
prometheus = PrometheusConnect(
    url="http://kube-prometheus-kube-prome-prometheus.monitoring.svc.cluster.local:9090",
    #url="http://localhost:9090",
    disable_ssl=True
)

def load_initial_data(metric, node, w_size=100, s_interval=15):
    end_time = datetime.now()
    start_time = end_time - timedelta(minutes=w_size * s_interval / 60)
    metric_data = prometheus.custom_query_range(
        query=get_query(metric, node),
        start_time=start_time,
        end_time=end_time,
        step=f"{s_interval}s"
    )
    return metric_data


# We expect the returned data to be a list of dictionaries
# Example: [{
#           'metric': {'nodename': 'nodename'}, 
#           'value': [timestamp, 'value']
#          }]
def get_data(metric, node):
    return prometheus.custom_query(get_query(metric, node))


def get_query(metric, node):
    if metric == "cpu":
        query = f'100 - (avg by (nodename) (avg by (instance) (rate(node_cpu_seconds_total{{mode="idle"}}[1m])) * on(instance) group_left(nodename) node_uname_info{{nodename="{node}"}}) * 100)'
    elif metric == "memory":
        query = f'100 * (1 - (avg by (nodename) (node_memory_MemAvailable_bytes * on(instance) group_left(nodename) node_uname_info{{nodename="{node}"}}) / avg by (nodename) (node_memory_MemTotal_bytes * on(instance) group_left(nodename) node_uname_info{{nodename="{node}"}})))'
    elif metric == "disk_read_latency":
        query = f'(sum by (nodename) (rate(node_disk_read_time_seconds_total[1m]) * on(instance) group_left(nodename) node_uname_info{{nodename="{node}"}}) / sum by (nodename) (rate(node_disk_reads_completed_total[1m]) * on(instance) group_left(nodename) node_uname_info{{nodename="{node}"}})) * 1000'
    elif metric == "disk_write_latency":
        query = f'(sum by (nodename) (rate(node_disk_write_time_seconds_total[1m]) * on(instance) group_left(nodename) node_uname_info{{nodename="{node}"}}) / sum by (nodename) (rate(node_disk_writes_completed_total[1m]) * on(instance) group_left(nodename) node_uname_info{{nodename="{node}"}})) * 1000'
    elif metric == "network_tx_saturation":
        query = f'(sum by (nodename) (rate(node_network_transmit_bytes_total{{device!~"lo|docker.*|veth.*"}}[1m]) * 8 * on(instance) group_left(nodename) node_uname_info{{nodename="{node}"}}) / sum by (nodename) (node_network_speed_bytes{{device!~"lo|docker.*|veth.*"}} * on(instance) group_left(nodename) node_uname_info{{nodename="{node}"}})) * 100'
    elif metric == "network_rx_saturation":
        query = f'(sum by (nodename) (rate(node_network_receive_bytes_total{{device!~"lo|docker.*|veth.*"}}[1m]) * 8 * on(instance) group_left(nodename) node_uname_info{{nodename="{node}"}}) / sum by (nodename) (node_network_speed_bytes{{device!~"lo|docker.*|veth.*"}} * on(instance) group_left(nodename) node_uname_info{{nodename="{node}"}})) * 100'
    return query
