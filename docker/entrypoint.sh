#!/bin/bash
set -e

AGENT_TYPE="${BINEX_AGENT_TYPE:-}"

case "$AGENT_TYPE" in
    planner)
        MODULE="binex.agents.planner.app:app"
        ;;
    researcher)
        MODULE="binex.agents.researcher.app:app"
        ;;
    validator)
        MODULE="binex.agents.validator.app:app"
        ;;
    summarizer)
        MODULE="binex.agents.summarizer.app:app"
        ;;
    registry)
        MODULE="binex.registry.app:app"
        ;;
    *)
        echo "Error: BINEX_AGENT_TYPE must be one of: planner, researcher, validator, summarizer, registry"
        echo "Usage: docker run -e BINEX_AGENT_TYPE=planner binex"
        exit 1
        ;;
esac

exec uvicorn "$MODULE" --host 0.0.0.0 --port 8000 "$@"
