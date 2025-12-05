#!/bin/bash

# Development server runner for DinkyDash
# Runs Flask in debug mode with auto-reloading on port 5111

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting DinkyDash Development Server${NC}"
echo -e "${BLUE}=================================${NC}"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${RED}❌ Virtual environment not found!${NC}"
    echo -e "${YELLOW}Please create it with: python3 -m venv venv${NC}"
    exit 1
fi

# Activate virtual environment
echo -e "${GREEN}✓ Activating virtual environment...${NC}"
source venv/bin/activate

# Check if dependencies are installed
if ! python -c "import flask" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Flask not found. Installing dependencies...${NC}"
    pip install -r requirements.txt
fi

# Set environment variables
export FLASK_APP=app.py
export FLASK_ENV=development
export FLASK_DEBUG=1

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  .env file not found. Creating from example...${NC}"
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${GREEN}✓ Created .env file from .env.example${NC}"
        echo -e "${YELLOW}Please update .env with your configuration${NC}"
    else
        echo -e "${YELLOW}Creating basic .env file...${NC}"
        cat > .env << EOF
FLASK_ENV=development
SECRET_KEY=dev-secret-key-change-in-production
DATABASE_URL=sqlite:///dinkydash-dev.db
UPLOAD_FOLDER=dinkydash/static/uploads
MAX_CONTENT_LENGTH=5242880
EOF
        echo -e "${GREEN}✓ Created basic .env file${NC}"
    fi
fi

# Check if database exists and run migrations
if [ ! -f "dinkydash-dev.db" ]; then
    echo -e "${YELLOW}⚠️  Database not found. Initializing...${NC}"
    
    # Check if migrations folder exists
    if [ ! -d "migrations" ]; then
        echo -e "${GREEN}Running flask db init...${NC}"
        flask db init
    fi
    
    echo -e "${GREEN}Running database migrations...${NC}"
    flask db migrate -m "Initial setup"
    flask db upgrade
    echo -e "${GREEN}✓ Database initialized${NC}"
else
    # Check for pending migrations
    echo -e "${GREEN}✓ Database found. Checking for pending migrations...${NC}"
    flask db upgrade
fi

# Create upload directory if it doesn't exist
mkdir -p dinkydash/static/uploads

# Display access information
echo ""
echo -e "${BLUE}=================================${NC}"
echo -e "${GREEN}✨ Server starting on port 5111${NC}"
echo -e "${BLUE}=================================${NC}"
echo ""
echo -e "🌐 Local:    ${GREEN}http://localhost:5111${NC}"
echo -e "🌐 Network:  ${GREEN}http://$(hostname -I | awk '{print $1}'):5111${NC}" 2>/dev/null || echo -e "🌐 Network:  ${GREEN}http://127.0.0.1:5111${NC}"
echo ""
echo -e "📝 Debug Mode: ${GREEN}ON${NC}"
echo -e "🔄 Auto-reload: ${GREEN}ON${NC}"
echo -e "🗄️  Database: ${GREEN}sqlite:///dinkydash-dev.db${NC}"
echo ""
echo -e "${YELLOW}Press CTRL+C to stop the server${NC}"
echo -e "${BLUE}=================================${NC}"
echo ""

# Run the Flask development server
flask run --host=0.0.0.0 --port=5111 --reload --debugger