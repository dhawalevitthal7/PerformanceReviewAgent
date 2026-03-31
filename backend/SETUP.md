# PerformBharat Backend Setup Guide

## Prerequisites

- Python 3.9 or higher
- PostgreSQL database (Neon DB provided)
- pip or pipenv

## Installation Steps

1. **Navigate to the backend directory:**
```bash
cd backend
```

2. **Create a virtual environment (recommended):**
```bash
python -m venv venv
```

3. **Activate the virtual environment:**
   - On Windows:
   ```bash
   venv\Scripts\activate
   ```
   - On macOS/Linux:
   ```bash
   source venv/bin/activate
   ```

4. **Install dependencies:**
```bash
pip install -r requirements.txt
```

5. **Set up environment variables:**
   - Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
   - Edit `.env` and ensure `DATABASE_URL` is set correctly (already provided)

6. **Initialize the database:**
```bash
python init_db.py
```

This will create all necessary tables in your Neon PostgreSQL database.

## Running the Server

**Option 1: Using the run script**
```bash
python run.py
```

**Option 2: Using uvicorn directly**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The server will start on `http://localhost:8000`

## API Documentation

Once the server is running:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Testing the API

### 1. Sign Up (Create a new user)
```bash
curl -X POST "http://localhost:8000/api/v1/auth/signup" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "password123",
    "full_name": "Test User",
    "role": "employee",
    "department": "Production",
    "company_name": "Test Company",
    "company_code": "TEST001"
  }'
```

### 2. Sign In
```bash
curl -X POST "http://localhost:8000/api/v1/auth/signin" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "password123"
  }'
```

Save the `access_token` from the response.

### 3. Get Current User Info
```bash
curl -X GET "http://localhost:8000/api/v1/auth/me" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 4. Create an OKR
```bash
curl -X POST "http://localhost:8000/api/v1/okrs" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
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
  }'
```

## Database Schema

The following tables are created:
- `users` - User accounts
- `profiles` - User profiles (role, department, company)
- `okrs` - Objectives and Key Results
- `key_results` - Individual key results
- `checkins` - Weekly check-ins
- `assessments` - Self-assessments
- `reviews` - Performance reviews
- `progress_history` - Historical progress tracking

## Notes

- All endpoints except `/auth/signup` and `/auth/signin` require authentication
- Use the `access_token` from signin in the `Authorization: Bearer <token>` header
- The database tables are automatically created on server startup
- File storage integration will be added later as mentioned

## Troubleshooting

1. **Database connection errors:**
   - Verify your `.env` file has the correct `DATABASE_URL`
   - Check that your Neon database is accessible

2. **Import errors:**
   - Ensure you're in the backend directory
   - Verify all dependencies are installed: `pip install -r requirements.txt`

3. **Port already in use:**
   - Change the port in `run.py` or use: `uvicorn app.main:app --port 8001`
