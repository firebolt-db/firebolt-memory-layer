# Firebolt Core Bug Report: S3 Secondary File Missing for NULL Array Columns

**Reported by:** John Kennedy  
**Date:** 2026-01-21  
**Severity:** High (blocks all read/write operations on affected tables)

---

## Error Message

```
Firebolt Core error: Secondary file s3://firebolt-core-account-id-aws-global-28/pm-waJL1p7B9N4aY5Iq6sg~28~all~1/related_memories.null1.bin does not exist. It is a bug.
```

---

## Environment

| Property | Value |
|----------|-------|
| Firebolt Core Version | 4.28.31 |
| Platform | macOS (Apple Silicon) via Docker |
| Core URL | `http://localhost:3473` |
| Query Parameters | `advanced_mode=1&enable_vector_search_tvf=1&enable_vector_search_index_creation=1` |

---

## Table Structure (DDL)

```sql
CREATE TABLE long_term_memories (
    memory_id       TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    org_id          TEXT,
    memory_category TEXT NOT NULL,
    memory_subtype  TEXT NOT NULL,
    content         TEXT NOT NULL,
    summary         TEXT,
    embedding       ARRAY(REAL NOT NULL) NOT NULL,  -- Works fine (NOT NULL)
    entities        ARRAY(TEXT),                     -- Nullable array, no issues observed
    metadata        TEXT,
    event_time      TIMESTAMPNTZ,
    is_temporal     BOOLEAN DEFAULT FALSE,
    importance      REAL DEFAULT 0.5,
    access_count    INT DEFAULT 0,
    decay_factor    REAL DEFAULT 1.0,
    related_memories ARRAY(TEXT),                    -- ⚠️ PROBLEMATIC COLUMN
    supersedes      TEXT,
    source_session  TEXT,
    source_type     TEXT,
    confidence      REAL DEFAULT 1.0,
    created_at      TIMESTAMPNTZ DEFAULT CURRENT_TIMESTAMP(),
    last_accessed   TIMESTAMPNTZ DEFAULT CURRENT_TIMESTAMP(),
    updated_at      TIMESTAMPNTZ DEFAULT CURRENT_TIMESTAMP(),
    deleted_at      TIMESTAMPNTZ
)
PRIMARY INDEX memory_id;

-- HNSW vector index was also created
CREATE INDEX idx_memories_embedding ON long_term_memories USING HNSW (
    embedding vector_cosine_ops
) WITH (
    dimension = 768,
    m = 16,
    ef_construction = 128,
    quantization = 'bf16'
);
```

---

## Data State

- Table had **~38 rows** with data
- The `related_memories` column was **never populated** - all rows had `NULL` values
- All other columns had valid data

---

## SQL Queries That Trigger the Error

### 1. SELECT * (FAILS)

```sql
SELECT * FROM long_term_memories LIMIT 1;
```

**Error:**
```
Firebolt Core error: Secondary file s3://firebolt-core-account-id-aws-global-59/cQbLZFK2ORTLyB4ZoQ29DA~59~all~1/related_memories.null1.bin does not exist. It is a bug.
```

### 2. UPDATE (FAILS)

```sql
UPDATE long_term_memories 
SET access_count = access_count + 1,
    last_accessed = CURRENT_TIMESTAMP()
WHERE memory_id = '5094f467-0902-4c65-8c4c-e238f5fe1ca8';
```

**Error:**
```
Firebolt Core error: Secondary file s3://firebolt-core-account-id-aws-global-17/jRye52BkjaEd3xxCHAFsyg~17~all~1/related_memories.null1.bin does not exist. It is a bug.
```

### 3. SELECT with problematic column (FAILS)

```sql
SELECT memory_id, related_memories 
FROM long_term_memories 
LIMIT 1;
```

**Error:**
```
Firebolt Core error: Secondary file s3://...related_memories.null1.bin does not exist. It is a bug.
```

### 4. COUNT(*) (FAILS)

```sql
SELECT COUNT(*) FROM long_term_memories 
WHERE related_memories IS NULL;
```

**Error:**
```
Firebolt Core error: Secondary file s3://...related_memories.null1.bin does not exist. It is a bug.
```

---

## SQL Queries That Work (Workaround)

### 1. SELECT with explicit columns (excluding related_memories)

