#!/bin/bash
# Clean Test Data Script
# Removes test data from Weaviate between test runs
#
# Usage:
#   ./scripts/clean_test_data.sh              # Clean all test data
#   ./scripts/clean_test_data.sh --obsidian   # Clean only Obsidian data
#   ./scripts/clean_test_data.sh --help       # Show help

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
WEAVIATE_URL="${WEAVIATE_URL:-http://localhost:8080}"
COLLECTION_NAME="${COLLECTION_NAME:-TheMuses}"
SOURCE_TYPE="${SOURCE_TYPE:-all}"

# Help message
show_help() {
    cat << EOF
Clean Test Data Script

Usage: $0 [OPTIONS]

Options:
    --obsidian          Clean only Obsidian test data (sourceType=obsidian)
    --email             Clean only email test data (sourceType=email)
    --pdf               Clean only PDF test data (sourceType=pdf)
    --all               Clean all test data (default)
    --collection NAME   Specify collection name (default: TheMuses)
    --url URL           Weaviate URL (default: http://localhost:8080)
    --help              Show this help message

Examples:
    # Clean all test data
    $0

    # Clean only Obsidian data
    $0 --obsidian

    # Clean specific collection
    $0 --collection MyCollection --obsidian

Environment Variables:
    WEAVIATE_URL        Override Weaviate URL
    COLLECTION_NAME     Override collection name

EOF
    exit 0
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --obsidian)
            SOURCE_TYPE="obsidian"
            shift
            ;;
        --email)
            SOURCE_TYPE="email"
            shift
            ;;
        --pdf)
            SOURCE_TYPE="pdf"
            shift
            ;;
        --all)
            SOURCE_TYPE="all"
            shift
            ;;
        --collection)
            COLLECTION_NAME="$2"
            shift 2
            ;;
        --url)
            WEAVIATE_URL="$2"
            shift 2
            ;;
        --help)
            show_help
            ;;
        *)
            echo -e "${RED}Error: Unknown option $1${NC}"
            show_help
            ;;
    esac
done

# Check if Weaviate is running
echo -e "${YELLOW}Checking Weaviate connection...${NC}"
if ! curl -s "${WEAVIATE_URL}/v1/.well-known/ready" > /dev/null 2>&1; then
    echo -e "${RED}Error: Cannot connect to Weaviate at ${WEAVIATE_URL}${NC}"
    echo "Please start Weaviate with: docker-compose up weaviate -d"
    exit 1
fi
echo -e "${GREEN}✓ Weaviate is running${NC}"

# Run Python cleanup script
echo -e "${YELLOW}Cleaning test data from collection '${COLLECTION_NAME}'...${NC}"

python3 << EOF
import weaviate
from weaviate.classes.query import Filter

try:
    # Connect to Weaviate
    client = weaviate.connect_to_local(
        host="localhost",
        port=8080,
    )

    # Get collection
    collection = client.collections.get("${COLLECTION_NAME}")

    # Build filter
    source_type = "${SOURCE_TYPE}"
    if source_type == "all":
        # Delete all objects (no filter)
        result = collection.data.delete_many(where=None)
    else:
        # Delete specific sourceType
        result = collection.data.delete_many(
            where=Filter.by_property("sourceType").equal(source_type)
        )

    print(f"✓ Deleted objects from collection '${COLLECTION_NAME}'")
    if source_type != "all":
        print(f"  Filter: sourceType = {source_type}")

    client.close()

except Exception as e:
    print(f"Error: {e}")
    exit(1)
EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Test data cleaned successfully${NC}"
else
    echo -e "${RED}✗ Failed to clean test data${NC}"
    exit 1
fi

echo ""
echo "Next steps:"
echo "  - Run your tests: poetry run pytest tests/e2e/"
echo "  - Or start fresh: docker-compose down && docker-compose up -d"
