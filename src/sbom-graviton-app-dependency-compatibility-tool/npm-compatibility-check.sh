#!/bin/bash
# npm-compatibility-check.sh
# This script performs npm install and test checks and outputs results in JSON format.
# assuming package.json exits in directory (temp)

INSTALL_LOG="temp_npm_install.log"
TEST_LOG="temp_npm_test.log"
ERROR_SNIPPET_LOG="temp_error_snippet.log"
NATIVE_BUILD_DETECTED="No"
LOAD_TEST_SUCCESS="No" #default
INSTALL_STATUS="Failed" #default
ERROR_DETAILS="N/A"


rm -f "$INSTALL_LOG" "$TEST_LOG" "$ERROR_SNIPPET_LOG"

# run npm install

echo "Running npm install..." >&2

npm install --silent > "$INSTALL_LOG" 2>&1
NPM_INSTALL_EXIT_CODE=$?

if [ $NPM_INSTALL_EXIT_CODE -eq 0 ]; then
    INSTALL_STATUS="Success"
    echo "npm install successful." >&2

    # native build comp
    if find node_modules -type f -name "*.node" -print -quit | grep -q .; then
        NATIVE_BUILD_DETECTED="Yes"
        echo "Native build detected (e.g., .node files)." >&2
    fi

    # npm test
    # checking if a 'test' script exists in package.json
    if jq -e '.scripts.test' package.json > /dev/null 2>&1; then
        echo "Running npm test..." >&2
        npm test --silent > "$TEST_LOG" 2>&1
        NPM_TEST_EXIT_CODE=$?
        if [ $NPM_TEST_EXIT_CODE -eq 0 ]; then
            LOAD_TEST_SUCCESS="Yes"
            echo "npm test successful." >&2
        else
            LOAD_TEST_SUCCESS="No"
            echo "npm test failed." >&2
            
            head -n 20 "$TEST_LOG" > "$ERROR_SNIPPET_LOG"
            echo "..." >> "$ERROR_SNIPPET_LOG"
            tail -n 20 "$TEST_LOG" >> "$ERROR_SNIPPET_LOG"
        fi
    else
        echo "No 'test' script found in package.json. Skipping npm test." >&2
        LOAD_TEST_SUCCESS="N/A - No test script" 
    fi

else
    echo "npm install failed." >&2
    
    head -n 20 "$INSTALL_LOG" > "$ERROR_SNIPPET_LOG"
    echo "..." >> "$ERROR_SNIPPET_LOG"
    tail -n 20 "$INSTALL_LOG" >> "$ERROR_SNIPPET_LOG"
fi


if [ -s "$ERROR_SNIPPET_LOG" ]; then 
    ERROR_DETAILS=$(cat "$ERROR_SNIPPET_LOG")
else
    
    if [ -s "$INSTALL_LOG" ]; then
        
        ERROR_DETAILS=$(head -n 50 "$INSTALL_LOG" | tr -d '\n' | cut -c 1-500)...
        
        if [ "$INSTALL_STATUS" == "Failed" ] && [ -z "$ERROR_DETAILS" ]; then
            ERROR_DETAILS="npm install failed with no specific output captured."
        fi
    fi
fi

#output results (json)
JSON_OUTPUT=$(jq -n \
                  --arg install_status "$INSTALL_STATUS" \
                  --arg error_details "$ERROR_DETAILS" \
                  --arg native_build_detected "$NATIVE_BUILD_DETECTED" \
                  --arg load_test_success "$LOAD_TEST_SUCCESS" \
                  '{install_status: $install_status, error_details: $error_details, native_build_detected: $native_build_detected, load_test_success: $load_test_success}')

echo "$JSON_OUTPUT"

rm -f "$INSTALL_LOG" "$TEST_LOG" "$ERROR_SNIPPET_LOG"

exit 0 