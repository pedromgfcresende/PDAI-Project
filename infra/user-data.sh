#!/bin/bash
set -euo pipefail

# Log everything for debugging
exec > /var/log/user-data.log 2>&1
echo "=== Starting setup at $(date) ==="

# --- Install Docker ---
dnf update -y
dnf install -y docker git nginx
systemctl enable docker
systemctl start docker
usermod -aG docker ec2-user

# Install Docker Compose plugin
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# --- Clone the project ---
cd /home/ec2-user
git clone ${repo_url} app
cd app

# --- Create .env file ---
cat > .env << 'ENVEOF'
ANTHROPIC_API_KEY=${anthropic_key}
GROQ_API_KEY=${groq_key}
GOOGLE_AI_API_KEY=${google_ai_key}
GITHUB_TOKEN=${github_token}
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=${langchain_key}
LANGCHAIN_PROJECT=${project_name}
DB_PASSWORD=${db_password}
ENVEOF

# --- Update docker-compose for production ---
# Change port mapping from 5433 to 5432 (no conflict on EC2)
sed -i 's/5433:5432/5432:5432/' docker-compose.yml

# Add the API service to docker-compose
cat >> docker-compose.yml << 'COMPOSEEOF'

  api:
    build: .
    container_name: trends-api
    restart: unless-stopped
    ports:
      - "8000:8000"
    env_file: .env
    environment:
      DB_HOST: postgres
      DB_PORT: 5432
    depends_on:
      postgres:
        condition: service_healthy
COMPOSEEOF

# --- Start everything ---
chown -R ec2-user:ec2-user /home/ec2-user/app
docker compose up -d --build

# --- Setup nginx to serve dashboard on port 80 ---
cat > /etc/nginx/conf.d/dashboard.conf << 'NGINXEOF'
server {
    listen 80;
    server_name _;

    # Dashboard static files
    location / {
        root /home/ec2-user/app/dashboard;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # Proxy API requests
    location /health { proxy_pass http://127.0.0.1:8000; }
    location /ingest { proxy_pass http://127.0.0.1:8000; }
    location /filter { proxy_pass http://127.0.0.1:8000; }
    location /signals { proxy_pass http://127.0.0.1:8000; }
    location /reports { proxy_pass http://127.0.0.1:8000; }
    location /items { proxy_pass http://127.0.0.1:8000; }
    location /pipeline { proxy_pass http://127.0.0.1:8000; }
}
NGINXEOF

systemctl enable nginx
systemctl start nginx

echo "=== Setup complete at $(date) ==="
