# Binex Demo — Multi-Provider Research Workflow
# Ollama (local) + OpenRouter (cloud) in one pipeline

Output assets/demo.gif
Set Theme "Dracula"
Set FontSize 15
Set Width 1400
Set Height 1000
Set Padding 20
Set TypingSpeed 40ms
Set PlaybackSpeed 0.5

# =============================================
# PART 1 (visible): Run multi-provider workflow
# =============================================
Sleep 500ms
Type "binex run examples/multi-provider-demo.yaml"
Sleep 300ms
Enter

# Wait for human input prompt to appear
Sleep 3s

# Type research topic
Type "How does quantum computing impact cryptography?"
Sleep 300ms
Enter
Sleep 1s

# =============================================
# PART 2 (hidden): Wait for LLMs to finish
# =============================================
Hide
Sleep 90s
Show

# =============================================
# PART 3 (visible): Explore dashboard
# =============================================
Sleep 3s

# Launch explore
Type "binex explore"
Sleep 300ms
Enter
Sleep 2s

# Select first run (latest)
Type "1"
Sleep 200ms
Enter
Sleep 2s

# Dashboard is shown with [t]race [g]raph [d]ebug [c]ost [a]rtifacts [n]ode [r]eplay [q]uit
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

# Show lineage for the artifact
Type "l"
Sleep 200ms
Enter
Sleep 3s

# Back from artifact list
Type "b"
Sleep 200ms
Enter
Sleep 1s

# Quit explore
Type "q"
Sleep 200ms
Enter
Sleep 2s

# =============================================
# PART 4 (visible): Debug the last run
# =============================================
Type "binex debug latest --rich"
Sleep 300ms
Enter
Sleep 5s
