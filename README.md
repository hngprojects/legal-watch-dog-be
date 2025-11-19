# **LEGAL_WATCH_DOG**

**LEGAL_WATCH_DOG** is an AI-powered monitoring platform that automatically tracks policy, regulatory, and data changes across global jurisdictions. Built for enterprise teams, it centralizes monitoring, collaboration, and workflow management, ensuring organisations never miss critical updates and can act on them quickly and confidently.

---

## **Cloning the Repository**

1. **Clone the repository:**

```bash
git clone https://github.com/hngprojects/legal-watch-dog-be.git
```

2. **Navigate into the project directory:**

```bash
cd legal-watch-dog-be
```

3. **Switch to the development branch** (if not already on `dev`):

```bash
git checkout dev
```

---

## **Project Architecture**

```bash
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

---

## **Setup Instructions**

1. **Install UV (if not already installed)**

```bash
# Using curl (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv --version

# Or using pip
pip install uv
uv --version
```

2. **Create a virtual environment:**

```bash
python3 -m venv .venv
python -m venv .venv    #Use for Windows

```

3. **Activate the virtual environment:**

* On macOS/Linux:

```bash
source .venv/bin/activate
```

* On Windows (PowerShell):

```bash
.venv\Scripts\Activate
```

4. **Add project dependencies**
   If you need to add new packages, run:

```bash
uv add <package_name>
```
> This updates `uv.lock` automatically.


5. **Install project dependencies**

```bash
uv sync



6. **Create a `.env` file from `.env.sample`:**

```bash
cp .env.sample .env
```

7. **Run the application locally:**

```bash
uv run python main.py --reload
```

> The app will start on the port defined in your `.env` file (default: `8000`).

---

## **Database Setup**

### Step 1: Create a Database User

```sql
CREATE USER db_user WITH PASSWORD 'your_password';
```

* Replace `db_user` → your preferred database username.
* Replace `'your_password'` → a secure password.

---

### Step 2: Create the Database

```sql
CREATE DATABASE legal_watch_dog_db;
```

* Replace `legal_watch_dog_db` → your preferred database name.

---

### Step 3: Grant Permissions

```sql
GRANT ALL PRIVILEGES ON DATABASE legal_watch_dog_db TO db_user;
```

---
\q

### Step 4: Update `.env` File

```env
DATABASE_URL=postgresql://db_user:your_password@localhost/legal_watch_dog_db
```

---

### Step 5: Verify Connection

```bash
psql -U db_user -d legal_watch_dog_db -h localhost
```

---

### Step 6: Run Database Migrations

```bash
alembic upgrade head
```

> **Do not run** `alembic revision --autogenerate -m 'initial migration'` initially.

---

### Step 7: Updating Migrations

When adding new tables or modifying models:

```bash
alembic revision --autogenerate -m "Migration message"
alembic upgrade head
```

---

## **Running Tests with Pytest**

1. **Run all tests:**

```bash
pytest
```

2. **Run tests with coverage:**

```bash
uv add pytest-cov
pytest --cov=api
```

---

## **Code Quality & Linting**

### Running Linters

1. **Format code with Black:**

```bash
uv run black .
```

2. **Check code style with Flake8:**

```bash
uv run flake8 app/
```

3. **Run both linters together:**

```bash
uv run black . && uv run flake8 app/
```

> Ensure your code passes both Black formatting and Flake8 checks before committing.

---

## **Pre-Commit Hooks (Code Quality)**

1. **Install pre-commit hooks:**

```bash
pre-commit install
```

2. **Manually run on all files:**

```bash
pre-commit run --all-files
```

3. **Fix issues and retry** if a hook fails.

---

## **Contribution Guidelines**

We welcome contributions! Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a pull request to understand our development process, testing requirements, and code standards.