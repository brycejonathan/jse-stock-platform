# shared/scripts/setup.sh
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

# Check for required tools
check_requirements() {
    print_status "Checking requirements..."
    
    command -v docker >/dev/null 2>&1 || { 
        print_error "Docker is required but not installed. Aborting."
        exit 1
    }
    
    command -v docker-compose >/dev/null 2>&1 || {
        print_error "Docker Compose is required but not installed. Aborting."
        exit 1
    }
    
    command -v python3 >/dev/null 2>&1 || {
        print_error "Python 3 is required but not installed. Aborting."
        exit 1
    }

    command -v pip3 >/dev/null 2>&1 || {
        print_error "pip3 is required but not installed. Aborting."
        exit 1
    }
}

# Setup Python virtual environments
setup_venvs() {
    print_status "Setting up Python virtual environments..."
    
    services=("auth-service" "scraper-service" "analysis-service" "notification-service")
    
    for service in "${services[@]}"; do
        if [ -d "services/${service}" ]; then
            print_status "Setting up venv for ${service}..."
            cd "services/${service}"
            python3 -m venv venv
            source venv/bin/activate
            pip install -r requirements.txt
            deactivate
            cd ../../
        else
            print_warning "Directory for ${service} not found. Skipping..."
        fi
    done
}

# Create necessary directories
create_directories() {
    print_status "Creating necessary directories..."
    
    directories=(
        "data/postgres"
        "data/dynamodb"
        "data/redis"
        "logs/auth-service"
        "logs/scraper-service"
        "logs/analysis-service"
        "logs/notification-service"
        "logs/nginx"
    )
    
    for dir in "${directories[@]}"; do
        mkdir -p "${dir}"
        chmod 755 "${dir}"
    done
}

# Setup environment variables
setup_env() {
    print_status "Setting up environment variables..."
    
    if [ ! -f ".env" ]; then
        cp .env.example .env
        print_warning "Created .env file from template. Please update with your configurations."
    else
        print_status ".env file already exists. Skipping..."
    fi
}

# Main setup process
main() {
    print_status "Starting setup process..."
    
    check_requirements
    create_directories
    setup_env
    setup_venvs
    
    print_status "Setup completed successfully!"
    print_warning "Don't forget to update your .env file with appropriate values."
}

# Run main function
main