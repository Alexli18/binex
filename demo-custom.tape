# Binex Demo — Custom Workflow Constructor
# Build a content pipeline node-by-node with DSL topology

Output assets/demo-custom.gif
Set Theme "Dracula"
Set FontSize 15
Set Width 1400
Set Height 1000
Set Padding 20
Set TypingSpeed 40ms
Set PlaybackSpeed 0.5

# =============================================
# PART 1: Launch start wizard
# =============================================
Sleep 500ms
Type "binex start"
Sleep 300ms
Enter
Sleep 2s

# Step 1: Choose template — select custom constructor
Type "c"
Sleep 200ms
Enter
Sleep 1s

# Choose mode: 1 = DSL
Type "1"
Sleep 200ms
Enter
Sleep 2s

# Type custom topology
Type "draft -> review -> publish"
Sleep 300ms
Enter
Sleep 2s

# =============================================
# PART 2: Configure each node
# =============================================

# --- Node 1/3: draft ---
Sleep 1s

# Agent type: 1 (LLM)
Type "1"
Sleep 200ms
Enter
Sleep 1s

# Provider: 1 (ollama)
Type "1"
Sleep 200ms
Enter
Sleep 500ms

# Model
Type "gemma3:4b"
Sleep 200ms
Enter
Sleep 1s

# System prompt: 81 (gen-draft-writer.md — recommended)
Type "81"
Sleep 200ms
Enter
Sleep 500ms

# Back-edge: no
Type "n"
Sleep 200ms
Enter
Sleep 500ms

# Advanced params: no
Type "n"
Sleep 200ms
Enter
Sleep 1s

# --- Node 2/3: review ---

# Agent type: 2 (Human review)
Type "2"
Sleep 200ms
Enter
Sleep 500ms

# Back-edge: no
Type "n"
Sleep 200ms
Enter
Sleep 500ms

# Advanced params: no
Type "n"
Sleep 200ms
Enter
Sleep 1s

# --- Node 3/3: publish ---

# Agent type: 1 (LLM)
Type "1"
Sleep 200ms
Enter
Sleep 1s

# Provider: 1 (ollama)
Type "1"
Sleep 200ms
Enter
Sleep 500ms

# Model
Type "gemma3:4b"
Sleep 200ms
Enter
Sleep 1s

# System prompt: 75 (gen-content-editor.md)
Type "75"
Sleep 200ms
Enter
Sleep 500ms

# Back-edge: no
Type "n"
Sleep 200ms
Enter
Sleep 500ms

# Advanced params: no
Type "n"
Sleep 200ms
Enter
Sleep 2s

# =============================================
# PART 3: Preview, save, done
# =============================================

# YAML preview is shown — save workflow
Type "y"
Sleep 200ms
Enter
Sleep 1s

# Project name: accept default
Enter
Sleep 1s

# Run now: no (just show the result)
Type "n"
Sleep 200ms
Enter
Sleep 3s
