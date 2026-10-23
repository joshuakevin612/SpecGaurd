# SpecGuard API Quick Start

Get up and running with the SpecGuard API in 5 minutes.

---

## Start the Backend

```bash
cd specguard
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

API is now at `http://localhost:8000`

---

## 1. Create a Project

```bash
curl -X POST http://localhost:8000/projects \
  -H "Content-Type: application/json" \
  -d '{
    "specification": "The function add(a, b) must return the sum of two integers. It must handle negative numbers and zero correctly.",
    "source_code": "def add(a, b):\n    return a + b\n\ndef subtract(a, b):\n    return a - b"
  }'
```

**Response:**
```json
{
  "project_id": "proj_abc123def456"
}
```

Save the `project_id` for the next steps.

---

## 2. Run Verification

```bash
curl -X POST http://localhost:8000/projects/proj_abc123def456/verify \
  -H "Content-Type: application/json" \
  -d '{
    "use_docker": false
  }'
```

**Response:**
```json
{
  "project_id": "proj_abc123def456",
  "requirements_count": 2,
  "tests_count": 2,
  "passed": 2,
  "failed": 0,
  "errors": 0,
  "timeouts": 0,
  "flaky": 0,
  "total_results": 2
}
```

---

## 3. Get the Report (JSON)

```bash
curl http://localhost:8000/projects/proj_abc123def456/report?format=json
```

**Response** (abbreviated):
```json
{
  "report": {
    "project_id": "proj_abc123def456",
    "generated_at": "2024-10-20T12:34:56.789Z",
    "summary": {
      "total_requirements": 2,
      "total_tests": 2,
      "passed": 2,
      "failed": 0,
      "errors": 0,
      "timeouts": 0,
      "flaky": 0,
      "total_results": 2
    },
    "requirements": [
      {
        "id": "req_xyz123",
        "text": "The function add(a, b) must return the sum of two integers...",
        "category": "functional",
        "measurable_criteria": "Verify that The function add(a, b) must return the sum of two integers...",
        "ambiguous": false,
        "clarification_note": null
      }
    ],
    "test_results": [
      {
        "test_id": "test_abc123",
        "requirement_id": "req_xyz123",
        "status": "passed",
        "output": "test passed",
        "duration_ms": 45
      }
    ],
    "static_findings": [],
    "fix_suggestions": []
  },
  "format": "json"
}
```

---

## 4. Get the Report (HTML)

```bash
curl http://localhost:8000/projects/proj_abc123def456/report?format=html > report.html
open report.html  # On macOS
# or
xdg-open report.html  # On Linux
```

Opens a beautiful, styled HTML report with:
- Summary statistics (cards with metrics)
- Requirement-by-requirement breakdown
- Test results with output
- Static findings and warnings
- Suggested fixes

---

## 5. Fix Code and Retest

Suppose the code had a bug. Update it and retest:

```bash
curl -X POST http://localhost:8000/projects/proj_abc123def456/retest \
  -H "Content-Type: application/json" \
  -d '{
    "updated_code": "def add(a, b):\n    # Fixed: was returning wrong type\n    return int(a) + int(b)\n\ndef subtract(a, b):\n    return a - b"
  }'
```

**Response:**
```json
{
  "project_id": "proj_abc123def456",
  "passed": 2,
  "failed": 0,
  "errors": 0,
  "timeouts": 0,
  "flaky": 0,
  "total_results": 2
}
```

---

## Example: Flawed Code Detection

**Scenario**: Code has a subtle bug.

### Step 1: Create project with flawed code

```bash
curl -X POST http://localhost:8000/projects \
  -H "Content-Type: application/json" \
  -d '{
    "specification": "The function validate_email(email) must check if an email is valid. Valid emails must contain an @ symbol and a domain.",
    "source_code": "def validate_email(email):\n    # BUG: Only checks for @, doesn'\''t validate domain\n    return '@' in email"
  }'
```

Response: `{"project_id": "proj_flawed_001"}`

### Step 2: Run verification

```bash
curl -X POST http://localhost:8000/projects/proj_flawed_001/verify \
  -H "Content-Type: application/json" \
  -d '{"use_docker": false}'
```

### Step 3: Check report

```bash
curl http://localhost:8000/projects/proj_flawed_001/report?format=html > flawed_report.html
```

The report will show:
- ❌ Test failed: "test_email_validation"
- Expected: Valid emails contain both @ and domain
- Actual: Only checks for @
- Suggested fix: "def validate_email(email):\n    return '@' in email and '.' in email.split('@')[1]"

### Step 4: Fix and retest

```bash
curl -X POST http://localhost:8000/projects/proj_flawed_001/retest \
  -H "Content-Type: application/json" \
  -d '{
    "updated_code": "def validate_email(email):\n    parts = email.split('\''@'\'')\n    return len(parts) == 2 and '\''.'\'' in parts[1]"
  }'
```

Response: `{"passed": 1, "failed": 0, ...}` ✅

---

## All Endpoints

### Create Project
```
POST /projects
{
  "specification": "...",
  "source_code": "..."
}
→ {"project_id": "proj_xxx"}
```

### Verify Project
```
POST /projects/{project_id}/verify
{
  "use_docker": false  // Optional, default false
}
→ {"project_id": "...", "passed": 2, "failed": 0, ...}
```

### Get Report
```
GET /projects/{project_id}/report?format=json|html
→ {"report": {...}, "format": "json|html"}
```

### Retest Project
```
POST /projects/{project_id}/retest
{
  "updated_code": "..."
}
→ {"project_id": "...", "passed": 2, "failed": 0, ...}
```

### Health Check
```
GET /health
→ {"status": "ok"}
```

---

## Testing with curl, Python, or JavaScript

### JavaScript (Fetch)
```javascript
// Create project
const res = await fetch('http://localhost:8000/projects', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    specification: 'The function must add numbers',
    source_code: 'def add(a, b): return a + b'
  })
});

const data = await res.json();
const projectId = data.project_id;

// Verify
const verifyRes = await fetch(`http://localhost:8000/projects/${projectId}/verify`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ use_docker: false })
});

const results = await verifyRes.json();
console.log(results);
```

### Python (Requests)
```python
import requests

BASE_URL = 'http://localhost:8000'

# Create project
res = requests.post(f'{BASE_URL}/projects', json={
    'specification': 'The function must add numbers',
    'source_code': 'def add(a, b): return a + b'
})
project_id = res.json()['project_id']

# Verify
res = requests.post(f'{BASE_URL}/projects/{project_id}/verify', json={
    'use_docker': False
})
print(res.json())
```

---

## Tips

1. **Spec Quality**: More detailed specifications → better test generation
2. **Local vs Docker**: 
   - Local (default): Fast, for testing
   - Docker: Sandboxed, requires Docker installed
3. **Flaky Tests**: If a test passes sometimes and fails other times, it's marked "flaky"
4. **Reports**: HTML reports are great for demos, JSON for automation
5. **Retest Often**: The retest endpoint is your friend during debugging

---

## Next Steps

- Build the React frontend to call these endpoints
- Person A integrates NVIDIA Nemotron for better spec parsing and test generation
- Add more complex specifications to test the pipeline
- Deploy with Docker Compose

Happy testing! 🚀
