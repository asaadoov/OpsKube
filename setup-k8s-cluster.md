# Kubernetes Cluster Setup Guide
## 3-Node Cluster with kubeadm and containerd

### Overview
This guide documents the setup of a Kubernetes cluster with:
- **1 Control Plane Node** (k8s-master)
- **2 Worker Nodes** (k8s-worker-1, k8s-worker-2)
- **containerd** as container runtime
- **Flannel** as CNI network plugin (needed for pod-2-pod communication)

### Cluster Specifications
| Component | Details |
|-----------|---------|
| **Kubernetes Version** | v1.28.15 |
| **Container Runtime** | containerd v1.7.27 |
| **CNI Plugin** | Flannel |
| **Pod Network CIDR** | 10.244.0.0/16 |
| **Service Network CIDR** | 10.96.0.0/12 |
| **Operating System** | Ubuntu 22.04.5 LTS |

---

## Prerequisites (All Nodes)

### 1. System Requirements
- **OS**: Ubuntu 22.04+ or compatible Linux distribution
- **RAM**: Minimum 2GB (4GB+ recommended)
- **CPU**: Minimum 2 cores
- **Disk**: 20GB+ available space
- **Network**: All nodes must communicate on required ports

### 2. Required Ports
| Node Type | Port | Protocol | Purpose |
|-----------|------|----------|---------|
| Control Plane | 6443 | TCP | Kubernetes API server |
| Control Plane | 2379-2380 | TCP | etcd server client API |
| Control Plane | 10250 | TCP | Kubelet API |
| Control Plane | 10259 | TCP | kube-scheduler |
| Control Plane | 10257 | TCP | kube-controller-manager |
| Worker Nodes | 10250 | TCP | Kubelet API |
| Worker Nodes | 30000-32767 | TCP | NodePort Services |

---

## Step 1: System Preparation (All Nodes)

### Disable Swap
```bash
# Disable swap immediately
sudo swapoff -a

# Disable swap permanently
sudo sed -i '/ swap / s/^\(.*\)$/#\1/g' /etc/fstab

# Verify swap is disabled
free -h
```

### Load Required Kernel Modules
```bash
# Create module configuration
cat <<EOF | sudo tee /etc/modules-load.d/k8s.conf
overlay
br_netfilter
EOF

# Load modules
sudo modprobe overlay
sudo modprobe br_netfilter
```

### Configure Kernel Parameters
```bash
# Configure sysctl parameters
cat <<EOF | sudo tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward                 = 1
EOF

# Apply sysctl params without reboot
sudo sysctl --system
```

---

## Step 2: Install Container Runtime (All Nodes)

### Install containerd
```bash
# Update system packages
sudo apt-get update

# Install containerd
sudo apt-get install -y containerd
```

### Configure containerd
```bash
# Create containerd configuration directory
sudo mkdir -p /etc/containerd

# Generate default configuration
containerd config default | sudo tee /etc/containerd/config.toml

# Configure systemd cgroup driver
sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml

# Restart and enable containerd
sudo systemctl restart containerd
sudo systemctl enable containerd

# Verify containerd is running
sudo systemctl status containerd
```

---

## Step 3: Install Kubernetes Components (All Nodes)

### Add Kubernetes Repository
```bash
# Install prerequisites
sudo apt-get install -y apt-transport-https ca-certificates curl gpg

# Add Kubernetes signing key
curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.28/deb/Release.key | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg

# Add Kubernetes repository
echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.28/deb/ /' | sudo tee /etc/apt/sources.list.d/kubernetes.list
```

### Install Kubernetes Tools
```bash
# Update package index
sudo apt-get update

# Install kubelet, kubeadm, and kubectl
sudo apt-get install -y kubelet kubeadm kubectl

# Hold packages to prevent automatic updates
sudo apt-mark hold kubelet kubeadm kubectl

# Enable kubelet service
sudo systemctl enable kubelet
```

---

## Step 4: Initialize Control Plane (Master Node Only)

### Initialize the Cluster
```bash
# Initialize Kubernetes cluster
sudo kubeadm init \
  --pod-network-cidr=10.244.0.0/16 \
  --apiserver-advertise-address=<MASTER_NODE_IP>

# Example:
sudo kubeadm init \
  --pod-network-cidr=10.244.0.0/16 \
  --apiserver-advertise-address=10.240.0.2
```

### Configure kubectl Access
```bash
# Set up kubeconfig for root user
mkdir -p $HOME/.kube
sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config

# Alternative: Export KUBECONFIG for current session
export KUBECONFIG=/etc/kubernetes/admin.conf
```

### Verify Control Plane
```bash
# Check node status
kubectl get nodes

# Check system pods
kubectl get pods -n kube-system
```

---

## Step 5: Install CNI Network Plugin (Master Node)

### Install Flannel
```bash
# Apply Flannel manifest
kubectl apply -f https://github.com/flannel-io/flannel/releases/latest/download/kube-flannel.yml

# Wait for flannel pods to be ready
kubectl get pods -n kube-flannel

# Verify all system pods are running
kubectl get pods -A
```

---

## Step 6: Join Worker Nodes

### Get Join Command (Master Node)
```bash
# Get the join command (if you missed it during init)
kubeadm token create --print-join-command
```

### Join Workers to Cluster (Worker Nodes)
```bash
# Run the join command from master node output
sudo kubeadm join <MASTER_IP>:6443 \
  --token <TOKEN> \
  --discovery-token-ca-cert-hash sha256:<HASH>

# Example:
sudo kubeadm join 10.240.0.2:6443 \
  --token 7il14l.hwm2nesdzjd7iox4 \
  --discovery-token-ca-cert-hash sha256:db7edbca36d4adc4e8a26f53c93b6e7d421dcb03a18add95f01e688026e64097
```

### Verify Cluster (Master Node)
```bash
# Check all nodes are ready
kubectl get nodes -o wide

# Check pods across all nodes
kubectl get pods -A -o wide
```

---

## Step 7: Test the Cluster

### Deploy Test Application
```bash
# Create nginx deployment
kubectl create deployment nginx-test --image=nginx --replicas=3

# Expose deployment as NodePort service
kubectl expose deployment nginx-test --port=80 --type=NodePort

# Check deployment status
kubectl get deployments
kubectl get services
kubectl get pods -o wide
```

### Test Connectivity
```bash
# Get service details
kubectl get svc nginx-test

# Test service (replace with actual NodePort)
curl http://<ANY_NODE_IP>:<NODEPORT>

# Clean up test resources
kubectl delete deployment nginx-test
kubectl delete service nginx-test
```

---

## Troubleshooting Common Issues

### Kubelet Not Starting
```bash
# Check kubelet status
sudo systemctl status kubelet

# Check kubelet logs
sudo journalctl -xeu kubelet

# Common fix: Reset and rejoin
sudo kubeadm reset -f
sudo rm -rf /etc/kubernetes/ ~/.kube/
# Then re-run join command
```

### Pod Network Issues
```bash
# Check CNI pods
kubectl get pods -n kube-flannel

# Restart flannel if needed
kubectl delete pods -n kube-flannel -l app=flannel

# Check pod logs
kubectl logs -n kube-flannel <flannel-pod-name>
```

---

## Cluster Information

### Node Details
| Node | Role | IP Address | Status |
|------|------|------------|--------|
| k8s-master | Control Plane | 10.240.0.2 | Ready |
| k8s-worker-1 | Worker | 10.240.0.4 | Ready |
| k8s-worker-2 | Worker | 10.240.0.3 | Ready |
