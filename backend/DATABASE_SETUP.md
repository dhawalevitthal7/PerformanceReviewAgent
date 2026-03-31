# Database Setup Guide

This guide explains how to set up and initialize the database for the PerformBharat application.

## Database Configuration

The application supports both SQLite (default for development) and PostgreSQL (for production).

### SQLite (Default - Development)

SQLite is used by default and requires no additional setup. The database file `performbharat.db` will be created automatically in the `backend` directory.

### PostgreSQL (Production)

To use PostgreSQL, create a `.env` file in the `backend` directory:

```env
DATABASE_URL=postgresql://username:password@host:port/database_name
SECRET_KEY=your-secret-key-here-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

## Database Schema

The application uses the following tables:

1. **users** - User accounts with authentication
2. **profiles** - User profiles with role, department, and company information
3. **okrs** - Objectives and Key Results
4. **key_results** - Individual key results linked to OKRs
5. **checkins** - Weekly check-ins/updates
6. **assessments** - Self-assessments
7. **reviews** - Performance reviews
8. **progress_history** - Historical progress tracking

## Initializing the Database

### Method 1: Automatic Initialization (Recommended)

The database tables are automatically created when you start the FastAPI server:

```bash
python run.py
```

or

```bash
uvicorn app.main:app --reload
```

The startup process will:
- Create all database tables if they don't exist
- Verify the database connection
- Print initialization status

### Method 2: Manual Initialization

You can also initialize the database manually using the initialization script:

```bash
python init_db.py
```

This script will:
- Create all database tables
- Verify the connection
- List all created tables

## Verifying Database Connection

### Health Check Endpoints

1. **Basic Health Check:**
   ```bash
   curl http://localhost:8000/health
   ```

2. **Database Health Check:**
   ```bash
   curl http://localhost:8000/health/db
   ```

The database health check returns:
- Connection status
- Database URL (masked)
- List of all tables

### Viewing Database Schema

To view the database schema documentation:

```bash
python create_db_schema.py
```

## Database Models

All models are defined in `app/db/models.py`:

- **User**: Authentication and user accounts
- **Profile**: User profile with role (employee/manager), department, company
- **OKR**: Objectives with due dates
- **KeyResult**: Key results with targets, current values, and units
- **CheckIn**: Weekly updates with mood and notes
- **Assessment**: Self-assessments with ratings and feedback
- **Review**: Performance reviews with scores and status
- **ProgressHistory**: Historical progress tracking

## Troubleshooting

### Database Not Connecting

1. Check your `.env` file exists and has correct `DATABASE_URL`
2. Verify database credentials are correct
3. Ensure database server is running (for PostgreSQL)
4. Check database file permissions (for SQLite)

### Tables Not Created

1. Ensure all models are imported in `app/main.py`
2. Run `python init_db.py` manually
3. Check for errors in the console output
4. Verify database connection string format

### Reset Database

To reset the database (⚠️ **WARNING: This will delete all data**):

1. Delete the database file (SQLite): `rm performbharat.db`
2. Or drop all tables (PostgreSQL): Connect to database and drop tables
3. Run `python init_db.py` to recreate tables

## Database Relationships

- **User** → **Profile** (One-to-One)
- **User** → **OKR** (One-to-Many)
- **User** → **CheckIn** (One-to-Many)
- **User** → **Assessment** (One-to-Many)
- **User** → **Review** (One-to-Many)
- **OKR** → **KeyResult** (One-to-Many)
- **User** → **ProgressHistory** (One-to-Many)

All relationships use CASCADE delete, so deleting a user will delete all related records.

## Production Considerations

1. **Use PostgreSQL** for production environments
2. **Set strong SECRET_KEY** in environment variables
3. **Use connection pooling** for better performance
4. **Set up database backups** regularly
5. **Monitor database health** using `/health/db` endpoint
6. **Use migrations** (Alembic) for schema changes in production

## Next Steps

After database initialization:

1. Create your first user account via `/api/v1/auth/signup`
2. Login via `/api/v1/auth/signin`
3. Start creating OKRs, check-ins, and assessments
4. Generate performance reviews

For API documentation, visit: http://localhost:8000/docs
