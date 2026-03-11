#!/bin/bash
# Record demo GIF — multi-provider workflow (Ollama + OpenRouter)
set -e

# Load API keys
source .env
if [ -z "$OPENROUTER_API_KEY" ]; then
    echo "Error: OPENROUTER_API_KEY not found in .env"
    exit 1
fi

# Export for binex run
export OPENROUTER_API_KEY

# Record
vhs demo.tape

echo "Done! GIF saved to assets/demo.gif"
