#!/bin/bash
# Setup test data for Mnemosyne development
# Creates a smaller dataset for faster testing during development

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔧 Setting up Mnemosyne test data${NC}"
echo "================================================"
echo ""

# Source paths
VAULT_SOURCE="/mnt/sda1/digital_vault/02_active/notes/Obsidian"
EMAIL_SOURCE="/mnt/sda1/digital_vault/raw_email_archive"
PDF_SOURCE="/mnt/sda1/digital_vault/01_inbox/scans"

# Test data destination
TEST_DATA_DIR="/home/tgrytnes/projects/Mnemosyne/test_data"
TEST_VAULT="$TEST_DATA_DIR/test_vault"
TEST_EMAILS="$TEST_DATA_DIR/test_emails"
TEST_PDFS="$TEST_DATA_DIR/test_pdfs"

# Configuration
VAULT_SAMPLE_SIZE=50      # Number of markdown files to copy
EMAIL_SAMPLE_SIZE=100     # Number of emails to copy
COPY_ALL_PDFS=true        # Copy all PDFs (only 6)

echo "Configuration:"
echo "  Vault sample: $VAULT_SAMPLE_SIZE files"
echo "  Email sample: $EMAIL_SAMPLE_SIZE files"
echo "  PDFs: All (6 files)"
echo ""

# Create test data directories
echo -e "${BLUE}Creating test data directories...${NC}"
mkdir -p "$TEST_VAULT"
mkdir -p "$TEST_EMAILS"
mkdir -p "$TEST_PDFS"
echo -e "${GREEN}✓${NC} Directories created"
echo ""

# Copy sample Obsidian vault files
echo -e "${BLUE}Copying sample vault files...${NC}"
if [ -d "$VAULT_SOURCE" ]; then
    # Find markdown files (excluding hidden and system files)
    # Use null separator to handle special characters
    FILE_COUNT=0

    find "$VAULT_SOURCE" -type f -name "*.md" \
        ! -path "*/\.*" \
        ! -name ".*" \
        -print0 | head -z -n $VAULT_SAMPLE_SIZE | while IFS= read -r -d '' file; do

        # Preserve directory structure relative to vault root
        REL_PATH=$(realpath --relative-to="$VAULT_SOURCE" "$file")
        DEST_DIR="$TEST_VAULT/$(dirname "$REL_PATH")"

        mkdir -p "$DEST_DIR"
        cp "$file" "$DEST_DIR/" 2>/dev/null || {
            # Skip files with problematic characters
            echo "Skipping: $REL_PATH"
            continue
        }
        ((FILE_COUNT++))
    done

    # Copy .obsidian config directory if it exists
    if [ -d "$VAULT_SOURCE/.obsidian" ]; then
        cp -r "$VAULT_SOURCE/.obsidian" "$TEST_VAULT/" 2>/dev/null || true
        echo -e "${GREEN}✓${NC} Copied .obsidian config"
    fi

    # Count actually copied files
    ACTUAL_COUNT=$(find "$TEST_VAULT" -type f -name "*.md" | wc -l)
    echo -e "${GREEN}✓${NC} Copied $ACTUAL_COUNT markdown files"
else
    echo -e "${YELLOW}⚠${NC} Vault source not found: $VAULT_SOURCE"
fi
echo ""

# Copy sample emails
echo -e "${BLUE}Copying sample emails...${NC}"
if [ -d "$EMAIL_SOURCE" ]; then
    # Try Posteo folder first, then Google
    EMAIL_DIR=""
    if [ -d "$EMAIL_SOURCE/Posteo" ]; then
        EMAIL_DIR="$EMAIL_SOURCE/Posteo"
    elif [ -d "$EMAIL_SOURCE/Google" ]; then
        EMAIL_DIR="$EMAIL_SOURCE/Google"
    fi

    if [ -n "$EMAIL_DIR" ]; then
        # Find .eml files
        EMAIL_COUNT=0

        find "$EMAIL_DIR" -type f -name "*.eml" -print0 | head -z -n $EMAIL_SAMPLE_SIZE | while IFS= read -r -d '' email; do
            # Preserve directory structure
            REL_PATH=$(realpath --relative-to="$EMAIL_DIR" "$email")
            DEST_DIR="$TEST_EMAILS/$(dirname "$REL_PATH")"

            mkdir -p "$DEST_DIR"
            cp "$email" "$DEST_DIR/" 2>/dev/null || continue
            ((EMAIL_COUNT++))
        done

        ACTUAL_EMAIL_COUNT=$(find "$TEST_EMAILS" -type f -name "*.eml" | wc -l)
        echo -e "${GREEN}✓${NC} Copied $ACTUAL_EMAIL_COUNT email files"
    else
        echo -e "${YELLOW}⚠${NC} No email folders found (Posteo/Google)"
    fi

    # Also copy the cleaned TSV if it exists
    if [ -f "/mnt/sda1/digital_vault/cleaned_emails_full.tsv" ]; then
        # Copy first 1000 lines (header + 999 emails)
        head -n 1000 /mnt/sda1/digital_vault/cleaned_emails_full.tsv > "$TEST_DATA_DIR/cleaned_emails_sample.tsv"
        echo -e "${GREEN}✓${NC} Created cleaned_emails_sample.tsv (1000 lines)"
    fi
else
    echo -e "${YELLOW}⚠${NC} Email source not found: $EMAIL_SOURCE"
fi
echo ""

