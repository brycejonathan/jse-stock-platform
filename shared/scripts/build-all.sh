# shared/scripts/build-all.sh
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

# Build Docker images
build_images() {
    print_status "Building Docker images..."
    
    services=(
        "auth-service"
        "scraper-service"
        "analysis-service"
        "notification-service"
    )
    
    for service in "${services[@]}"; do
        print_status "Building ${service}..."
        docker build -t "jse-stock-platform/${service}:latest" "./services/${service}"
    done
    
    print_status "Building frontend webapp..."
    docker build -t "jse-stock-platform/webapp:latest" "./frontend/web-app"
}

# Run tests
run_tests() {
    print_status "Running tests..."
    
    services=(
        "auth-service"
        "scraper-service"
        "analysis-service"
        "notification-service"
    )
    
    for service in "${services[@]}"; do
        print_status "Testing ${service}..."
        cd "services/${service}"
        python -m pytest tests/
        cd ../../
    done
    
    print_status "Testing frontend..."
    cd frontend/web-app
    npm run test
    cd ../../
}

# Check code quality
check_code_quality() {
    print_status "Checking code quality..."
    
    services=(
        "auth-service"
        "scraper-service"
        "analysis-service"
        "notification-service"
    )
    
    for service in "${services[@]}"; do
        print_status "Checking ${service}..."
        cd "services/${service}"
        flake8 src/
        black --check src/
        isort --check-only src/
        cd ../../
    done
    
    print_status "Checking frontend..."
    cd frontend/web-app
    npm run lint
    npm run prettier:check
    cd ../../
}

# Tag images for deployment
tag_images() {
    print_status "Tagging images..."
    
    # Get current timestamp for versioning
    timestamp=$(date +%Y%m%d-%H%M%S)
    
    services=(
        "auth-service"
        "scraper-service"
        "analysis-service"
        "notification-service"
        "webapp"
    )
    
    for service in "${services[@]}"; do
        docker tag "jse-stock-platform/${service}:latest" "jse-stock-platform/${service}:${timestamp}"
    done
}

# Push images to registry
push_images() {
    print_status "Pushing images to registry..."
    
    services=(
        "auth-service"
        "scraper-service"
        "analysis-service"
        "notification-service"
        "webapp"
    )
    
    for service in "${services[@]}"; do
        docker push "jse-stock-platform/${service}:latest"
    done
}

# Main build process
main() {
    print_status "Starting build process..."
    
    # Check if running in CI environment
    if [ -n "$CI" ]; then
        print_status "Running in CI environment..."
    fi
    
    check_code_quality
    run_tests
    build_images
    tag_images
    
    # Only push images if explicitly requested or in CI
    if [ "$1" == "--push" ] || [ -n "$CI" ]; then
        push_images
    fi
    
    print_status "Build completed successfully!"
}

# Run main function with all arguments
main "$@"