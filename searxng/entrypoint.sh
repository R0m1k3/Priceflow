#!/bin/sh
# Custom entrypoint for SearXNG - creates limiter.toml before starting

# Remove any existing limiter.toml (file or directory)
rm -rf /etc/searxng/limiter.toml

# Create limiter.toml to disable bot detection
cat > /etc/searxng/limiter.toml << 'EOF'
[botdetection.ip_limit]
link_token = false

[botdetection.ip_lists]
pass_ip = [
    "0.0.0.0/0",
    "127.0.0.0/8",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "::/0"
]
block_ip = []
EOF

echo "limiter.toml created successfully"

# Execute the original entrypoint
exec /usr/local/searxng/dockerfiles/docker-entrypoint.sh
