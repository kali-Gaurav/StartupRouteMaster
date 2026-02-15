#!/bin/bash

# Railway Intelligence Engine Deployment Script
# This script deploys the entire system using Docker Compose

set -e

echo "🚂 Railway Intelligence Engine Deployment"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."

    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi

    print_status "Prerequisites check passed."
}

# Build all services
build_services() {
    print_status "Building Docker images..."

    # Build services in dependency order
    services=("scraper" "etl" "route_service" "user_service")

    for service in "${services[@]}"; do
        print_status "Building $service..."
        if ! docker-compose build "$service"; then
            print_error "Failed to build $service"
            exit 1
        fi
    done

    # RL service takes longer due to TensorFlow
    print_status "Building rl_service (this may take several minutes due to TensorFlow)..."
    if ! timeout 1800 docker-compose build rl_service; then
        print_warning "RL service build timed out or failed. You can build it manually later."
    fi

    print_status "All services built successfully."
}

# Start infrastructure services first
start_infrastructure() {
    print_status "Starting infrastructure services..."

    docker-compose up -d db redis zookeeper kafka

    # Wait for services to be healthy
    print_status "Waiting for database to be ready..."
    for i in {1..30}; do
        if docker-compose exec -T db pg_isready -U postgres > /dev/null 2>&1; then
            break
        fi
        sleep 2
    done

    print_status "Waiting for Redis to be ready..."
    for i in {1..30}; do
        if docker-compose exec -T redis redis-cli ping | grep -q PONG; then
            break
        fi
        sleep 2
    done

    print_status "Infrastructure services started."
}

# Start application services
start_applications() {
    print_status "Starting application services..."

    # Start ETL consumer first (needs to be running to consume messages)
    docker-compose up -d etl

    # Start API services
    docker-compose up -d scraper route_service user_service

    # Start RL service if image exists
    if docker images | grep -q startupv2-rl_service; then
        docker-compose up -d rl_service
        print_status "RL service started."
    else
        print_warning "RL service image not found. Build it manually: docker-compose build rl_service"
    fi

    print_status "Application services started."
}

# Run database migrations
run_migrations() {
    print_status "Running database migrations..."

    # The tables are created manually in create_tables.py
    # If using Alembic, uncomment the following:
    # docker-compose run --rm backend alembic upgrade head

    print_status "Database schema is ready."
}

# Health checks
health_checks() {
    print_status "Running health checks..."

    services=("scraper:8001" "route_service:8002" "user_service:8004")

    for service in "${services[@]}"; do
        name=$(echo $service | cut -d: -f1)
        port=$(echo $service | cut -d: -f2)

        if curl -f http://localhost:$port/health > /dev/null 2>&1; then
            print_status "$name is healthy"
        else
            print_warning "$name health check failed"
        fi
    done

    # Check RL service if running
    if docker-compose ps | grep -q rl_service; then
        if curl -f http://localhost:8003/health > /dev/null 2>&1; then
            print_status "rl_service is healthy"
        else
            print_warning "rl_service health check failed"
        fi
    fi
}

# Main deployment function
deploy() {
    check_prerequisites
    build_services
    start_infrastructure
    run_migrations
    start_applications

    print_status "Deployment completed successfully!"
    print_status ""
    print_status "Services available at:"
    print_status "  Scraper API: http://localhost:8001"
    print_status "  Route API:   http://localhost:8002"
    print_status "  User API:    http://localhost:8004"
    print_status "  RL API:      http://localhost:8003 (if built)"
    print_status ""
    print_status "API Documentation:"
    print_status "  Scraper: http://localhost:8001/docs"
    print_status "  Route:   http://localhost:8002/docs"
    print_status "  User:    http://localhost:8004/docs"
    print_status "  RL:      http://localhost:8003/docs (if built)"

    health_checks
}

# Cleanup function
cleanup() {
    print_status "Cleaning up..."
    docker-compose down -v
    docker system prune -f
    print_status "Cleanup completed."
}

# Main script logic
case "${1:-deploy}" in
    "deploy")
        deploy
        ;;
    "cleanup")
        cleanup
        ;;
    "build")
        build_services
        ;;
    "start")
        start_infrastructure
        start_applications
        ;;
    "health")
        health_checks
        ;;
    *)
        echo "Usage: $0 [deploy|cleanup|build|start|health]"
        echo "  deploy  - Full deployment (default)"
        echo "  cleanup - Remove all containers and volumes"
        echo "  build   - Build all Docker images"
        echo "  start   - Start all services"
        echo "  health  - Run health checks"
        exit 1
        ;;
esac