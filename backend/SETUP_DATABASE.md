# Database Setup Instructions

## PostgreSQL Database Configuration

Your application is configured to use PostgreSQL with Neon. Follow these steps:

### Step 1: Create .env File

Create a `.env` file in the `backend` directory with the following content:

```env
DATABASE_URL=postgresql://USERNAME:PASSWORD@HOST/DBNAME?sslmode=require&channel_binding=require
SECRET_KEY=replace-with-a-strong-random-string
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
AZURE_OPENAI_API_KEY=replace-with-your-azure-openai-api-key
AZURE_OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-12-01-preview
AZURE_OPENAI_DEPLOYMENT=gpt-4o
```

**Important:** 
- Replace `your-secret-key-change-in-production-please-change-this-to-a-random-string` with a strong random secret key
- The `.env` file is gitignored and won't be committed to version control

### Step 2: Initialize Database

Run the initialization script to create all tables:

```bash
cd backend
python init_db.py
```

This will:
- Connect to your PostgreSQL database
- Create all required tables
- Verify the connection
- List all created tables

### Step 3: Verify Connection

Test the database connection:

```bash
python test_db.py
```

### Step 4: Start the Server

Start your FastAPI server:

```bash
python run.py
```

The server will automatically:
- Connect to PostgreSQL
- Verify all tables exist
- Display connection status

### Step 5: Check Database Health

Once the server is running, check the database health:

```bash
curl http://localhost:8000/health/db
```

Or visit: http://localhost:8000/health/db

## Database Tables Created

The following tables will be created:

1. **users** - User accounts
2. **profiles** - User profiles with role, department, company
3. **okrs** - Objectives and Key Results
4. **key_results** - Individual key results
5. **checkins** - Weekly check-ins
6. **assessments** - Self-assessments
7. **reviews** - Performance reviews
8. **progress_history** - Historical progress tracking

## Troubleshooting

### Connection Errors

If you see connection errors:

1. **Check .env file exists** in the `backend` directory
2. **Verify DATABASE_URL** is correct (no extra spaces or quotes)
3. **Check Neon dashboard** to ensure database is active
4. **Verify network access** - Neon databases require SSL

### SSL Connection Issues

Neon requires SSL connections. The connection string includes:
- `sslmode=require` - Requires SSL
- `channel_binding=require` - Requires channel binding

If you have SSL issues, try:
```env
DATABASE_URL=postgresql://USERNAME:PASSWORD@HOST/DBNAME?sslmode=require
```

### Tables Not Created

If tables aren't created:

1. Run `python init_db.py` manually
2. Check for errors in the output
3. Verify you have CREATE TABLE permissions
4. Check the Neon dashboard for any restrictions

## Quick Start Commands

```bash
# 1. Create .env file (copy from .env.example and update)
cp .env.example .env
# Edit .env with your actual values

# 2. Initialize database
python init_db.py

# 3. Test connection
python test_db.py

# 4. Start server
python run.py
```

## Database URL Format

Your PostgreSQL URL format:
```
postgresql://[username]:[password]@[host]:[port]/[database]?[parameters]
```

For Neon, copy the connection string from the Neon dashboard
(**Settings → Connection Details → Connection string**) and paste it as
`DATABASE_URL` in your `.env` file.

## Next Steps

After database setup:
1. Create your first user account via signup
2. Login and start using the application
3. Create OKRs, check-ins, and assessments
4. Generate performance reviews

For API documentation: http://localhost:8000/docs
