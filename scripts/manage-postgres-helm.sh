#!/bin/bash
# manage-postgres-helm.sh
# Script to manage PostgreSQL Helm deployments

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to display usage
usage() {
    echo -e "${BLUE}Usage: $0 {deploy|status|upgrade|rollback|delete|logs|connect}${NC}"
    echo ""
    echo -e "${YELLOW}Commands:${NC}"
    echo "  deploy    - Deploy PostgreSQL databases using Helm"
    echo "  status    - Show status of PostgreSQL deployments"
    echo "  upgrade   - Upgrade PostgreSQL deployments"
    echo "  rollback  - Rollback PostgreSQL deployments"
    echo "  delete    - Delete PostgreSQL deployments"
    echo "  logs      - Show logs from PostgreSQL pods"
    echo "  connect   - Connect to PostgreSQL databases"
    echo ""
    exit 1
}

# Function to check prerequisites
check_prerequisites() {
    if ! command -v helm &> /dev/null; then
        echo -e "${RED}❌ Helm is not installed. Please install Helm first.${NC}"
        exit 1
    fi

    if ! kubectl cluster-info &> /dev/null; then
        echo -e "${RED}❌ kubectl is not configured or cluster is not accessible.${NC}"
        exit 1
    fi
}

# Function to deploy PostgreSQL
deploy_postgres() {
    echo -e "${GREEN}🚀 Deploying PostgreSQL databases with Helm${NC}"
    
    # Add Bitnami repo
    helm repo add bitnami https://charts.bitnami.com/bitnami
    helm repo update
    
    # Deploy Auth PostgreSQL
    echo -e "${YELLOW}🔐 Deploying Auth PostgreSQL...${NC}"
    helm upgrade --install postgres-auth bitnami/postgresql \
        --values helm-charts/postgres-auth-values.yaml \
        --set fullnameOverride=postgres-auth \
        --namespace default \
        --wait \
        --timeout 5m
    
    # Deploy Todo PostgreSQL
    echo -e "${YELLOW}📝 Deploying Todo PostgreSQL...${NC}"
    helm upgrade --install postgres-todo bitnami/postgresql \
        --values helm-charts/postgres-todo-values.yaml \
        --set fullnameOverride=postgres-todo \
        --namespace default \
        --wait \
        --timeout 5m
    
    echo -e "${GREEN}✅ PostgreSQL deployments completed!${NC}"
}

# Function to show status
show_status() {
    echo -e "${BLUE}📊 PostgreSQL Helm Deployments Status${NC}"
    echo "=========================================="
    
    # Helm releases
    echo -e "${YELLOW}Helm Releases:${NC}"
    helm list -n default | grep postgres || echo "No PostgreSQL releases found"
    echo ""
    
    # Pods
    echo -e "${YELLOW}Pods:${NC}"
    kubectl get pods -l app.kubernetes.io/name=postgresql
    echo ""
    
    # Services
    echo -e "${YELLOW}Services:${NC}"
    kubectl get services -l app.kubernetes.io/name=postgresql
    echo ""
    
    # PVCs
    echo -e "${YELLOW}Persistent Volume Claims:${NC}"
    kubectl get pvc -l app.kubernetes.io/name=postgresql
    echo ""
}

# Function to upgrade
upgrade_postgres() {
    echo -e "${YELLOW}⬆️  Upgrading PostgreSQL deployments...${NC}"
    
    helm upgrade postgres-auth bitnami/postgresql \
        --values helm-charts/postgres-auth-values.yaml \
        --set fullnameOverride=postgres-auth \
        --namespace default
    
    helm upgrade postgres-todo bitnami/postgresql \
        --values helm-charts/postgres-todo-values.yaml \
        --set fullnameOverride=postgres-todo \
        --namespace default
    
    echo -e "${GREEN}✅ Upgrades completed!${NC}"
}

# Function to rollback
rollback_postgres() {
    echo -e "${YELLOW}⬅️  Rolling back PostgreSQL deployments...${NC}"
    
    read -p "Enter revision number to rollback to (or press Enter for previous): " revision
    
    if [ -z "$revision" ]; then
        helm rollback postgres-auth
        helm rollback postgres-todo
    else
        helm rollback postgres-auth $revision
        helm rollback postgres-todo $revision
    fi
    
    echo -e "${GREEN}✅ Rollback completed!${NC}"
}

# Function to delete
delete_postgres() {
    echo -e "${RED}🗑️  This will delete PostgreSQL deployments and data!${NC}"
    read -p "Are you sure? (yes/no): " confirm
    
    if [ "$confirm" = "yes" ]; then
        helm uninstall postgres-auth -n default
        helm uninstall postgres-todo -n default
        
        # Optionally delete PVCs
        read -p "Delete persistent volumes (data will be lost)? (yes/no): " delete_pvc
        if [ "$delete_pvc" = "yes" ]; then
            kubectl delete pvc -l app.kubernetes.io/name=postgresql
        fi
        
        echo -e "${GREEN}✅ PostgreSQL deployments deleted!${NC}"
    else
        echo -e "${YELLOW}❌ Operation cancelled.${NC}"
    fi
}

# Function to show logs
show_logs() {
    echo -e "${BLUE}📋 PostgreSQL Logs${NC}"
    echo "=================="
    
    echo -e "${YELLOW}Auth PostgreSQL logs:${NC}"
    kubectl logs -l app.kubernetes.io/instance=postgres-auth --tail=50
    echo ""
    
    echo -e "${YELLOW}Todo PostgreSQL logs:${NC}"
    kubectl logs -l app.kubernetes.io/instance=postgres-todo --tail=50
}

# Function to connect to databases
connect_postgres() {
    echo -e "${BLUE}🔗 Database Connection Options${NC}"
    echo "==============================="
    
    echo "1. Connect to Auth Database"
    echo "2. Connect to Todo Database"
    echo "3. Show connection strings"
    
    read -p "Choose option (1-3): " option
    
    case $option in
        1)
            kubectl run postgres-auth-client --rm -i --restart=Never \
                --image=postgres:15 \
                --env="PGPASSWORD=authpassword" \
                -- psql -h postgres-auth -U authuser -d authdb
            ;;
        2)
            kubectl run postgres-todo-client --rm -i --restart=Never \
                --image=postgres:15 \
                --env="PGPASSWORD=todopassword" \
                -- psql -h postgres-todo -U todouser -d todoapp
            ;;
        3)
            echo -e "${GREEN}Auth Database:${NC}"
            echo "  Host: postgres-auth"
            echo "  Port: 5432"
            echo "  Database: authdb"
            echo "  Username: authuser"
            echo "  Password: authpassword"
            echo ""
            echo -e "${GREEN}Todo Database:${NC}"
            echo "  Host: postgres-todo"
            echo "  Port: 5432"
            echo "  Database: todoapp"
            echo "  Username: todouser"
            echo "  Password: todopassword"
            ;;
        *)
            echo -e "${RED}Invalid option${NC}"
            ;;
    esac
}

# Main script logic
check_prerequisites

case "${1:-}" in
    deploy)
        deploy_postgres
        ;;
    status)
        show_status
        ;;
    upgrade)
        upgrade_postgres
        ;;
    rollback)
        rollback_postgres
        ;;
    delete)
        delete_postgres
        ;;
    logs)
        show_logs
        ;;
    connect)
        connect_postgres
        ;;
    *)
        usage
        ;;
esac