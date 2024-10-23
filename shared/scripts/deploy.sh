# shared/scripts/deploy.sh
#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Function to print status messages
print_status() {
    echo -e "${GREEN}[*] $1${NC}"
}

print_error() {
    echo -e "${RED}[!] $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}[!] $1${NC}"
}

# Check kubectl connection
check_kubernetes() {
    print_status "Checking Kubernetes connection..."
    
    if ! kubectl get nodes &>/dev/null; then
        print_error "Unable to connect to Kubernetes cluster. Please check your kubeconfig."
        exit 1
    fi
}

# Create namespace if it doesn't exist
create_namespace() {
    print_status "Creating namespace..."
    
    if ! kubectl get namespace jse-stock-platform &>/dev/null; then
        kubectl create namespace jse-stock-platform
    else
        print_status "Namespace already exists. Skipping..."
    fi
}

# Apply Kubernetes configurations
apply_configs() {
    print_status "Applying Kubernetes configurations..."
    
    # Apply secrets and configmaps first
    kubectl apply -f k8s/database.yaml

    # Apply services in order
    services=(
        "backend/auth-service.yaml"
        "backend/scraper-service.yaml"
        "backend/analysis-service.yaml"
        "backend/notification-service.yaml"
        "frontend/webapp.yaml"
        "ingress.yaml"
    )
    
    for service in "${services[@]}"; do
        print_status "Applying ${service}..."
        kubectl apply -f "k8s/${service}"
    done
}

# Wait for deployments to be ready
wait_for_deployments() {
    print_status "Waiting for deployments to be ready..."
    
    deployments=(
        "auth-service"
        "scraper-service"
        "analysis-service"
        "notification-service"
        "webapp"
    )
    
    for deployment in "${deployments[@]}"; do
        kubectl rollout status deployment/${deployment} -n jse-stock-platform
    done
}

# Verify service health
verify_health() {
    print_status "Verifying service health..."
    
    services=(
        "auth-service:8000"
        "scraper-service:8001"
        "analysis-service:8002"
        "notification-service:8003"
    )
    
    for service in "${services[@]}"; do
        name=$(echo $service | cut -d: -f1)
        port=$(echo $service | cut -d: -f2)
        
        if kubectl exec -it -n jse-stock-platform deploy/${name} -- curl -s http://localhost:${port}/health | grep -q "healthy"; then
            print_status "${name} is healthy"
        else
            print_warning "${name} health check failed"
        fi
    done
}

# Main deployment process
main() {
    print_status "Starting deployment process..."
    
    check_kubernetes
    create_namespace
    apply_configs
    wait_for_deployments
    verify_health
    
    print_status "Deployment completed successfully!"
}

# Run main function
main