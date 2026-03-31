# PerformBharat API Endpoints Reference

Base URL: `http://localhost:8000/api/v1`

All endpoints (except auth endpoints) require Bearer token authentication:
```
Authorization: Bearer <access_token>
```

## Authentication Endpoints

### POST `/auth/signup`
Register a new user.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "password123",
  "full_name": "John Doe",
  "role": "employee",  // or "manager"
  "department": "Production",
  "company_name": "Company Name",
  "company_code": "COMP001"
}
```

**Response:**
```json
{
  "user": {
    "id": "uuid",
    "email": "user@example.com"
  },
  "profile": {
    "id": "uuid",
    "user_id": "uuid",
    "full_name": "John Doe",
    "role": "employee",
    "department": "Production",
    "company_name": "Company Name",
    "company_code": "COMP001"
  },
  "token": {
    "access_token": "jwt_token",
    "token_type": "bearer"
  }
}
```

### POST `/auth/signin`
Login and get access token.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response:** Same as signup

### GET `/auth/me`
Get current authenticated user information.

**Headers:** `Authorization: Bearer <token>`

**Response:** Same as signup

---

## OKR Endpoints

### GET `/okrs`
Get all OKRs for the current user.

**Response:**
```json
[
  {
    "id": "uuid",
    "objective": "Increase production output",
    "created_at": "2026-01-15T00:00:00",
    "due_date": "2026-03-31T00:00:00",
    "key_results": [
      {
        "id": "uuid",
        "title": "Units produced per shift",
        "target": 500,
        "current": 420,
        "unit": "units",
        "due_date": "2026-03-31T00:00:00"
      }
    ]
  }
]
```

### GET `/okrs/{okr_id}`
Get a specific OKR by ID.

### POST `/okrs`
Create a new OKR.

**Request Body:**
```json
{
  "objective": "Increase production output",
  "due_date": "2026-03-31T00:00:00",
  "key_results": [
    {
      "title": "Units produced per shift",
      "target": 500,
      "unit": "units",
      "due_date": "2026-03-31T00:00:00"
    }
  ]
}
```

### PUT `/okrs/{okr_id}`
Update an OKR.

**Request Body:**
```json
{
  "objective": "Updated objective",  // optional
  "due_date": "2026-04-30T00:00:00"  // optional
}
```

### DELETE `/okrs/{okr_id}`
Delete an OKR.

### PUT `/okrs/{okr_id}/key-results/{kr_id}`
Update a key result's current value.

**Request Body:**
```json
{
  "current": 450
}
```

---

## Check-in Endpoints

### GET `/checkins`
Get all check-ins for the current user.

**Response:**
```json
[
  {
    "id": "uuid",
    "date": "2026-03-03T00:00:00",
    "note": "Good week. Hit shift target 4 out of 5 days.",
    "mood": "good",  // "great", "good", "okay", "struggling"
    "created_at": "2026-03-03T00:00:00"
  }
]
```

### POST `/checkins`
Create a new check-in.

**Request Body:**
```json
{
  "date": "2026-03-03T00:00:00",
  "note": "Good week. Hit shift target 4 out of 5 days.",
  "mood": "good"
}
```

### GET `/checkins/{checkin_id}`
Get a specific check-in by ID.

---

## Assessment Endpoints

### GET `/assessments`
Get all assessments for the current user.

### GET `/assessments/latest`
Get the latest assessment.

**Response:**
```json
{
  "id": "uuid",
  "self_rating": 4,  // 1-5
  "strengths": "Consistently met shift targets...",
  "improvements": "Need to improve documentation...",
  "notes": "Additional notes...",
  "created_at": "2026-03-01T00:00:00",
  "updated_at": "2026-03-01T00:00:00"
}
```

### POST `/assessments`
Create a new assessment.

**Request Body:**
```json
{
  "self_rating": 4,
  "strengths": "Consistently met shift targets...",
  "improvements": "Need to improve documentation...",
  "notes": "Additional notes..."  // optional
}
```

### PUT `/assessments/{assessment_id}`
Update an assessment.

---

## Review Endpoints

### GET `/reviews`
Get reviews. Managers can view team reviews, employees see their own.

**Query Parameters:**
- `user_id` (optional): For managers to view specific team member's reviews

**Response:**
```json
[
  {
    "id": "uuid",
    "summary": "Performance review summary...",
    "strengths": ["Strength 1", "Strength 2"],
    "improvements": ["Improvement 1", "Improvement 2"],
    "score": 4.1,
    "status": "pending",  // "pending", "submitted", "completed"
    "created_at": "2026-03-01T00:00:00",
    "updated_at": "2026-03-01T00:00:00"
  }
]
```

### GET `/reviews/{review_id}`
Get a specific review by ID.

### POST `/reviews/generate`
Generate an AI-powered review based on OKRs and assessments.

**Query Parameters:**
- `user_id` (optional): For managers to generate review for team member

**Response:** Review object

### PUT `/reviews/{review_id}/status`
Update review status (manager only).

**Request Body:**
```json
{
  "status": "completed"  // "pending", "submitted", "completed"
}
```

---

## Team Endpoints (Manager Only)

### GET `/team`
Get all team members in the same department/company.

**Response:**
```json
[
  {
    "id": "user_uuid",
    "name": "John Doe",
    "role": "employee",
    "department": "Production",
    "overall_progress": 78.5,
    "okr_count": 2
  }
]
```

### GET `/team/{user_id}`
Get a specific team member's details.

---

## Progress Endpoints

### GET `/progress`
Get progress history and KPI data.

**Response:**
```json
{
  "progress_history": [
    {
      "week": "W1",
      "progress": 35.0
    }
  ],
  "kpi_data": [
    {
      "day": "Mon",
      "output": 92.0
    }
  ]
}
```

---

## Coaching Endpoints

### GET `/coaching`
Get personalized coaching tips.

**Response:**
```json
{
  "tips": [
    {
      "title": "Break large goals into weekly milestones",
      "description": "Instead of aiming for 500 units...",
      "category": "Goal Setting"
    }
  ]
}
```

---

## Error Responses

All endpoints may return the following error responses:

**401 Unauthorized:**
```json
{
  "detail": "Could not validate credentials"
}
```

**404 Not Found:**
```json
{
  "detail": "Resource not found"
}
```

**403 Forbidden:**
```json
{
  "detail": "Not authorized to perform this action"
}
```

**400 Bad Request:**
```json
{
  "detail": "Validation error message"
}
```
