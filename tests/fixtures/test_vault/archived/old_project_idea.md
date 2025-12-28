# Old Project Idea - Habit Tracking App (ARCHIVED)

**Status**: Abandoned
**Date**: 2023-06-15

## Original Idea

Build a mobile app for habit tracking with these features:
- Daily check-ins
- Streak tracking
- Social accountability (share progress with friends)
- Gamification (badges, levels)

## Why Abandoned

After market research, found 50+ existing apps that do exactly this:
- Habitica
- Streaks
- Loop Habit Tracker
- Productive
- etc.

Market is completely saturated. Would need a unique angle to compete.

## Lessons Learned

1. **Do market research BEFORE building**
2. **"Scratching your own itch" isn't enough if 1000 others already scratched it**
3. **Distribution is harder than building**

## What I Built Anyway

Made a simple CLI tool for personal use:

```python
# habit.py
import json
from datetime import date

def check_in(habit_name):
    with open('habits.json', 'r') as f:
        habits = json.load(f)

    today = str(date.today())
    habits[habit_name].append(today)

    with open('habits.json', 'w') as f:
        json.dump(habits, f)

    print(f"✅ {habit_name} checked in!")

# Usage: python habit.py "Exercise"
```

Works fine for me. No need to over-engineer.

#archived #lessons-learned #projects
