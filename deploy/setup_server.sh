#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${GREEN}Starting Server Setup...${NC}"

# 1. Update System
echo "Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

# 2. Install Dependencies
echo "Installing dependencies..."
sudo apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    ufw \
    fail2ban

# 3. Install Docker
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
else
    echo "Docker already installed."
fi

# 4. Configure Firewall (UFW)
echo "Configuring Firewall..."
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

# 5. Create App Directory
APP_DIR="/opt/parsefin"
echo "Setting up app directory at $APP_DIR..."
sudo mkdir -p $APP_DIR
sudo chown -R $USER:$USER $APP_DIR

echo -e "${GREEN}Server Setup Complete!${NC}"
echo "Next steps: Clone repo into $APP_DIR and run deploy/init_database.sh"