```sql
SELECT memory_id FROM long_term_memories LIMIT 1;
-- Success: Returns ('6112fbff-1f36-44e5-9aa5-b5d6e21f2cbd',)

SELECT memory_id, content, importance FROM long_term_memories LIMIT 1;
-- Success
```

### 2. vector_search with explicit columns

```sql
SELECT memory_id, content
FROM vector_search(
    INDEX idx_memories_embedding,
    [0.263864, 0.996047, -2.615234, ...]::ARRAY(DOUBLE),
    5,
    64
)
LIMIT 3;
-- Success
```

### 3. COUNT(*) without touching the column

```sql
SELECT COUNT(*) FROM long_term_memories;
-- This may or may not work depending on query plan
```

---

## Root Cause Analysis

The bug appears to occur when:

1. A column is defined as `ARRAY(TEXT)` (nullable, outer NULL allowed)
2. Rows are inserted **without** populating that column (resulting in NULL values)
3. Firebolt Core's storage layer expects a secondary file for the array data
4. The file `related_memories.null1.bin` was never created because no data was written
5. Any query that reads the column (directly or indirectly via SELECT *, UPDATE, etc.) fails

### Key Observations

| Column | Type | Behavior |
|--------|------|----------|
| `embedding` | `ARRAY(REAL NOT NULL) NOT NULL` | ✅ Works - always populated |
| `entities` | `ARRAY(TEXT)` | ✅ Works - some rows had data |
| `related_memories` | `ARRAY(TEXT)` | ❌ Fails - all rows were NULL |

The difference appears to be:
- Columns with at least some non-NULL data work
- Columns with **100% NULL values** cause the S3 file error

---

## Steps to Reproduce

1. Create a table with a nullable `ARRAY(TEXT)` column
2. Insert rows **without** providing values for that column
3. Attempt to `SELECT *` or `UPDATE` any row

```sql
-- Step 1: Create table
CREATE TABLE test_null_array (
    id TEXT NOT NULL,
    data TEXT,
    nullable_array ARRAY(TEXT)  -- Nullable array column
)
PRIMARY INDEX id;

-- Step 2: Insert without populating the array
INSERT INTO test_null_array (id, data) VALUES ('row1', 'test data');

-- Step 3: Try to read (should fail)
SELECT * FROM test_null_array;
-- Expected: S3 secondary file error
```

---

## Workaround Applied

We recreated the table without the problematic column:

```sql
-- 1. Backup data (explicit columns, excluding related_memories)
CREATE TABLE long_term_memories_backup_temp AS
SELECT 
    memory_id, user_id, org_id, memory_category, memory_subtype,
    content, summary, embedding, entities, metadata,
    event_time, is_temporal, importance, access_count, decay_factor,
    supersedes, source_session, source_type, confidence,
    created_at, last_accessed, updated_at, deleted_at
FROM long_term_memories;

-- 2. Drop old index and table
DROP INDEX idx_memories_embedding;
DROP TABLE long_term_memories;

-- 3. Create new table WITHOUT the problematic column
CREATE TABLE long_term_memories (
    -- ... same schema minus related_memories column ...
)
PRIMARY INDEX memory_id;

-- 4. Create HNSW index on EMPTY table (required by Firebolt)
CREATE INDEX idx_memories_embedding ON long_term_memories USING HNSW (
    embedding vector_cosine_ops
) WITH (
    dimension = 768,
    m = 16,
    ef_construction = 128,
    quantization = 'bf16'
);

-- 5. Restore data
INSERT INTO long_term_memories 
SELECT * FROM long_term_memories_backup_temp;

-- 6. Cleanup
DROP TABLE long_term_memories_backup_temp;
```

---

## Suggested Fix

1. **Immediate**: Ensure secondary files are created for nullable array columns even when all values are NULL
2. **Alternative**: Return empty array or NULL gracefully instead of failing with S3 error
3. **Prevention**: Add validation during INSERT to materialize the secondary file structure

---

## Impact

- **Severity**: High
- **Affected Operations**: SELECT *, UPDATE, any query touching the NULL array column
- **Data Loss**: None (data is intact, just inaccessible)
- **Workaround Available**: Yes (recreate table without the column, or ensure column always has data)

---

## Contact

For questions about this bug report, contact the FML project team.

**Project**: Firebolt Memory Layer (FML)  
**Repository**: https://github.com/johnkennedy-cmyk/Firebolt-Memory-Layer
