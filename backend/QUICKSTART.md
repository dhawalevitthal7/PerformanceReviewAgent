# Quick Start Guide

## 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

## 2. Set Up Environment

Create a `.env` file in the `backend` directory:

Copy `.env.example` to `.env` and fill in your real values:
```bash
cp .env.example .env
```

Key variables to set in `.env`:
```env
# PostgreSQL (get from Neon dashboard) or keep sqlite:///./performbharat.db for local dev
DATABASE_URL=postgresql://USERNAME:PASSWORD@HOST/DBNAME?sslmode=require&channel_binding=require

# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=replace-with-a-strong-random-string

# From Azure portal → your OpenAI resource → Keys and Endpoint
AZURE_OPENAI_API_KEY=replace-with-your-azure-openai-api-key
AZURE_OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com/
```

## 3. Initialize Database

```bash
python init_db.py
```

This creates all necessary tables in your Neon PostgreSQL database.

## 4. Start the Server

```bash
python run.py
```

The API will be available at `http://localhost:8000`

## 5. Test the API

Visit http://localhost:8000/docs for interactive API documentation.

Or test with curl:

```bash
# Sign up
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

## Next Steps

1. Integrate the frontend to use these API endpoints
2. Update the frontend `AuthContext` to call `/api/v1/auth/signin` instead of mock auth
3. Replace mock data calls with actual API calls
4. Add file storage integration when ready

## Important Notes

- The database URL is already configured for Neon DB
- Tables are automatically created on server startup
- All endpoints require authentication except `/auth/signup` and `/auth/signin`
- CORS is configured for `localhost:5173` (Vite default port)
