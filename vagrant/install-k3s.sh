#!/bin/bash


vagrant ssh -c "curl -sfL https://get.k3s.io | sh -" master

K3S_TOKEN=$(vagrant ssh master -c "sudo cat /var/lib/rancher/k3s/server/node-token" 2>/dev/null | tr -d '\r\n' | tr -d '\r' | tr -d '\n')

for i in {1..4}; do
	    vagrant ssh worker$i -c "curl -sfL https://get.k3s.io | K3S_URL=https://192.168.121.10:6443 K3S_TOKEN='$K3S_TOKEN' sh -"
done

vagrant ssh master -c "sudo mkdir -p /home/vagrant/.kube"
vagrant ssh master -c "sudo cp /etc/rancher/k3s/k3s.yaml /home/vagrant/.kube/config"
vagrant ssh master -c "sudo chown vagrant:vagrant /home/vagrant/.kube/config"

vagrant scp master:/home/vagrant/.kube/config /home/javi/.kube/config
sed "s/127.0.0.1/$(vagrant ssh-config master  | grep HostName | awk '{print $2}')/" /home/javi/.kube/config -i