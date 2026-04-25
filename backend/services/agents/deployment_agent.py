"""
Deployment Agent
===============
Prepares environment for VPS deployment.
"""
import logging
import os
import subprocess
from typing import Dict, Any, Optional
from services.agents.base_agent import BaseAgent

logger = logging.getLogger("agent.deployment")

class DeploymentAgent(BaseAgent):
    """Handles deployment preparation and execution"""
    name = "DeploymentAgent"
    description = "Prepares environment for VPS deployment"
    category = "deployment"

    async def on_start(self):
        """Initialize deployment agent"""
        logger.info("🚀 DeploymentAgent starting...")
        return True
    
    async def validate_environment(self, **kwargs) -> Dict[str, Any]:
        """Validate production environment"""
        missing_vars = []
        required_vars = [
            "DATABASE_URL", "REDIS_URL", "SUPABASE_URL", "SUPABASE_KEY",
            "RAPIDAPI_KEY", "RAPIDAPI_HOST"
        ]
        
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        return {
            "operation": "environment_validation",
            "status": "passed" if not missing_vars else "failed",
            "missing_variables": missing_vars,
            "environment": os.getenv("ENVIRONMENT", "development"),
            "recommendations": [
                "Set all required environment variables",
                "Use .env.production for production",
                "Test database connections before deployment"
            ] if missing_vars else [
                "Environment ready for deployment",
                "Consider using Docker for consistency",
                "Set up monitoring and alerts"
            ]
        }
    
    async def generate_deployment_checklist(self, **kwargs) -> Dict[str, Any]:
        """Generate deployment checklist"""
        checklist = [
            {"task": "Environment variables configured", "status": "pending"},
            {"task": "Database migrations applied", "status": "pending"},
            {"task": "Docker images built", "status": "pending"},
            {"task": "SSL certificates configured", "status": "pending"},
            {"task": "Domain DNS configured", "status": "pending"},
            {"task": "Backup system configured", "status": "pending"},
            {"task": "Monitoring configured", "status": "pending"},
            {"task": "Load testing completed", "status": "pending"},
            {"task": "Security audit completed", "status": "pending"},
            {"task": "Rollback plan tested", "status": "pending"},
        ]
        
        return {
            "operation": "deployment_checklist",
            "status": "completed",
            "checklist": checklist,
            "total_tasks": len(checklist),
            "pending_tasks": len([t for t in checklist if t["status"] == "pending"])
        }
    
    async def generate_docker_compose(self, **kwargs) -> Dict[str, Any]:
        """Generate Docker Compose configuration"""
        docker_compose = """version: '3.8'

services:
  backend:
    build: 
      context: ./backend
      dockerfile: Dockerfile.prod
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_KEY=${SUPABASE_KEY}
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - backend
"""
        
        return {
            "operation": "generate_docker_compose",
            "status": "completed",
            "configuration": docker_compose,
            "file_suggested": "docker-compose.prod.yml",
            "notes": [
                "Update environment variables for your VPS",
                "Configure SSL certificates in nginx",
                "Set up database backups"
            ]
        }
    
    async def generate_nginx_config(self, **kwargs) -> Dict[str, Any]:
        """Generate Nginx configuration"""
        nginx_config = """events {
    worker_connections 1024;
}

http {
    upstream backend {
        server backend:8000;
    }

    server {
        listen 80;
        server_name yourdomain.com;
        
        location / {
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
        
        location /health {
            proxy_pass http://backend/health;
            access_log off;
        }
    }
    
    # SSL configuration (uncomment and configure)
    # server {
    #     listen 443 ssl;
    #     server_name yourdomain.com;
    #     
    #     ssl_certificate /etc/nginx/ssl/yourdomain.crt;
    #     ssl_certificate_key /etc/nginx/ssl/yourdomain.key;
    #     
    #     location / {
    #         proxy_pass http://backend;
    #         proxy_set_header Host $host;
    #         proxy_set_header X-Real-IP $remote_addr;
    #         proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    #         proxy_set_header X-Forwarded-Proto $scheme;
    #     }
    # }
}
"""
        
        return {
            "operation": "generate_nginx_config",
            "status": "completed",
            "configuration": nginx_config,
            "file_suggested": "nginx.conf",
            "notes": [
                "Replace 'yourdomain.com' with your actual domain",
                "Configure SSL certificates for HTTPS",
                "Adjust worker_connections based on expected traffic"
            ]
        }
    
    async def execute(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute deployment task"""
        ctx = context or {}
        task = str(ctx.get("task", ctx.get("action", ""))).strip()
        task_lower = task.lower()
        
        if "validate" in task_lower or "environment" in task_lower:
            return await self.validate_environment(**ctx)
        elif "checklist" in task_lower:
            return await self.generate_deployment_checklist(**ctx)
        elif "docker" in task_lower:
            return await self.generate_docker_compose(**ctx)
        elif "nginx" in task_lower:
            return await self.generate_nginx_config(**ctx)
        elif "deploy" in task_lower or "vps" in task_lower:
            # Comprehensive deployment preparation
            validation = await self.validate_environment(**ctx)
            checklist = await self.generate_deployment_checklist(**ctx)
            docker = await self.generate_docker_compose(**ctx)
            nginx = await self.generate_nginx_config(**ctx)
            
            return {
                "operation": "deployment_preparation",
                "status": "completed",
                "validation": validation,
                "checklist": checklist,
                "docker_config": docker,
                "nginx_config": nginx,
                "next_steps": [
                    "1. Set up VPS server with Docker",
                    "2. Configure environment variables",
                    "3. Build and deploy containers",
                    "4. Configure DNS and SSL",
                    "5. Run smoke tests"
                ]
            }
        else:
            return {
                "operation": "unknown",
                "status": "failed",
                "error": f"Unknown deployment task: {task}"
            }