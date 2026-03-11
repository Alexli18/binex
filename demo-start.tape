# Binex Demo — Start Wizard
# Create a research pipeline from template in under 2 minutes

Output assets/demo-start.gif
Set Theme "Dracula"
Set FontSize 15
Set Width 1400
Set Height 1000
Set Padding 20
Set TypingSpeed 40ms
Set PlaybackSpeed 0.5

# =============================================
# PART 1: Create project directory
# =============================================
Sleep 500ms
Type "mkdir my-research && cd my-research"
Sleep 300ms
Enter
Sleep 1s

# =============================================
# PART 2: Launch start wizard
# =============================================
Type "binex start"
Sleep 300ms
Enter
Sleep 2s

# Step 1 of 5: Choose template
# Select category: 1 (general)
Type "1"
Sleep 200ms
Enter
Sleep 1s

# Select template: 1 (Research)
Type "1"
Sleep 200ms
Enter
Sleep 1s

# Step 2 of 5: User input — yes
Type "y"
Sleep 200ms
Enter
Sleep 1s

# Step 3 of 5: Choose LLM
# Provider: 1 (ollama — free, runs locally)
Type "1"
Sleep 200ms
Enter
Sleep 1s

# Model: accept default (ollama/llama3.2)
Enter
Sleep 1s

# Step 4 of 5: Project name — accept default
Enter
Sleep 1s

# Step 5 of 5: Project created
Sleep 2s

# Run now? — yes
Type "y"
Sleep 200ms
Enter
Sleep 2s

# =============================================
# PART 3: Workflow is running — human input
# =============================================
Sleep 2s

# Type research topic
Type "How AI agents collaborate in multi-step pipelines"
Sleep 300ms
Enter
Sleep 1s

# =============================================
# PART 4 (hidden): Wait for LLMs to finish
# =============================================
Hide
Sleep 90s
Show

# =============================================
# PART 5: Explore the run
# =============================================
Sleep 3s

Type "binex explore"
Sleep 300ms
Enter
Sleep 2s

# Select first run (latest)
Type "1"
Sleep 200ms
Enter
Sleep 2s

# Open artifacts browser
Type "a"
Sleep 200ms
Enter
Sleep 2s

# Select last artifact (summarizer)
Type "5"
Sleep 200ms
Enter
Sleep 3s

# Show lineage
Type "l"
Sleep 200ms
Enter
Sleep 3s

# Back from artifacts
Type "b"
Sleep 200ms
Enter
Sleep 1s

# Quit explore
Type "q"
Sleep 200ms
Enter
Sleep 2s
