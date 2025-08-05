provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

resource "google_compute_network" "vpc_network" {
  name = "k8s-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "subnet" {
  name          = "k8s-subnet"
  ip_cidr_range = "10.240.0.0/16"
  region        = var.region
  network       = google_compute_network.vpc_network.id
}

resource "google_compute_firewall" "k8s-firewall" {
  name    = "k8s-allow"
  network = google_compute_network.vpc_network.name

  allow {
    protocol = "tcp"
    ports    = ["22", "6443", "10250", "30000-32767"]
  }

  source_ranges = ["0.0.0.0/0"]
}

# Master Node
resource "google_compute_instance" "master" {
  name         = "k8s-master"
  machine_type = "e2-medium"
  zone         = var.zone

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2204-lts"
    }
  }

  network_interface {
    subnetwork    = google_compute_subnetwork.subnet.name
    access_config {}
  }

  metadata_startup_script = file("scripts/init.sh")
  tags                    = ["k8s"]
}

# Worker Nodes
resource "google_compute_instance" "worker" {
  count        = var.worker_count
  name         = "k8s-worker-${count.index+1}"
  machine_type = "e2-medium"
  zone         = var.zone

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2204-lts"
    }
  }

  network_interface {
    subnetwork    = google_compute_subnetwork.subnet.name
    access_config {}
  }

  metadata_startup_script = file("scripts/init.sh")
  tags                    = ["k8s"]
}
