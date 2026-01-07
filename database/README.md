# Database Setup & Management

This guide covers local database setup, running migrations, and Kubernetes deployment.

## Table of Contents

1. [Local Setup](#local-setup)
2. [Running Migrations](#running-migrations)
3. [Database Models](#database-models)
4. [Kubernetes Deployment](#kubernetes-deployment)

---

## Local Setup

### Prerequisites

- Python 3.9+
- PostgreSQL 15 (or Docker)
- Virtual environment

### Option 1: Using Docker Compose (Recommended)

The easiest way to set up the database locally is using Docker Compose.

1. **Start PostgreSQL**

```bash
docker-compose up -d
```

This will:

- Start a PostgreSQL 15 container
- Create a database named `pdf_converter`
- Set up credentials: `pdf_user` / `pdf_pass`
- Listen on `localhost:5432`
- Persist data in a Docker volume (`pgdata`)

2. **Verify the connection**

```bash
psql -U pdf_user -d pdf_converter -h localhost -c "SELECT 1;"
```

### Option 2: Manual PostgreSQL Installation

If you have PostgreSQL installed locally:

1. **Create a database and user**

```bash
psql -U postgres -c "CREATE USER pdf_user WITH PASSWORD 'pdf_pass';"
psql -U postgres -c "CREATE DATABASE pdf_converter OWNER pdf_user;"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE pdf_converter TO pdf_user;"
```

### Configure Environment

1. **Create a `.env` file** in the project root (if not already present):

```bash
cp .env.example .env
```

2. **Update `.env` with your database URL**

```
DATABASE_URL=postgresql+psycopg://pdf_user:pdf_pass@localhost:5432/pdf_converter
```

For Docker Compose, use the same URL as above. For manual setup, adjust `localhost` or password as needed.

### Install Dependencies

```bash
pip install -r requirements.txt
```

This includes:

- `SQLAlchemy>=2.0` - ORM
- `alembic>=1.13` - Migration tool
- `psycopg[binary]>=3.1` - PostgreSQL driver

---

## Running Migrations

Migrations are managed using **Alembic**. The `migrate.py` script in the project root provides a CLI interface.

### How Migrations Work

1. Migration files live in `database/alembic/versions/`
2. Each migration has an `upgrade()` and `downgrade()` function
3. The migration script tracks which versions have been applied

### Apply Migrations (Recommended)

```bash
# Apply all pending migrations to HEAD
python migrate.py upgrade head

# Apply a specific number of migrations
python migrate.py upgrade +2

# Apply up to a specific revision
python migrate.py upgrade <revision_id>
```

**Example:**

```bash
# First time setup
python migrate.py upgrade head
```

### Create a New Migration

1. **Modify a model** in `database/models/` (e.g., add a new field, new table)

2. **Create a migration file**

```bash
python migrate.py revision -m "Add new_field to City"
```

This creates a new file in `database/alembic/versions/` like:

```
20250107_150000_add_new_field_to_city.py
```

3. **Implement the migration**

Edit the generated file and fill in the `upgrade()` and `downgrade()` functions:

```python
def upgrade() -> None:
    # What to do when applying this migration
    op.add_column('city', sa.Column('new_field', sa.String(255), nullable=True))

def downgrade() -> None:
    # How to undo this migration
    op.drop_column('city', 'new_field')
```

4. **Apply the migration**

```bash
python migrate.py upgrade head
```

### Rollback Migrations

```bash
# Rollback the last applied migration
python migrate.py downgrade -1

# Rollback to a specific revision
python migrate.py downgrade <revision_id>

# Rollback all migrations
python migrate.py downgrade base
```

### Check Migration Status

To see which migrations have been applied:

```bash
# View all migration history
psql -U pdf_user -d pdf_converter -h localhost -c "SELECT * FROM alembic_version;"
```

---

## Database Models

The data model is centered around the **City** entity. Here's the hierarchy:

### Core Tables

- **City** - Real-world city, central anchor point
- **ClimateCityContract** - Climate contract document for a city (1:1)
- **Sector** - Taxonomy for sectors (GPC, CCC, etc.)

### Emissions

- **EmissionRecord** - Time series of GHG emissions by city, sector, and year

### Budgets & Funding

- **Budget** - City budget for a given year
- **FundingSource** - Money sources (EU Green Fund, etc.)
- **BudgetFunding** - Links budgets to funding sources (many-to-many)

### Initiatives & Stakeholders

- **Initiative** - Programs/projects run by a city
- **Stakeholder** - Actors (city dept, NGO, company, etc.)
- **InitiativeStakeholder** - Links initiatives to stakeholders with roles (many-to-many)

### Indicators & Targets

- **Indicator** - What is measured (citywide or sector-specific)
- **IndicatorValue** - Time series values for an indicator
- **CityTarget** - City's official targets (e.g., 2030 or 2050 goals)
- **InitiativeIndicator** - Links initiatives to indicators (many-to-many)

### Reference

For a detailed data model diagram, see: [DBDiagram](https://dbdiagram.io/d/NZCs-Data-Model-69160b2e6735e11170b30725)

### Naming Convention

The database uses a consistent naming convention for constraints and indexes:

```python
- Indexes: ix_<table>_<column>
- Unique constraints: uq_<table>_<column>
- Check constraints: ck_<table>_<constraint_name>
- Foreign keys: fk_<table>_<column>_<referenced_table>
- Primary keys: pk_<table>
```

---

## Kubernetes Deployment

The database is deployed in Kubernetes using a PostgreSQL service and migrations run as a Job.

### Files

- `k8s/pdf-converter-db-configmap.yml` - ConfigMap with database credentials
- `k8s/pdf-converter-migrate.yml` - Job to run migrations

### Prerequisites

- Kubernetes cluster (EKS, GKE, AKS, or local kind/minikube)
- `kubectl` configured
- Docker image pushed to a registry (e.g., `ghcr.io/open-earth-foundation/pdf-converter:latest`)

### Configuration

#### 1. Database ConfigMap

Update `k8s/pdf-converter-db-configmap.yml` with your database host:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: pdf-converter-db-configmap
  namespace: default
data:
  DB_HOST: "your-db-host" # ← Update this
  DB_PORT: "5432"
  DB_USER: "pdf_user"
  DB_PASSWORD: "pdf_pass"
  DB_NAME: "pdf_converter"
  DATABASE_URL: "postgresql+psycopg://pdf_user:pdf_pass@your-db-host:5432/pdf_converter"
```

**Example values:**

- **RDS (AWS)**: `pdf-converter-db.c9akciq32.us-east-1.rds.amazonaws.com`
- **Google Cloud SQL**: `10.0.0.3` (internal IP)
- **Self-hosted in-cluster**: `postgres.database.svc.cluster.local` (if running in `database` namespace)
- **Docker desktop**: `host.docker.internal` (for local K8s)

#### 2. Apply ConfigMap

```bash
kubectl apply -f k8s/pdf-converter-db-configmap.yml
```

### Running Migrations in Kubernetes

The migration runs as a **Kubernetes Job**. It:

1. Uses the same Docker image as the app
2. Reads the `DATABASE_URL` from ConfigMap
3. Runs `python migrate.py upgrade head`
4. Completes when done (does not restart)

#### Deploy Migration Job

```bash
kubectl apply -f k8s/pdf-converter-migrate.yml
```

#### Monitor the Job

```bash
# Check job status
kubectl get jobs

# View logs
kubectl logs job/pdf-converter-migrate

# Describe the job (see why it failed, if it did)
kubectl describe job pdf-converter-migrate

# View pod details
kubectl get pods | grep migrate
kubectl describe pod <pod-name>
```

#### Retry or Delete a Job

```bash
# Delete the job to run migrations again
kubectl delete job pdf-converter-migrate

# Then reapply
kubectl apply -f k8s/pdf-converter-migrate.yml
```

### Backoff Behavior

The Job is configured with `backoffLimit: 3`, meaning:

- If the migration fails, it will retry up to 3 times
- After 3 failures, the job stays in a failed state (does not keep retrying)

### Best Practices for K8s Deployment

1. **Run migrations before the app**

   - Use an init container or ensure migrations complete before deploying the app
   - This prevents the app from crashing due to missing tables

2. **Use a separate database service or managed service**

   - Don't run PostgreSQL in Kubernetes unless you have persistence configured
   - Use AWS RDS, Google Cloud SQL, or similar for production

3. **Secrets management**

   - Store passwords in Kubernetes Secrets instead of ConfigMap
   - Update the Job to reference the secret:
     ```yaml
     env:
       - name: DATABASE_URL
         valueFrom:
           secretKeyRef:
             name: pdf-converter-db-secret
             key: DATABASE_URL
     ```

4. **Namespace isolation**
   - Use separate namespaces for dev, staging, and production
   - Update the ConfigMap/Job metadata with the correct namespace

### Example: Using Secrets

Create a secret:

```bash
kubectl create secret generic pdf-converter-db-secret \
  --from-literal=DATABASE_URL='postgresql+psycopg://pdf_user:pdf_pass@my-db-host:5432/pdf_converter'
```

Then update `k8s/pdf-converter-migrate.yml`:

```yaml
env:
  - name: DATABASE_URL
    valueFrom:
      secretKeyRef:
        name: pdf-converter-db-secret
        key: DATABASE_URL
```

---

## Troubleshooting

### Error: `DATABASE_URL is not set`

**Cause**: The `DATABASE_URL` environment variable is not set.

**Solution**: Set it before running migrations:

```bash
export DATABASE_URL="postgresql+psycopg://pdf_user:pdf_pass@localhost:5432/pdf_converter"
python migrate.py upgrade head
```

Or ensure `.env` file exists with the variable set.

### Error: `psycopg.OperationalError: connection refused`

**Cause**: PostgreSQL is not running or the host/port is wrong.

**Solution**:

```bash
# Check if postgres is running (Docker)
docker-compose ps

# Start it if needed
docker-compose up -d

# Or test manual connection
psql -U pdf_user -d pdf_converter -h localhost
```

### Error: `FATAL: permission denied for database "pdf_converter"`

**Cause**: The user doesn't have permissions.

**Solution**: Verify user permissions:

```bash
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE pdf_converter TO pdf_user;"
```

### Migration file exists but won't apply

**Cause**: The migration may be in an inconsistent state.

**Solution**:

```bash
# Check the alembic_version table
psql -U pdf_user -d pdf_converter -h localhost -c "SELECT * FROM alembic_version;"

# Manually fix if needed (use with caution)
psql -U pdf_user -d pdf_converter -h localhost -c "DELETE FROM alembic_version WHERE version_num = '<revision_id>';"
```

---

## Quick Reference

### Local Development

```bash
# Start database
docker-compose up -d

# Install dependencies
pip install -r requirements.txt

# Set environment
export DATABASE_URL="postgresql+psycopg://pdf_user:pdf_pass@localhost:5432/pdf_converter"

# Run migrations
python migrate.py upgrade head
```

### Create and Apply Migration

```bash
python migrate.py revision -m "Your migration description"
python migrate.py upgrade head
```

### Kubernetes Deployment

```bash
# Apply configuration
kubectl apply -f k8s/pdf-converter-db-configmap.yml

# Run migrations
kubectl apply -f k8s/pdf-converter-migrate.yml

# Monitor
kubectl logs job/pdf-converter-migrate -f
```
