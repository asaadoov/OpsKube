
---

# GCP Kubernetes (K8s) Terraform Setup Guide

## Overview

This Terraform setup provisions a basic Kubernetes cluster on GCP using **Compute Engine instances**:

* **One master node**
* **Multiple worker nodes** (default: 2)
* Custom **VPC network** and **subnet**
* **Firewall rules** to allow essential traffic
* Instances boot with a shared `init.sh` startup script

---

## File Structure

```
.
├── main.tf               # Core infrastructure: VPC, instances, firewall
├── variables.tf          # Input variables
├── terraform.tfvars      # Project-specific values
├── output.tf             # Public IP outputs
└── scripts/
    └── init.sh           # Startup script for master and workers
```

---

## Prerequisites

Before starting, ensure you have:

* [Terraform](https://developer.hashicorp.com/terraform/downloads) installed
* [gcloud CLI](https://cloud.google.com/sdk/docs/install) configured
* A GCP project with billing enabled
* API services enabled:

  * Compute Engine API

Enable via gcloud:

```bash
gcloud services enable compute.googleapis.com
```

Authenticate Terraform:

```bash
gcloud auth application-default login
```

---

## Setup Instructions

### 1. **Clone Your Terraform Setup**

Ensure your directory has the structure listed above.

### 2. **Review and Set Project ID**

In `terraform.tfvars`:

```hcl
project_id = "your-gcp-project-id"
```

### 3. **Initialize Terraform**

```bash
terraform init
```

This will download the required provider plugins.

### 4. **Preview the Plan**

```bash
terraform plan
```

Check that everything looks correct.

### 5. **Apply the Configuration**

```bash
terraform apply
```

Confirm with `yes` when prompted.

Terraform will provision:

* A VPC and subnet (`k8s-vpc`, `k8s-subnet`)
* A firewall rule allowing traffic on:

  * TCP ports: 22, 6443 (Kubernetes API), 10250 (Kubelet), 30000–32767 (NodePorts)
* One master instance and multiple worker instances

---

## Outputs

After a successful run, Terraform will display:

* **Master public IP**
* **Worker public IPs**

You can also get them via:

```bash
terraform output
```

---

## Testing the provisioning state

SSH into the master node:

```bash
gcloud compute ssh k8s-master --zone=us-central1-a
```

---

## Destroying Resources

To delete everything:

```bash
terraform destroy
```

