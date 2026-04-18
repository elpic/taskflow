---
name: stop
description: "Stop the continuous delivery loop after the current ticket completes"
---

The user wants to stop the taskflow continuous delivery loop.

1. Let the current ticket finish through its merge (do not abandon mid-PR)
2. After the current ticket merges (or if between tickets), stop the loop
3. Report:
   - How many tickets were completed in this session
   - How many tickets remain in the backlog
   - Any tech debt items created during this session
   - Store a session summary in mempalace
4. Do NOT start the next ticket
