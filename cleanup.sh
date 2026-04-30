#!/bin/bash

echo "🧹 Cleaning up Vera AI development environment"
echo ""

# Stop and remove containers
echo "Stopping containers..."
docker-compose down

# Optional: Remove volumes
read -p "Remove volumes and data? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker-compose down -v
    echo "✅ Volumes removed"
fi

# Optional: Clean build cache
read -p "Clean Docker build cache? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker builder prune -af
    echo "✅ Build cache cleaned"
fi

echo ""
echo "🧹 Cleanup complete!"
