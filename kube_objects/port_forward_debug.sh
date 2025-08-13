#!/bin/bash

declare -A node_ports=(
  [master]=8500
  [worker1]=8501
  [worker2]=8502
  [worker3]=8503
  [worker4]=8504
)

kubectl -n monitoring get pods -o wide | grep metrics-forecast | while read -r pod _ _ _ _ _ _ node _; do
  port=${node_ports[$node]}
  if [[ -n "$port" ]]; then
    screen -dmS "kubectl-port-forward-$node" kubectl -n monitoring port-forward "$pod" "${port}":8501 --address 0.0.0.0
  fi
done
