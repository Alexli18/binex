# Binex Demo — Explore Dashboard (all features)
# Interactive run inspector: trace, graph, cost, artifacts, node detail, debug

Output assets/demo-explore.gif
Set Theme "Dracula"
Set FontSize 15
Set Width 1400
Set Height 1000
Set Padding 20
Set TypingSpeed 40ms
Set PlaybackSpeed 0.5

# =============================================
# PART 1: Run a workflow to have data
# =============================================
Sleep 500ms
Type "binex run examples/multi-provider-demo.yaml"
Sleep 300ms
Enter
Sleep 3s

# Human input prompt
Type "Impact of AI on modern education"
Sleep 300ms
Enter
Sleep 1s

# Wait for LLMs
Hide
Sleep 90s
Show

# Show run result briefly
Sleep 3s

# =============================================
# PART 2: Launch explore
# =============================================
Type "binex explore"
Sleep 300ms
Enter
Sleep 2s

# Select latest run
Type "1"
Sleep 200ms
Enter
Sleep 2s

# =============================================
# Feature 1: [t] Trace — execution timeline
# =============================================
Type "t"
Sleep 200ms
Enter
Sleep 3s

# Back to dashboard
Enter
Sleep 2s

# =============================================
# Feature 2: [g] Graph — DAG visualization
# =============================================
Type "g"
Sleep 200ms
Enter
Sleep 3s

# Back to dashboard
Enter
Sleep 2s

# =============================================
# Feature 3: [c] Cost — cost breakdown
# =============================================
Type "c"
Sleep 200ms
Enter
Sleep 3s

# Back to dashboard
Enter
Sleep 2s

# =============================================
# Feature 4: [a] Artifacts — browser + lineage
# =============================================
Type "a"
Sleep 200ms
Enter
Sleep 2s

# Select summarizer artifact (last one)
Type "5"
Sleep 200ms
Enter
Sleep 3s

# Show lineage tree
Type "l"
Sleep 200ms
Enter
Sleep 3s

# Back from artifact list
Type "b"
Sleep 200ms
Enter
Sleep 1s

# Back to dashboard
Enter
Sleep 2s

# =============================================
# Feature 5: [n] Node — detail inspector
# =============================================
Type "n"
Sleep 200ms
Enter
Sleep 2s

# Select planner node (2nd)
Type "2"
Sleep 200ms
Enter
Sleep 3s

# Back to dashboard
Enter
Sleep 2s

# =============================================
# Feature 6: [d] Debug — full report
# =============================================
Type "d"
Sleep 200ms
Enter
Sleep 4s

# Quit explore
Type "q"
Sleep 200ms
Enter
Sleep 2s
