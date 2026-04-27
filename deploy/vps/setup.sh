#!/bin/bash

# RouteMaster VPS Setup Script
# Usage: ./setup.sh <domain_name> <email_for_ssl>

DOMAIN=$1
EMAIL=$2

if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
    echo "Usage: ./setup.sh <domain_name> <email_for_ssl>"
    exit 1
fi

echo "🚀 Starting RouteMaster VPS Setup for $DOMAIN..."

# 1. Install Docker & Docker Compose if not present
if ! [ -x "$(command -v docker)" ]; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
fi

# 2. Prepare Environment
if [ ! -f ".env" ]; then
    echo "Creating .env from example..."
    cp .env.example .env
    echo "Please update .env with your secrets before running docker-compose up."
fi

# 3. Update Nginx Config with Domain
echo "Updating Nginx configuration..."
sed -i "s/\${DOMAIN_NAME}/$DOMAIN/g" nginx/conf.d/default.conf

# 4. Get SSL Certificate (First time)
echo "Obtaining SSL certificate via Certbot..."
docker-compose run --rm --entrypoint "\
  certbot certonly --webroot -w /var/www/certbot \
    --email $EMAIL --agree-tos --no-eff-email \
    -d $DOMAIN" certbot

# 5. Start all services
echo "Starting RouteMaster Services..."
docker-compose up -d

echo "✅ Setup Complete! Your app should be live at https://$DOMAIN"
echo "Check logs with: docker-compose logs -f"
