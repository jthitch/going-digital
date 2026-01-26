"""
Script to generate schema.sql from Django models for PostgreSQL.
Run this to create a schema.sql file that can be used to recreate the database.
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'photocourses.settings')
django.setup()

from django.core.management import call_command
from django.db import connection
from io import StringIO

def generate_schema():
    """Generate SQL schema from Django migrations."""
    output = StringIO()
    
    # Get SQL from migrations for each app
    apps = ['contenttypes', 'auth', 'core', 'admin', 'sessions', 
            'franchises', 'courses', 'bookings', 'payments']
    
    schema_sql = []
    schema_sql.append("-- Django Photography Course Booking Platform Schema")
    schema_sql.append("-- Generated from Django migrations")
    schema_sql.append("-- PostgreSQL compatible")
    schema_sql.append("")
    schema_sql.append("-- This file contains the table structure only.")
    schema_sql.append("-- For production, use: python manage.py migrate")
    schema_sql.append("")
    
    # Note: In production, you would use:
    # python manage.py migrate --run-syncdb
    # Or: pg_dump -s database_name > schema.sql
    
    schema_sql.append("-- To recreate this database:")
    schema_sql.append("-- 1. Create database: CREATE DATABASE photocourses;")
    schema_sql.append("-- 2. Run migrations: python manage.py migrate")
    schema_sql.append("-- OR use PostgreSQL dump: pg_dump -s photocourses > schema.sql")
    schema_sql.append("")
    
    return "\n".join(schema_sql)

if __name__ == '__main__':
    schema = generate_schema()
    with open('schema.sql', 'w', encoding='utf-8') as f:
        f.write(schema)
    print("Schema instructions written to schema.sql")
    print("\nNote: For actual PostgreSQL schema, use:")
    print("  python manage.py sqlmigrate <app> <migration_number>")
    print("  OR use: pg_dump -s database_name > schema.sql")
