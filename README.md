# LEGAL_WATCH_DOG

LEGAL_WATCH_DOG is an AI-powered monitoring platform that automatically tracks policy, regulatory, and data changes across global jurisdictions. Built for enterprise teams, it centralizes monitoring, collaboration, and workflow management, ensuring organisations never miss critical updates and can act on them quickly and confidently.

## Cloning the Repository

1. Clone the repository:
```bash
git clone https://github.com/hngprojects/legal-watch-dog-be.git
```

2. Navigate into the project directory:
```bash
cd legal-watch-dog-be
```

3. Switch to the development branch (if not already on dev):
```bash
git checkout dev
```

## Project Architecture

```
legal-watch-dog-be/
│
├── alembic/                             # Alembic migration system
│   ├── versions/                        # Auto-generated migration scripts
│   ├── env.py                           # Alembic environment setup
│   ├── script.py.mako                   # Template for migration scripts
│   └── README                           # Alembic docs / notes
│
├── app/                                 # Main application package
│   ├── __init__.py
│   │
│   ├── api/                             # API layer for routing and versioning
│   │   ├── __init__.py
│   │   │
│   │   ├── core/                        # Core API utilities & config
│   │   │   ├── dependencies/            # Depends(), email utilities, etc.
│   │   │   │   └── email/
│   │   │   │       └── __init__.py
│   │   │   ├── middleware/              # App middlewares (auth, logging, etc.)
│   │   │   │   └── __init__.py
│   │   │   └── config.py                # Core config models/settings
│   │   │
│   │   ├── db/                          # Database module
│   │   │   ├── __init__.py
│   │   │   └── database.py              # DB engine/session setup (SQLModel)
│   │   │
│   │   ├── utils/                       # Helper utilities shared across API
│   │   │   └── __init__.py
│   │   │
│   │   ├── modules/                     # Modules folder for API versions
│   │       └── v1/                      # Version 1 of the API
│   │           ├── __init__.py
│   │           │
│   │           ├── api_access/          # API Access module
│   │           │   ├── __init__.py
│   │           │   ├── models/
│   │           │   ├── routes/
│   │           │   ├── schemas/
│   │           │   └── service/
│   │           │
│   │           ├── auth/                 # Authentication module
│   │           │   ├── __init__.py
│   │           │   ├── models/
│   │           │   ├── routes/
│   │           │   ├── schemas/
│   │           │   └── service/
│   │           │
│   │           ├── jurisdictions/       # Jurisdictions module
│   │           │   ├── __init__.py
│   │           │   ├── models/
│   │           │   ├── routes/
│   │           │   ├── schemas/
│   │           │   └── service/
│   │           │
│   │           ├── notifications/       # Notifications module
│   │           │   ├── __init__.py
│   │           │   ├── models/
│   │           │   ├── routes/
│   │           │   ├── schemas/
│   │           │   └── service/
│   │           │
│   │           ├── organization/        # Organization module
│   │           │   ├── __init__.py
│   │           │   ├── models/
│   │           │   ├── routes/
│   │           │   ├── schemas/
│   │           │   └── service/
│   │           │
│   │           ├── projects/            # Projects module
│   │           │   ├── __init__.py
│   │           │   ├── models/
│   │           │   ├── routes/
│   │           │   ├── schemas/
│   │           │   └── service/
│   │           │
│   │           ├── scraping/            # Scraping module
│   │           │   ├── __init__.py
│   │           │   ├── models/
│   │           │   ├── routes/
│   │           │   ├── schemas/
│   │           │   └── service/
│   │           │
│   │           ├── tickets/             # Tickets module
│   │           │   ├── __init__.py
│   │           │   ├── models/
│   │           │   ├── routes/
│   │           │   ├── schemas/
│   │           │   └── service/
│   │           │
│   │           ├── users/               # Users module
│   │           │   ├── __init__.py
│   │           │   ├── models/
│   │           │   ├── routes/
│   │           │   ├── schemas/
│   │           │   └── service/
│   │           │
│   │           └── waitlist/            # Waitlist module
│   │               ├── __init__.py
│   │               ├── models/
│   │               ├── routes/
│   │               ├── schemas/
│   │               └── service/
│
├── tests/                               # Test suite (pytest)
│   └── __init__.py
│
├── .venv/                               # Local virtual environment
├── .env                                 # Local environment variables
├── .env.sample                          # Template for environment variables
├── .gitignore                           # Files/folders to ignore in Git
├── .python-version                      # Python version used by pyenv
├── alembic.ini                          # Alembic configuration file
├── CONTRIBUTING.md                      # Guidelines for contributors
├── LICENSE                              # License information (MIT, Apache, etc.)
├── main.py                              # FastAPI app entry point
├── pyproject.toml                       # Project dependencies + build config
├── README.md                            # Documentation & setup guide
├── uv.lock                              # Lockfile generated by uv
```

