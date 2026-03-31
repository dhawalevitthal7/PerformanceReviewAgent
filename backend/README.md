# PerformBharat Backend API

FastAPI backend for PerformBharat - OKRs & Performance Reviews application.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. **Database Setup:**

   **Option A: SQLite (Default - No setup needed)**
   - SQLite is used by default for local development
   - Database file `performbharat.db` will be created automatically
   - No additional configuration needed

   **Option B: PostgreSQL (Optional)**
   - Create a `.env` file in the `backend` directory:
   ```env
   DATABASE_URL=postgresql://username:password@host:port/database_name
   SECRET_KEY=your-secret-key-here-change-in-production
   ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=30
   ```

3. **Initialize Database:**
   
   The database tables are automatically created when you start the server. However, you can also initialize manually:
   
   ```bash
   python init_db.py
   ```
   
   To test the database connection:
   ```bash
   python test_db.py
   ```

4. **Run the application:**
```bash
python run.py
```

Or using uvicorn directly:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The server will automatically:
- Create all database tables on startup
- Verify database connection
- Display initialization status

## API Documentation

Once the server is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Database Schema

The application uses the following main tables:
- `users` - User accounts
- `profiles` - User profiles with role, department, company info
- `okrs` - Objectives and Key Results
- `key_results` - Individual key results linked to OKRs
- `checkins` - Weekly check-ins
- `assessments` - Self-assessments
- `reviews` - Performance reviews
- `progress_history` - Historical progress tracking

## API Endpoints

### Authentication
- `POST /api/v1/auth/signup` - Register new user
- `POST /api/v1/auth/signin` - Login
- `GET /api/v1/auth/me` - Get current user info

### OKRs
- `GET /api/v1/okrs` - Get all OKRs
- `GET /api/v1/okrs/{okr_id}` - Get specific OKR
- `POST /api/v1/okrs` - Create OKR
- `PUT /api/v1/okrs/{okr_id}` - Update OKR
- `DELETE /api/v1/okrs/{okr_id}` - Delete OKR
- `PUT /api/v1/okrs/{okr_id}/key-results/{kr_id}` - Update key result progress

### Check-ins
- `GET /api/v1/checkins` - Get all check-ins
- `POST /api/v1/checkins` - Create check-in
- `GET /api/v1/checkins/{checkin_id}` - Get specific check-in

### Assessments
- `GET /api/v1/assessments` - Get all assessments
- `GET /api/v1/assessments/latest` - Get latest assessment
- `POST /api/v1/assessments` - Create assessment
- `PUT /api/v1/assessments/{assessment_id}` - Update assessment

### Reviews
- `GET /api/v1/reviews` - Get reviews
- `GET /api/v1/reviews/{review_id}` - Get specific review
- `POST /api/v1/reviews/generate` - Generate AI-powered review
- `PUT /api/v1/reviews/{review_id}/status` - Update review status

### Team (Manager only)
- `GET /api/v1/team` - Get team members
- `GET /api/v1/team/{user_id}` - Get team member details

### Progress
- `GET /api/v1/progress` - Get progress history

### Coaching
- `GET /api/v1/coaching` - Get coaching tips

## Authentication

All endpoints (except signup/signin) require authentication via Bearer token in the Authorization header:
```
Authorization: Bearer <access_token>
```

## Notes

- File storage integration will be added later as mentioned
- The review generation is simplified - in production, integrate with an AI service
- Progress history tracking can be enhanced to store actual historical data
- Team management assumes users in the same department/company
