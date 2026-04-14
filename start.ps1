# Librus APIX Integration - Quick Start Script for Windows
# PowerShell version

Write-Host "🎓 Starting Librus APIX Integration Test Environment" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green

# Check if Docker is installed
try {
    docker --version | Out-Null
    Write-Host "✅ Docker found" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker is not installed. Please install Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Check if Docker Compose is installed
try {
    docker-compose --version | Out-Null
    Write-Host "✅ Docker Compose found" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker Compose is not installed. Please install Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Create necessary directories
Write-Host "📁 Creating directories..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "config\custom_components" | Out-Null
New-Item -ItemType Directory -Force -Path "themes" | Out-Null

# Copy integration files
Write-Host "📋 Copying integration files..." -ForegroundColor Yellow
if (Test-Path "custom_components") {
    Copy-Item -Path "custom_components\librus_apix" -Destination "config\custom_components\" -Recurse -Force
    Write-Host "✅ Integration copied successfully" -ForegroundColor Green
} else {
    Write-Host "❌ Custom components not found!" -ForegroundColor Red
    exit 1
}

# Start Docker containers
Write-Host "🐳 Starting Docker containers..." -ForegroundColor Yellow
docker-compose up -d

# Wait a moment for containers to start
Start-Sleep -Seconds 5

# Check if containers are running
$haRunning = docker ps | Select-String "librus-ha-test"
$codeRunning = docker ps | Select-String "librus-code-server"

if ($haRunning) {
    Write-Host "✅ Home Assistant container is running" -ForegroundColor Green
    Write-Host "🌐 Home Assistant URL: http://localhost:8123" -ForegroundColor Cyan
} else {
    Write-Host "❌ Failed to start Home Assistant container" -ForegroundColor Red
    exit 1
}

if ($codeRunning) {
    Write-Host "✅ Code Server container is running" -ForegroundColor Green
    Write-Host "💻 Code Server URL: http://localhost:8443" -ForegroundColor Cyan
    Write-Host "🔑 Code Server Password: homeassistant" -ForegroundColor Magenta
} else {
    Write-Host "⚠️  Code Server is not running (this is optional)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "🎉 Environment is ready!" -ForegroundColor Green
Write-Host "=================================================="
Write-Host "1. Open Home Assistant: http://localhost:8123" -ForegroundColor White
Write-Host "2. Complete the initial setup wizard" -ForegroundColor White
Write-Host "3. Go to Configuration > Integrations" -ForegroundColor White
Write-Host "4. Add 'Librus APIX' integration" -ForegroundColor White
Write-Host "5. Enter your Librus credentials" -ForegroundColor White
Write-Host ""
Write-Host "📝 Optional: Edit files in Code Server: http://localhost:8443" -ForegroundColor Cyan
Write-Host ""
Write-Host "🛑 To stop the environment:" -ForegroundColor Yellow
Write-Host "   docker-compose down" -ForegroundColor Gray
Write-Host ""
Write-Host "📋 To view logs:" -ForegroundColor Yellow
Write-Host "   docker-compose logs -f homeassistant" -ForegroundColor Gray