## Setup Instructions

### Install UV (if not already installed)

```bash
# Using curl (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv --version

# Or using pip
pip install uv
uv --version
```

### Create a virtual environment

```bash
python3 -m venv .venv
```

### Activate the virtual environment

**On macOS/Linux:**
```bash
source .venv/bin/activate
```

**On Windows (PowerShell):**
```bash
.venv\Scripts\Activate
```

### Install project dependencies with UV

```bash
uv sync
```

This command reads `pyproject.toml` and installs all project dependencies into your virtual environment.

### Create a .env file from .env.sample

```bash
cp .env.sample .env
```

### Run the application locally

```bash
uv run python main.py --reload
```

The app will start on the port defined in your `.env` file (default: 8000).

## Alternative Setup (if you prefer pip)

If you want to use traditional pip instead of UV:

```bash
# Install dependencies from pyproject.toml
pip install -e .

# Or if you have a requirements.txt file
pip install -r requirements.txt
```

## Database Setup

### Step 1: Create a Database User

```sql
CREATE USER db_user WITH PASSWORD 'your_password';
```

- Replace `db_user` → your preferred database username.
- Replace `'your_password'` → a secure password.

### Step 2: Create the Database

```sql
CREATE DATABASE legal_watch_dog_db;
```

Replace `legal_watch_dog_db` → your preferred database name.

### Step 3: Grant Permissions

```sql
GRANT ALL PRIVILEGES ON DATABASE legal_watch_dog_db TO db_user;
```

### Step 4: Update .env File

```env
DATABASE_URL=postgresql://db_user:your_password@localhost/legal_watch_dog_db
```

### Step 5: Verify Connection

```bash
psql -U db_user -d legal_watch_dog_db -h localhost
```

### Step 6: Run Database Migrations

```bash
alembic upgrade head
```

**Note:** Do not run `alembic revision --autogenerate -m 'initial migration'` initially.

### Step 7: Updating Migrations

When adding new tables or modifying models:

```bash
alembic revision --autogenerate -m "Migration message"
alembic upgrade head
```

## Running Tests with Pytest

### Run all tests

```bash
pytest
```

### Run tests with coverage

```bash
uv add pytest-cov
pytest --cov=api
```

## Code Quality & Linting

### Running Linters

**Format code with Black:**
```bash
uv run black .
```

**Check code style with Flake8:**
```bash
uv run flake8 app/
```

**Run both linters together:**
```bash
uv run black . && uv run flake8 app/
```

Ensure your code passes both Black formatting and Flake8 checks before committing.

### Pre-Commit Hooks (Code Quality)

**Install pre-commit hooks:**
```bash
pre-commit install
```

**Manually run on all files:**
```bash
pre-commit run --all-files
```

Fix issues and retry if a hook fails.

## Contribution Guidelines

We welcome contributions! Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a pull request to understand our development process, testing requirements, and code standards.

## Troubleshooting

### Common Issues

- **Dependencies not installed:** Make sure you ran `uv sync` after creating the virtual environment
- **Database connection issues:** Verify your `.env` file has the correct `DATABASE_URL` and that PostgreSQL is running
- **Migration errors:** Ensure you've created the database and user before running `alembic upgrade head`

### Getting Help

If you encounter any issues during setup, please:

1. Check that all steps in this README have been followed exactly
2. Ensure all required services (PostgreSQL) are running
3. Check the project's issue tracker for similar problems
4. Create a new issue with detailed information about your setup and the error
