#!/bin/bash
# deploy-postgres-helm.sh
# Script to deploy PostgreSQL databases using Helm charts

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting PostgreSQL Helm Deployment${NC}"

# Check if helm is installed
if ! command -v helm &> /dev/null; then
    echo -e "${RED}❌ Helm is not installed. Please install Helm first.${NC}"
    exit 1
fi

# Check if kubectl is configured
if ! kubectl cluster-info &> /dev/null; then
    echo -e "${RED}❌ kubectl is not configured or cluster is not accessible.${NC}"
    exit 1
fi

echo -e "${YELLOW}📦 Adding Bitnami Helm repository...${NC}"
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

echo -e "${YELLOW}🗑️  Removing existing PostgreSQL deployments (if any)...${NC}"
kubectl delete deployment postgres-auth postgres-todo --ignore-not-found=true
kubectl delete service postgres-auth postgres-todo --ignore-not-found=true
kubectl delete pvc postgres-auth-pvc postgres-todo-pvc --ignore-not-found=true
kubectl delete configmap postgres-auth-config postgres-todo-config --ignore-not-found=true
kubectl delete secret postgres-auth-secret postgres-todo-secret --ignore-not-found=true

echo -e "${YELLOW}⏳ Waiting for resources to be cleaned up...${NC}"
sleep 10

echo -e "${YELLOW}🔐 Deploying PostgreSQL for Auth Service...${NC}"
helm upgrade --install postgres-auth bitnami/postgresql \
  --values helm-charts/postgres-auth-values.yaml \
  --set fullnameOverride=postgres-auth \
  --namespace default \
  --wait \
  --timeout 5m

echo -e "${YELLOW}📝 Deploying PostgreSQL for Todo Service...${NC}"
helm upgrade --install postgres-todo bitnami/postgresql \
  --values helm-charts/postgres-todo-values.yaml \
  --set fullnameOverride=postgres-todo \
  --namespace default \
  --wait \
  --timeout 5m

echo -e "${YELLOW}🔍 Checking deployment status...${NC}"

# Wait for pods to be ready
echo -e "${YELLOW}⏳ Waiting for PostgreSQL pods to be ready...${NC}"
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=postgresql -l app.kubernetes.io/instance=postgres-auth --timeout=300s
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=postgresql -l app.kubernetes.io/instance=postgres-todo --timeout=300s

echo -e "${GREEN}✅ PostgreSQL deployments completed successfully!${NC}"

echo -e "${YELLOW}📊 Deployment Summary:${NC}"
echo "===================="

echo -e "${GREEN}Auth PostgreSQL:${NC}"
kubectl get pods -l app.kubernetes.io/instance=postgres-auth
kubectl get pvc -l app.kubernetes.io/instance=postgres-auth
kubectl get svc -l app.kubernetes.io/instance=postgres-auth

echo -e "${GREEN}Todo PostgreSQL:${NC}"
kubectl get pods -l app.kubernetes.io/instance=postgres-todo
kubectl get pvc -l app.kubernetes.io/instance=postgres-todo
kubectl get svc -l app.kubernetes.io/instance=postgres-todo

echo -e "${YELLOW}🔗 Connection Information:${NC}"
echo "===================="
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

echo -e "${YELLOW}🧪 Testing Database Connectivity:${NC}"
echo "===================="

# Test auth database
echo -e "${YELLOW}Testing Auth Database...${NC}"
kubectl run postgres-auth-test --rm -i --restart=Never --image=postgres:15 --env="PGPASSWORD=authpassword" -- psql -h postgres-auth -U authuser -d authdb -c "SELECT version();" || echo -e "${RED}❌ Auth DB connection failed${NC}"

# Test todo database  
echo -e "${YELLOW}Testing Todo Database...${NC}"
kubectl run postgres-todo-test --rm -i --restart=Never --image=postgres:15 --env="PGPASSWORD=todopassword" -- psql -h postgres-todo -U todouser -d todoapp -c "SELECT version();" || echo -e "${RED}❌ Todo DB connection failed${NC}"

echo -e "${GREEN}🎉 All done! PostgreSQL databases are ready for your microservices.${NC}"
echo -e "${YELLOW}💡 Next steps:${NC}"
echo "1. Update your application deployments to use the new service names"
echo "2. Deploy your auth-service and todo-service"
echo "3. Test the complete application stack"