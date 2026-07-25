# Kubernetes Cluster Setup with kubeadm (1 Master + 2 Worker Nodes)

![Kubernetes](https://img.shields.io/badge/Kubernetes-v1.29.6-326CE5?logo=kubernetes&logoColor=white)
![Container Runtime](https://img.shields.io/badge/Containerd-v1.7.14-blue)
![CNI](https://img.shields.io/badge/Calico-v3.28-green)
![Platform](https://img.shields.io/badge/Platform-Ubuntu-orange)

## 📖 Overview

This repository provides a complete step-by-step guide to deploy a production-style Kubernetes cluster using **kubeadm**.

The cluster consists of:

- **1 Master (Control Plane) Node**
- **2 Worker Nodes**
- **Container Runtime:** containerd
- **CNI Plugin:** Calico
- **Kubernetes Version:** v1.29.6

> **Note:** Kubernetes **v1.29** is intentionally installed so the cluster can later be upgraded to **v1.30**.

---

# Architecture

```
                   +----------------------+
                   |    Master Node       |
                   |----------------------|
                   | kube-apiserver       |
                   | etcd                |
                   | scheduler           |
                   | controller-manager  |
                   +----------+----------+
                              |
             -------------------------------------
             |                                   |
     +-------+--------+                 +--------+-------+
     |   Worker Node1 |                 | Worker Node2  |
     |----------------|                 |---------------|
     | kubelet        |                 | kubelet       |
     | kube-proxy     |                 | kube-proxy    |
     | containerd     |                 | containerd    |
     +----------------+                 +---------------+
```

---

# Infrastructure

Provision the following Virtual Machines:

| Node | Quantity | Purpose |
|-------|----------|----------|
| Master | 1 | Kubernetes Control Plane |
| Worker | 2 | Run application workloads |

---

# Security Groups

Create **two Security Groups**.

## Master Security Group

| Protocol | Direction | Port | Purpose |
|----------|-----------|------|----------|
| TCP | Inbound | 22 | SSH (Self) |
| TCP | Inbound | 6443 | Kubernetes API Server |
| TCP | Inbound | 2379-2380 | etcd |
| TCP | Inbound | 10250 | Kubelet API |
| TCP | Inbound | 10257 | Controller Manager |
| TCP | Inbound | 10259 | Scheduler |

---

## Worker Security Group

| Protocol | Direction | Port | Purpose |
|----------|-----------|------|----------|
| TCP | Inbound | 22 | SSH (Self) |
| TCP | Inbound | 10250 | Kubelet API |
| TCP | Inbound | 10256 | kube-proxy |
| TCP | Inbound | 30000-32767 | NodePort Services |
| UDP | Inbound | 30000-32767 | NodePort Services |

---

## Additional Security Rule (Calico)

Attach this rule to **both Master and Worker Security Groups**.

| Protocol | Direction | Port | Purpose |
|----------|-----------|------|----------|
| TCP | Inbound & Outbound | 179 | Calico BGP |

> If Calico pods are unhealthy, disable **Source/Destination Check** on all EC2 instances.

---

# Master Node Setup

SSH into the Master node.

---

# Step 1 - Disable Swap

```bash
swapoff -a

sudo sed -i '/ swap / s/^\(.*\)$/#\1/g' /etc/fstab
```

---

# Step 2 - Enable Kernel Modules

```bash
cat <<EOF | sudo tee /etc/modules-load.d/k8s.conf
overlay
br_netfilter
EOF

sudo modprobe overlay

sudo modprobe br_netfilter
```

---

# Step 3 - Configure Networking

```bash
cat <<EOF | sudo tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-iptables=1
net.bridge.bridge-nf-call-ip6tables=1
net.ipv4.ip_forward=1
EOF

sudo sysctl --system
```

Verify

```bash
lsmod | grep br_netfilter

lsmod | grep overlay

sysctl net.bridge.bridge-nf-call-iptables \
net.bridge.bridge-nf-call-ip6tables \
net.ipv4.ip_forward
```

---

# Step 4 - Install containerd

Download

```bash
curl -LO https://github.com/containerd/containerd/releases/download/v1.7.14/containerd-1.7.14-linux-amd64.tar.gz
```

Extract

```bash
sudo tar Cxzvf /usr/local containerd-1.7.14-linux-amd64.tar.gz
```

Install service

```bash
curl -LO https://raw.githubusercontent.com/containerd/containerd/main/containerd.service

sudo mkdir -p /usr/local/lib/systemd/system/

sudo mv containerd.service /usr/local/lib/systemd/system/
```

Generate configuration

```bash
sudo mkdir -p /etc/containerd

containerd config default | sudo tee /etc/containerd/config.toml
```

Enable Systemd Cgroup

```bash
sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/g' \
/etc/containerd/config.toml
```

Enable service

```bash
sudo systemctl daemon-reload

sudo systemctl enable --now containerd
```

Verify

```bash
systemctl status containerd
```

---

# Step 5 - Install runc

```bash
curl -LO https://github.com/opencontainers/runc/releases/download/v1.1.12/runc.amd64

sudo install -m 755 runc.amd64 /usr/local/sbin/runc
```

---

# Step 6 - Install CNI Plugins

```bash
curl -LO https://github.com/containernetworking/plugins/releases/download/v1.5.0/cni-plugins-linux-amd64-v1.5.0.tgz

sudo mkdir -p /opt/cni/bin

sudo tar Cxzvf /opt/cni/bin cni-plugins-linux-amd64-v1.5.0.tgz
```

---

# Step 7 - Install Kubernetes Components

Install prerequisites

```bash
sudo apt-get update

sudo apt-get install -y apt-transport-https ca-certificates curl gpg
```

Add Kubernetes repository

```bash
curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.29/deb/Release.key \
| sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
```

```bash
echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.29/deb/ /' \
| sudo tee /etc/apt/sources.list.d/kubernetes.list
```

Install packages

```bash
sudo apt-get update

sudo apt-get install -y \
kubelet=1.29.6-1.1 \
kubeadm=1.29.6-1.1 \
kubectl=1.29.6-1.1 \
--allow-downgrades \
--allow-change-held-packages
```

Hold package versions

```bash
sudo apt-mark hold kubelet kubeadm kubectl
```

Verify

```bash
kubeadm version

kubelet --version

kubectl version --client
```

---

# Step 8 - Configure crictl

```bash
sudo crictl config runtime-endpoint \
unix:///var/run/containerd/containerd.sock
```

---

# Step 9 - Initialize the Control Plane

Replace the advertise IP with your Master private IP.

```bash
sudo kubeadm init \
--pod-network-cidr=192.168.0.0/16 \
--apiserver-advertise-address=<MASTER_PRIVATE_IP> \
--node-name=master
```

Example

```bash
sudo kubeadm init \
--pod-network-cidr=192.168.0.0/16 \
--apiserver-advertise-address=172.31.89.68 \
--node-name=master
```

> **Important:** Save the generated `kubeadm join` command. It will be used later to join Worker nodes.

---

# Step 10 - Configure kubectl

```bash
mkdir -p $HOME/.kube

sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config

sudo chown $(id -u):$(id -g) $HOME/.kube/config
```

---

# Step 11 - Install Calico

Install Tigera Operator

```bash
kubectl create -f \
https://raw.githubusercontent.com/projectcalico/calico/v3.28.0/manifests/tigera-operator.yaml
```

Download custom resources

```bash
curl https://raw.githubusercontent.com/projectcalico/calico/v3.28.0/manifests/custom-resources.yaml -O
```

Apply

```bash
kubectl apply -f custom-resources.yaml
```

---

# Worker Node Setup

Perform **Steps 1 through 8** on **both Worker nodes**.

Do **NOT** initialize the cluster.

---

# Join Worker Nodes

Run the join command generated by the Master node.

Example:

```bash
sudo kubeadm join 172.31.71.210:6443 \
--token xxxxxxxxx \
--discovery-token-ca-cert-hash sha256:xxxxxxxx
```

If you lost the command, regenerate it on the Master:

```bash
kubeadm token create --print-join-command
```

---

# Validation

Verify all nodes are ready.

```bash
kubectl get nodes
```

Expected output

```
NAME        STATUS   ROLES           AGE
master      Ready    control-plane
worker-1    Ready    <none>
worker-2    Ready    <none>
```

Check all pods.

```bash
kubectl get pods -A
```

All pods should be in **Running** state.

---

# Calico Troubleshooting

## 1. Disable Source/Destination Check

Disable **Source/Destination Check** on:

- Master Node
- Worker Node 1
- Worker Node 2

---

## 2. Add Security Group Rule

Allow:

| Protocol | Port |
|----------|------|
| TCP | 179 |

Attach the rule to every node.

---

## 3. Configure Interface Detection

Find the default interface.

```bash
ifconfig
```

Update Calico.

```bash
kubectl set env daemonset/calico-node \
-n calico-system \
IP_AUTODETECTION_METHOD=interface=ens5
```

Replace **ens5** with your default network interface if different.

Wait a few minutes or restart the Calico pods.

---

## 4. Alternative Calico Installation

If the operator installation continues to fail, deploy Calico using the manifest.

```bash
kubectl apply -f https://docs.projectcalico.org/manifests/calico.yaml
```

> **Note:** This installs **Calico v3.25** in the `kube-system` namespace rather than the latest release.

---

# Verify Cluster Health

Check Nodes

```bash
kubectl get nodes
```

Check Pods

```bash
kubectl get pods -A
```

Check Cluster Info

```bash
kubectl cluster-info
```

---

# Kubernetes Version

| Component | Version |
|------------|----------|
| Kubernetes | v1.29.6 |
| kubeadm | v1.29.6 |
| kubelet | v1.29.6 |
| kubectl | v1.29.6 |
| containerd | v1.7.14 |
| runc | v1.1.12 |
| Calico | v3.28.0 |

---

# Repository Structure

```
.
├── README.md
├── manifests/
├── scripts/
└── images/
```

---

# References

- Kubernetes Documentation
- kubeadm Installation Guide
- Containerd Documentation
- Project Calico Documentation

---

## ⭐ If you found this guide useful, consider giving the repository a Star.
