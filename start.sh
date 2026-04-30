#!/bin/bash

echo "🚀 Starting Vera AI Full-Stack Solution"
echo ""

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    echo "Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed."
    exit 1
fi

echo "✅ Docker is available"
echo ""

# Create .env if it doesn't exist
if [ ! -f backend/.env ]; then
    echo "📝 Creating backend/.env from .env.example"
    cp backend/.env.example backend/.env
fi

if [ ! -f frontend/.env.local ]; then
    echo "📝 Creating frontend/.env.local from .env.example"
    cp frontend/.env.example frontend/.env.local
fi

echo ""
echo "📦 Starting services..."
docker-compose up --build

echo ""
echo "🎉 Vera AI is running!"
echo "🌐 Frontend: http://localhost:5173"
echo "📡 Backend: http://localhost:8000"
echo "📚 API Docs: http://localhost:8000/docs"
