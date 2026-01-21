# FML Memory Maintenance Guide

This document describes the memory quality evaluation and maintenance processes for the Firebolt Memory Layer.

## Overview

FML includes automated tools to maintain memory quality over time:
- **Daily backups** - Incremental backup of new memories
- **Quality evaluation** - Find contradictions and stale memories  
- **Decay system** - Reduce importance of unused memories
- **Supersession** - Mark outdated memories as replaced

## MCP Tools

### memory_quality_report
Generate a comprehensive quality report for a user's memories.

```
Tool: memory_quality_report
Args:
  - user_id: "johnkennedy"
  - include_contradictions: true
  - include_stale: true
```

Returns:
- Overall statistics (count, avg importance, access patterns)
- Category distribution
- Health score (0-100)
- Potential contradictions
- Stale memories needing review

### find_memory_contradictions
Find memories that may contain conflicting information.

```
Tool: find_memory_contradictions
Args:
  - user_id: "johnkennedy"
  - similarity_threshold: 0.75  # 0.0-1.0
  - limit: 10
```

Returns pairs of memories that are semantically similar (same topic) but have different content, suggesting one may supersede the other.

### supersede_memory
Mark an outdated memory as replaced by a newer one.

```
Tool: supersede_memory
Args:
  - old_memory_id: "abc123..."
  - new_memory_id: "def456..."
  - user_id: "johnkennedy"
```

The old memory is soft-deleted and the relationship is tracked via the `supersedes` field.

### apply_memory_decay
Reduce importance of memories that haven't been accessed recently.

```
Tool: apply_memory_decay
Args:
  - user_id: "johnkennedy"
  - decay_rate: 0.95  # Multiplier (0.0-1.0)
  - days_inactive: 7  # Days without access
```

### run_daily_maintenance
Run all maintenance tasks in one call (for scheduled jobs).

```
Tool: run_daily_maintenance
Args:
  - user_id: "johnkennedy"
```

Performs:
1. Backup new memories
2. Apply decay to unused memories
3. Generate quality stats

## Automated Scheduling (Cron)

### Setup Cron Job (Monday-Friday at 9 AM)

```bash
# Make script executable
chmod +x /path/to/fml-server/scripts/cron_maintenance.sh

# Edit crontab
crontab -e

# Add this line (runs Mon-Fri at 9:00 AM):
0 9 * * 1-5 /Users/johnkennedy/DevelopmentArea/Firebolt-Memory-Layer/fml/fml-server/scripts/cron_maintenance.sh johnkennedy
```

### Cron Schedule Syntax
```
┌───────────── minute (0-59)
│ ┌───────────── hour (0-23)
│ │ ┌───────────── day of month (1-31)
│ │ │ ┌───────────── month (1-12)
│ │ │ │ ┌───────────── day of week (0-6, 0=Sunday)
│ │ │ │ │
0 9 * * 1-5  command
```

### View Logs
```bash
# Today's log
cat /path/to/fml-server/logs/maintenance_$(date +%Y%m%d).log

# All logs
ls -la /path/to/fml-server/logs/
```

## Manual Scripts

### Daily Backup
```bash
cd fml-server
source .venv/bin/activate
python scripts/daily_backup.py
```

### Quality Report
```bash
python scripts/memory_quality.py johnkennedy report
```

### Find Contradictions
```bash
python scripts/memory_quality.py johnkennedy contradictions
```

### Find Stale Memories
```bash
python scripts/memory_quality.py johnkennedy stale
```

### Supersede Memory
```bash
python scripts/memory_quality.py johnkennedy supersede OLD_ID NEW_ID
```

### Apply Decay
```bash
python scripts/memory_quality.py johnkennedy decay
```

## Memory Quality Concepts

### Health Score (0-100)
- **90-100**: Excellent - memories are well-used and important
- **70-89**: Good - minor issues to address
- **50-69**: Fair - some cleanup needed
- **0-49**: Needs Attention - significant maintenance required

### Contradictions
Two memories are flagged as potential contradictions when:
1. High semantic similarity (>75%) - same topic
2. Low content overlap (<50%) - different information
3. One is newer than the other

**Resolution options:**
- **Supersede**: Newer info replaces older (use `supersede_memory`)
- **Merge**: Combine into one comprehensive memory
- **Keep both**: Both are valid complementary information

### Decay System
- Memories not accessed in 7+ days have importance reduced
- Default decay rate: 98% (2% reduction per maintenance run)
- Minimum importance: 0.1 (never fully decays)
- Frequently accessed memories maintain importance

### Backup Strategy
- Incremental: Only new memories since last backup
- Storage: `long_term_memories_backup` table in Firebolt
- Updated memories are also synced to backup
- Backup preserved on table rebuilds

## Troubleshooting

### Cron Not Running
```bash
# Check cron service
sudo launchctl list | grep cron

# Check cron logs (macOS)
log show --predicate 'process == "cron"' --last 1h
```

### High Contradiction Count
Many contradictions may indicate:
- Rapidly evolving knowledge (normal)
- Duplicate content being stored (check deduplication threshold)
- Need to run supersession more frequently

### Low Health Score
Common causes:
- Many never-accessed memories → Review and clean up
- Low average importance → LLM classification may need tuning
- Many stale memories → Run decay more frequently
