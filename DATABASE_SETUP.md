# Database Setup Guide

This guide explains how to set up the PostgreSQL database for the Investment AI Companion application.

## Prerequisites

1. **PostgreSQL** installed and running
2. **Python** with virtual environment activated
3. **Dependencies** installed (`pip install -r requirements.txt`)

## Quick Setup

### Option 1: Automatic Setup (Recommended)

```bash
# Create tables and seed with sample data
python setup_database.py --seed

# Or just create tables without sample data
python setup_database.py
```

### Option 2: Manual Setup

```bash
# 1. Create database
createdb investment_ai

# 2. Run the application (tables will be created automatically)
python -m uvicorn main:app --reload
```

## Database Configuration

### Environment Variables

Create a `.env` file in your project root:

```env
# Database connection
DATABASE_URL=postgresql://username:password@localhost:5432/investment_ai

# Other settings...
DEBUG=True
SECRET_KEY=your-secret-key-here
```

### Connection String Format

```
postgresql://username:password@host:port/database_name
```

**Examples:**
- Local development: `postgresql://postgres:password@localhost:5432/investment_ai`
- With SSL: `postgresql://user:pass@host:5432/db?sslmode=require`

## Database Schema

### Tables Created

1. **`companies`** - Company information
   - Primary key: `id` (auto-increment)
   - Unique constraints: `ticker`, `(name, ticker)`
   - Indexes: `id`, `name`, `ticker`

2. **`financial_metrics`** - Financial performance data
   - Primary key: `id` (auto-increment)
   - Foreign key: `company_id` → `companies.id`
   - Unique constraint: `(company_id, period_end, period_type)`
   - Indexes: `id`, `company_id`

### Relationships

- **One-to-Many**: Company → Financial Metrics
- **Cascade Delete**: Deleting a company removes all related metrics

## Sample Data

The seed script adds:

- **3 Sample Companies**: Apple, Microsoft, Tesla
- **2 Financial Records**: Apple's 2022-2023 annual metrics

## Troubleshooting

### Common Issues

1. **Connection Refused**
   ```
   Error: connection to server at "localhost" (127.0.0.1), port 5432 failed
   ```
   **Solution**: Start PostgreSQL service

2. **Database Does Not Exist**
   ```
   Error: database "investment_ai" does not exist
   ```
   **Solution**: Create database first: `createdb investment_ai`

3. **Permission Denied**
   ```
   Error: permission denied for database "investment_ai"
   ```
   **Solution**: Check user permissions or create user with proper rights

4. **Port Already in Use**
   ```
   Error: port 5432 is already in use
   ```
   **Solution**: Check if another PostgreSQL instance is running

### PostgreSQL Commands

```bash
# Start PostgreSQL service
sudo systemctl start postgresql

# Connect to PostgreSQL
psql -U postgres

# List databases
\l

# Create database
CREATE DATABASE investment_ai;

# Grant permissions
GRANT ALL PRIVILEGES ON DATABASE investment_ai TO username;

# Exit
\q
```

## Development vs Production

### Development
- Use `setup_database.py` for quick setup
- Sample data included
- Debug mode enabled
- Local PostgreSQL instance

### Production
- Use Alembic migrations for schema changes
- No sample data
- Debug mode disabled
- Managed PostgreSQL service (e.g., AWS RDS, Google Cloud SQL)

## Next Steps

After database setup:

1. **Test the API**: Visit `http://localhost:8000/docs`
2. **Create Companies**: Use POST `/api/v1/companies/`
3. **Add Financial Metrics**: Use POST `/api/v1/financial-metrics/`
4. **Run Tests**: `pytest` (when implemented)

## Alembic Migrations

For future schema changes:

```bash
# Create new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

## Support

If you encounter issues:

1. Check the error messages carefully
2. Verify PostgreSQL is running
3. Confirm database connection string
4. Check user permissions
5. Review the application logs
