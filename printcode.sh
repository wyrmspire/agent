#!/bin/bash

# Configuration
# Add directories to ignore here.
IGNORE_DIRS=("node_modules" ".next" ".git" "__pycache__" "venv" ".venv" "env" "dist" "build" "coverage" ".pytest_cache" "tmp" "temp" ".vscode" ".idea" "target" "bin" "obj")
IGNORE_FILES=("package-lock.json" "yarn.lock" "custom_instructions.md" "printcode.sh" "project_structure.txt")
OUTPUT_PREFIX="dump"
OUTPUT_EXT=".md"
NUM_FILES=9

# Helper to construct find command ignore arguments
construct_find_args() {
    local args=""
    for ignore in "${IGNORE_DIRS[@]}"; do
        args="$args -name $ignore -prune -o"
    done
    echo "$args"
}

IGNORE_ARGS=$(construct_find_args)

echo "========================================================"
echo "generating project structure..."
echo "========================================================"

# Print directory structure
# We interpret 'ignore system stuff' as hiding the contents of ignored dirs
find . \( $IGNORE_ARGS -print0 \) | sed 's/.\///' | sed -e 's;[^/]*/;|____;g;s;____|; |;g'

echo ""
echo "========================================================"
echo "scanning files for code dump..."
echo "========================================================"

# Prepare to gather files
TMP_LIST="files_with_lines.tmp"
: > "$TMP_LIST"

# Find files, calculate line counts
# We include -type f to find files only
# We exclude the output files themselves to avoid infinite loops if re-run
find . \( $IGNORE_ARGS -type f -print \) | while read -r file; do
    # Skip output files
    if [[ "$file" == *"dump"*".md" ]]; then continue; fi
    
    # Skip specific ignored files
    filename=$(basename "$file")
    skip=0
    for ignore_f in "${IGNORE_FILES[@]}"; do
        if [[ "$filename" == "$ignore_f" ]]; then skip=1; break; fi
    done
    if [[ $skip -eq 1 ]]; then continue; fi
    
    # Check if text file (simple heuristic)
    if grep -Iq . "$file"; then
        lines=$(wc -l < "$file")
        # Handle 0-line empty files gracefully (treat as 1 to avoid division issues if all empty)
        if [[ $lines -eq 0 ]]; then lines=1; fi
        echo "$lines $file" >> "$TMP_LIST"
    fi
done

# Calculate distribution
TOTAL_LINES=$(awk '{s+=$1} END {print s+0}' "$TMP_LIST")
if [[ "$TOTAL_LINES" -eq 0 ]]; then
    echo "No lines of code found!"
    rm "$TMP_LIST"
    exit 0
fi

LINES_PER_FILE=$((TOTAL_LINES / NUM_FILES))
if [[ $LINES_PER_FILE -eq 0 ]]; then LINES_PER_FILE=1; fi

echo "Total Lines: $TOTAL_LINES"
echo "Target Lines Per File: $LINES_PER_FILE"

CURRENT_FILE_INDEX=1
CURRENT_LINE_COUNT=0

FILE_NAME="${OUTPUT_PREFIX}${CURRENT_FILE_INDEX}${OUTPUT_EXT}"
echo "# Code Dump Part $CURRENT_FILE_INDEX" > "$FILE_NAME"

while read -r lines path; do
    # Display path relative to root
    clean_path="${path#./}"
    
    # Add header and content
    {
        echo ""
        echo "## File: $clean_path"
        echo '```'
        cat "$path"
        echo ""
        echo '```'
    } >> "$FILE_NAME"
    
    CURRENT_LINE_COUNT=$((CURRENT_LINE_COUNT + lines))
    
    # Check if we should rotate to next file
    # We rotate if we exceeded target lines AND we aren't on the last file
    if [ $CURRENT_LINE_COUNT -ge $LINES_PER_FILE ] && [ $CURRENT_FILE_INDEX -lt $NUM_FILES ]; then
        echo "Created $FILE_NAME ($CURRENT_LINE_COUNT lines)"
        
        CURRENT_FILE_INDEX=$((CURRENT_FILE_INDEX + 1))
        CURRENT_LINE_COUNT=0
        FILE_NAME="${OUTPUT_PREFIX}${CURRENT_FILE_INDEX}${OUTPUT_EXT}"
        
        echo "# Code Dump Part $CURRENT_FILE_INDEX" > "$FILE_NAME"
    fi
done < "$TMP_LIST"

echo "Created $FILE_NAME ($CURRENT_LINE_COUNT lines)"
rm "$TMP_LIST"
echo "Done."
