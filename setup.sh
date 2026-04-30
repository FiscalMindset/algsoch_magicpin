#!/bin/bash

# Backend setup
echo "🔧 Setting up backend..."
cd backend
pip install -r requirements.txt
cd ..

# Frontend setup
echo "🔧 Setting up frontend..."
cd frontend
npm install
cd ..

echo ""
echo "✅ Setup complete!"
echo ""
echo "To start the services:"
echo "1. Backend: cd backend && python main.py"
echo "2. Frontend: cd frontend && npm run dev"
echo ""
echo "Or use Docker:"
echo "bash start.sh"
