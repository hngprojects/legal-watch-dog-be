# Content Hashing Flow - When and Where It Changes

## Overview
Content hashing is a **deduplication mechanism** that prevents re-extracting identical content. Here's the complete flow:

---

## Step-by-Step Pipeline

### 1. **FETCH URL** (Line 98)
```
https://www.gov.uk/national-minimum-wage-rates
           ↓
    Raw HTML bytes (106KB)
```
- **Hash Status**: ❌ No hash yet
- Content is raw, unprocessed HTML with formatting, scripts, CSS

---

### 2. **UPLOAD TO MINIO** (Line 150)
```
raw_html_bytes → MinIO storage
           ↓
minio_key: raw/{project_id}/{source_id}/{timestamp}.html
```
- **Hash Status**: ❌ No hash yet
- Raw content archived for audit trail

---

### 3. **CLEAN HTML TO TEXT** (Line 152)
```
Raw HTML (106KB)
    ↓ [clean_html_content()]
Plain text (5.3KB)
```
- **Hash Status**: ❌ No hash yet
- Removes formatting, scripts, CSS, boilerplate
- Keeps only semantic content (wages, dates, etc.)

---

### 4. **COMPUTE SHA256 HASH** ✅ **HASH CREATED HERE** (Line 153)
```python
content_hash = hashlib.sha256(clean_text.encode()).hexdigest()
```

**Example:**
- Input: `"In April 2025, the National Living Wage for those aged 21..."`
- Output: `38733e8df8315ae2...` (64-char hex)

- **Hash Status**: ✅ **Hash computed from cleaned text**
- This is the deduplication key

---

### 5. **CHECK LAST REVISION** (Lines 156-159)
```python
last_revision = self.db.query(DataRevision)\
    .filter(DataRevision.source_id == source.id)\
    .order_by(desc(DataRevision.scraped_at))\
    .first()

if last_revision and last_revision.content_hash == content_hash:
    # Content is identical!
    logger.info(f"Content unchanged (hash: {content_hash[:8]}...)")
```

**Two Scenarios:**

#### Scenario A: Same Content (Test Run 2)
```
Previous Run 1: content_hash = 38733e8df8315ae2...
Current Run 2:  content_hash = 38733e8df8315ae2...
                               ↓ MATCH!
Action: ✅ REUSE previous extraction
- Don't call LLM
- Set was_change_detected = False
- Skip AI extraction entirely
```

#### Scenario B: Different Content
```
Previous: content_hash = abc123...
Current:  content_hash = def456...
                         ↓ MISMATCH!
Action: ⚙️ RUN full pipeline
- Call AIExtractionService
- Call DiffAIService
- Detect semantic changes
- Create new DataRevision
```

---

### 6. **STORE HASH IN DATABASE** (Line 201)
```python
new_revision = DataRevision(
    content_hash=content_hash,  # 38733e8df8315ae2...
    extracted_data=ai_result,
    ...
)
```

- **Hash Status**: ✅ **Persisted to DB**
- Used as comparison key for next run
- Enables deduplication across runs

---

## Test Run Results: When Hash Changes

### First Extraction (test_celery_scraper_mock.py Run 1)
```
Content: GOV.UK minimum wage HTML
           ↓
Cleaned text: "In April 2025..."
           ↓
Hash: 38733e8df8315ae2... ← NEW
           ↓
Previous revision: None
           ↓
Action: Extract & Store
Result: was_change_detected = TRUE (first time seeing this content)
```

### Second Extraction (test_celery_scraper_mock.py Run 2)
```
Content: Same GOV.UK page (no changes)
           ↓
Cleaned text: "In April 2025..." (identical)
           ↓
Hash: 38733e8df8315ae2... ← SAME
           ↓
Previous revision exists with hash: 38733e8df8315ae2...
           ↓
Action: Comparison → MATCH → Reuse extraction
Result: was_change_detected = FALSE (skipped AI call)
```

---

## When Hash CHANGES (Content is Different)

```
Page Updated: Old rates removed, new rates added
           ↓
Cleaned text: "In April 2026..." (DIFFERENT)
           ↓
Hash: 9a8b7c6d... ← DIFFERENT
           ↓
Previous revision hash: 38733e8df8315ae2... ← MISMATCH!
           ↓
Action: Extract & Compare
Result: was_change_detected = TRUE (new data detected)
```

---

## Key Insights

| Aspect | Details |
|--------|---------|
| **Hash Input** | Cleaned, plain text (semantic content only) |
| **Hash Algorithm** | SHA256 (256-bit, cryptographically secure) |
| **When Computed** | After HTML→text cleaning, before DB lookup |
| **Stored** | DataRevision.content_hash column |
| **Purpose** | Detect duplicate content, avoid re-extraction |
| **Efficiency** | If hash matches: Skip AI call (saves 3-5 seconds + API cost) |
| **Accuracy** | 100% consistent - same content = same hash |

---

## Code Flow Diagram

```
FETCH URL
    ↓
UPLOAD RAW HTML TO MINIO
    ↓
CLEAN HTML → PLAIN TEXT
    ↓
COMPUTE SHA256 HASH ← ✅ HASH CREATED
    ↓
QUERY LAST REVISION (check its hash)
    ↓
    ├─ Hash matches? → REUSE extraction (was_change_detected=FALSE)
    │
    └─ Hash differs or no revision? → RUN AI + DIFF (was_change_detected=TRUE/FALSE)
            ↓
        EXTRACT + COMPARE
            ↓
        STORE NEW REVISION WITH HASH
```

---

## Test Evidence

From test_celery_scraper_mock.py output:

**Run 1:**
```
Content Hash: 38733e8df8315ae2...
Was Change Detected: True
```

**Run 2 (same URL):**
```
Content Hash: 38733e8df8315ae2... ← IDENTICAL
Content unchanged (hash: 38733e8d...). Reusing previous extraction.
Was Change Detected: False
```

✅ This proves the hash-based deduplication works perfectly.