# Copy all PDFs (only 6)
echo -e "${BLUE}Copying PDF scans...${NC}"
if [ -d "$PDF_SOURCE" ]; then
    PDF_COUNT=0

    find "$PDF_SOURCE" -type f \( -name "*.pdf" -o -name "*.PDF" \) -print0 | while IFS= read -r -d '' pdf; do
        cp "$pdf" "$TEST_PDFS/" 2>/dev/null || continue
        ((PDF_COUNT++))
    done

    ACTUAL_PDF_COUNT=$(find "$TEST_PDFS" -type f \( -name "*.pdf" -o -name "*.PDF" \) | wc -l)
    echo -e "${GREEN}✓${NC} Copied $ACTUAL_PDF_COUNT PDF files"
else
    echo -e "${YELLOW}⚠${NC} PDF source not found: $PDF_SOURCE"
fi
echo ""

# Create a README in test_data
cat > "$TEST_DATA_DIR/README.md" << 'EOF'
# Test Data for Mnemosyne Development

This directory contains a smaller sample of data for faster testing during development.

## Contents

### test_vault/ (50 markdown files)
Sample from: `/mnt/sda1/digital_vault/02_active/notes/Obsidian/`
- Representative sample of ~50 markdown files
- Preserves directory structure
- Includes .obsidian config

**Use for:** Testing Story 000 (Obsidian Vault Ingestion)

### test_emails/ (100 emails)
Sample from: `/mnt/sda1/digital_vault/raw_email_archive/`
- ~100 .eml files from Posteo or Google
- Preserves folder structure

**Use for:** Testing Story 001 (Email Archive Ingestion)

### test_pdfs/ (all PDFs)
All PDFs from: `/mnt/sda1/digital_vault/01_inbox/scans/`
- All scanned documents (small dataset)

**Use for:** Testing Story 003 (PDF/OCR Ingestion)

### cleaned_emails_sample.tsv (1000 rows)
First 1000 lines from cleaned_emails_full.tsv
- Header + 999 emails
- Pre-processed format

**Use for:** Alternative email ingestion testing

## Environment Variables for Testing

Add to your `.env`:

```bash
# Test data paths (use these during development)
TEST_VAULT_PATH=/home/tgrytnes/projects/Mnemosyne/test_data/test_vault
TEST_EMAIL_PATH=/home/tgrytnes/projects/Mnemosyne/test_data/test_emails
TEST_PDF_PATH=/home/tgrytnes/projects/Mnemosyne/test_data/test_pdfs

# Production paths (use these for full ingestion)
VAULT_PATH=/mnt/sda1/digital_vault/02_active/notes/Obsidian
EMAIL_ARCHIVE_PATH=/mnt/sda1/digital_vault/raw_email_archive
PDF_SCAN_PATH=/mnt/sda1/digital_vault/01_inbox/scans
```

## Testing Workflow

1. **Development Phase**: Use test data
   ```bash
   python -m Aletheia.ingestor --vault test_data/test_vault
   ```

2. **Validation Phase**: Verify with test data
   ```bash
   pytest tests/integration/test_weaviate_integration.py -v
   ```

3. **Production Run**: Switch to full data
   ```bash
   python -m Aletheia.ingestor --vault $VAULT_PATH
   ```

## Re-generate Test Data

To create a fresh sample:
```bash
./setup_test_data.sh
```

## Expected Results

### TheMuses (Obsidian vault)
- Files: ~50
- Expected chunks: ~150-250
- Ingestion time: ~2-3 minutes

### TheLethe (Emails)
- Emails: ~100
- Expected chunks: ~200-400
- Ingestion time: ~3-5 minutes

### TheLethe (PDFs)
- PDFs: ~6
- Expected chunks: varies by content
- Ingestion time: ~1-2 minutes

## Notes

- Test data is ~1/10th the size of production data
- Allows rapid iteration during development
- Switch to production paths when ready for full ingestion
- Test data is NOT tracked in git (.gitignore)
EOF

echo -e "${GREEN}✓${NC} Created test_data/README.md"
echo ""

# Add to .gitignore
if [ -f /home/tgrytnes/projects/Mnemosyne/.gitignore ]; then
    if ! grep -q "^test_data/" /home/tgrytnes/projects/Mnemosyne/.gitignore 2>/dev/null; then
        echo "test_data/" >> /home/tgrytnes/projects/Mnemosyne/.gitignore
        echo -e "${GREEN}✓${NC} Added test_data/ to .gitignore"
    fi
else
    echo "test_data/" > /home/tgrytnes/projects/Mnemosyne/.gitignore
    echo -e "${GREEN}✓${NC} Created .gitignore with test_data/"
fi

# Summary
echo "================================================"
echo -e "${GREEN}✓ Test data setup complete!${NC}"
echo ""
echo "Summary:"
echo "  Location: $TEST_DATA_DIR"
VAULT_COUNT=$(find "$TEST_DATA_DIR" -type f -name "*.md" 2>/dev/null | wc -l)
EMAIL_COUNT=$(find "$TEST_DATA_DIR" -type f -name "*.eml" 2>/dev/null | wc -l)
PDF_COUNT=$(find "$TEST_DATA_DIR" -type f \( -name "*.pdf" -o -name "*.PDF" \) 2>/dev/null | wc -l)

echo "  Markdown files: $VAULT_COUNT"
echo "  Email files: $EMAIL_COUNT"
echo "  PDF files: $PDF_COUNT"

# Check TSV
if [ -f "$TEST_DATA_DIR/cleaned_emails_sample.tsv" ]; then
    TSV_LINES=$(wc -l < "$TEST_DATA_DIR/cleaned_emails_sample.tsv")
    echo "  TSV lines: $TSV_LINES"
fi

echo ""
echo "Next steps:"
echo "  1. Review: cat test_data/README.md"
echo "  2. Create .env with TEST_* paths"
echo "  3. Start development with Story 000"
echo "  4. Use test data for faster iteration"
echo ""
