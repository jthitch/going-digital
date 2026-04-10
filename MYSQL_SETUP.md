# MySQL / MariaDB setup

The app targets **MySQL or MariaDB** (legacy `gd_*` schema). Configure `.env` and run migrations.

## Environment variables

```ini
DB_NAME=goingdigital
DB_USER=your_user
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=3306
```

## Create database

```bash
mysql -u root -p -e "CREATE DATABASE goingdigital CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

## Install client

```bash
pip install mysqlclient
```

(`requirements.txt` already includes it.)

## Migrate

```bash
python manage.py migrate
```

## Optional: import legacy dump

```bash
mysql -u root -p goingdigital < backup.sql
```

Plan import order vs migrations if the dump overlaps Django-created tables.

## Superuser

```bash
python manage.py createsuperuser
```
