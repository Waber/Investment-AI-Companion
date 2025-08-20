#!/usr/bin/env python3
"""
Database setup script for Investment AI Companion.
This script initializes the database and optionally seeds it with sample data.

Usage:
    python setup_database.py          # Just create tables
    python setup_database.py --seed   # Create tables and add sample data
"""

import argparse
import sys
from sqlalchemy.orm import Session

# Add the project root to Python path
sys.path.append('.')

from app.core.database import engine, SessionLocal
from app.core.init_db import init_db, seed_sample_data

def main():
    parser = argparse.ArgumentParser(description='Setup database for Investment AI Companion')
    parser.add_argument('--seed', action='store_true', help='Seed database with sample data')
    args = parser.parse_args()
    
    print("🚀 Setting up database for Investment AI Companion...")
    
    try:
        # Initialize database (create tables)
        print("📋 Creating database tables...")
        init_db()
        print("✅ Database tables created successfully!")
        
        if args.seed:
            print("🌱 Seeding database with sample data...")
            # Create a database session for seeding
            db = SessionLocal()
            try:
                seed_sample_data(db)
                print("✅ Sample data seeded successfully!")
            finally:
                db.close()
        else:
            print("💡 Tip: Run with --seed to add sample data")
        
        print("\n🎉 Database setup complete!")
        print("You can now run the application with: python -m uvicorn main:app --reload")
        
    except Exception as e:
        print(f"❌ Error setting up database: {e}")
        print("\n🔧 Troubleshooting tips:")
        print("1. Make sure PostgreSQL is running")
        print("2. Check your .env file has correct DATABASE_URL")
        print("3. Ensure the database exists")
        print("4. Verify your user has CREATE permissions")
        sys.exit(1)

if __name__ == "__main__":
    main()
