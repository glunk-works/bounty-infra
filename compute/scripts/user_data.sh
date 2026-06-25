#!/bin/bash
set -e

# Redirect output for setup debugging
exec > >(tee /var/log/user-data.log|logger -t user-data -s2) 2>&1

echo "Starting security tools installation..."

# Update package lists
apt-get update -y
apt-get upgrade -y

# Install essential foundational tools
apt-get install -y \
    curl \
    git \
    unzip \
    build-essential \
    jq \
    tmux \
    python3-pip \
    python3-venv \
    libpcap-dev

# Install Go Language Environment
GO_VERSION="1.22.2"
curl -OL "https://golang.org/dl/go${GO_VERSION}.linux-amd64.tar.gz"
tar -C /usr/local -xf "go${GO_VERSION}.linux-amd64.tar.gz"
rm "go${GO_VERSION}.linux-amd64.tar.gz"

# Configure environment variables for all system profiles
cat << 'EOF' >> /etc/profile.d/go.sh
export PATH=$PATH:/usr/local/go/bin
export GOPATH=/usr/share/go
export PATH=$PATH:$GOPATH/bin
EOF

source /etc/profile.d/go.sh

# Install Go-based tools securely via native build pipelines
echo "Installing projectdiscovery utilities..."
go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest
go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest

echo "Installing web assessment tools..."
go install -v github.com/ffuf/ffuf/v2@latest
go install -v github.com/OWASP/Amass/v4/...@latest

# Align binaries into default system binary routes
cp /usr/share/go/bin/* /usr/local/bin/

# Configure the local storage environment for findings sync
mkdir -p /opt/findings

echo "Environment provisioning completed successfully."