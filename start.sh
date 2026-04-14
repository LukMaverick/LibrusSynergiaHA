#!/bin/bash

# Librus APIX Integration - Quick Start Script

echo "🎓 Starting Librus APIX Integration Test Environment"
echo "=================================================="

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p config/custom_components
mkdir -p themes

# Copy integration files
echo "📋 Copying integration files..."
if [ -d "custom_components" ]; then
    cp -r custom_components/librus_apix config/custom_components/
    echo "✅ Integration copied successfully"
else
    echo "❌ Custom components not found!"
    exit 1
fi

# Start Docker containers
echo "🐳 Starting Docker containers..."
docker-compose up -d

# Wait a moment for containers to start
sleep 5

# Check if containers are running
if docker ps | grep -q "librus-ha-test"; then
    echo "✅ Home Assistant container is running"
    echo "🌐 Home Assistant URL: http://localhost:8123"
else
    echo "❌ Failed to start Home Assistant container"
    exit 1
fi

if docker ps | grep -q "librus-code-server"; then
    echo "✅ Code Server container is running"
    echo "💻 Code Server URL: http://localhost:8443"
    echo "🔑 Code Server Password: homeassistant"
else
    echo "⚠️  Code Server is not running (this is optional)"
fi

echo ""
echo "🎉 Environment is ready!"
echo "=================================================="
echo "1. Open Home Assistant: http://localhost:8123"
echo "2. Complete the initial setup wizard"
echo "3. Go to Configuration > Integrations"
echo "4. Add 'Librus APIX' integration"
echo "5. Enter your Librus credentials"
echo ""
echo "📝 Optional: Edit files in Code Server: http://localhost:8443"
echo ""
echo "🛑 To stop the environment:"
echo "   docker-compose down"
echo ""
echo "📋 To view logs:"
echo "   docker-compose logs -f homeassistant"