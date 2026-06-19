#!/bin/bash

# WandaTools Backend - Setup Script
# Run this script to set up the development environment

set -e  # Exit on error

echo "🚀 WandaTools Backend - Setup Script"
echo "===================================="
echo ""

# Check Python version
echo "📍 Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✅ Python $python_version found"
echo ""

# Create virtual environment
echo "📍 Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi
echo ""

# Activate virtual environment
echo "📍 Activating virtual environment..."
source venv/bin/activate
echo "✅ Virtual environment activated"
echo ""

# Upgrade pip
echo "📍 Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1
echo "✅ pip upgraded"
echo ""

# Install dependencies
echo "📍 Installing dependencies from requirements.txt..."
pip install -r requirements.txt
echo "✅ Dependencies installed"
echo ""

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📍 Creating .env file..."
    cp .env.example .env
    echo "✅ .env file created from template"
    echo "⚠️  Please edit .env with your configuration:"
    echo "   - DATABASE_URL: Update with your PostgreSQL connection string"
    echo "   - SECRET_KEY: Generate a strong key with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
    echo ""
else
    echo "✅ .env file already exists"
fi
echo ""

# Create PostgreSQL database (optional)
echo "📍 PostgreSQL Database Setup (optional)"
echo "To create the database, run:"
echo "  psql"
echo "  CREATE DATABASE wandatools_db;"
echo "  \\q"
echo ""

# Display next steps
echo "✅ Setup complete!"
echo ""
echo "📝 Next steps:"
echo "1. Edit .env file with your configuration"
echo "2. Ensure PostgreSQL is running"
echo "3. Create the database: psql -c 'CREATE DATABASE wandatools_db;'"
echo "4. Start the server: uvicorn main:app --reload"
echo "5. Open http://localhost:8000/api/docs"
echo ""
echo "🎉 Ready to develop!"
