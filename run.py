#!/usr/bin/env python3
"""
Unified project setup.

Handles three scenarios:
  1. Connect to an existing Supabase database (validate schema + cases)
  2. Set up a new Supabase project (create tables, validate, write secrets)
  3. Dry run (verify local artifacts only, no database)

Usage:
    python setup.py

The script is interactive and guides you through each step.
"""

import hashlib
import json
import os
import sys
import textwrap

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
PLATFORM_DIR = os.path.join(PROJECT_ROOT, "experiment_platform")
SECRETS_PATH = os.path.join(PLATFORM_DIR, ".streamlit", "secrets.toml")
SQL_PATH = os.path.join(PLATFORM_DIR, "setup_supabase.sql")
LOCK_FILE = os.path.join(PROJECT_ROOT, "artifacts", "cases.lock")

sys.path.insert(0, PLATFORM_DIR)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "codes"))


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def heading(text):
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}\n")


def step(n, text):
    print(f"\n--- Step {n}: {text} ---\n")


def success(text):
    print(f"  [OK] {text}")


def fail(text):
    print(f"  [FAIL] {text}")


def warn(text):
    print(f"  [WARN] {text}")


def ask(prompt, default=None):
    if default:
        result = input(f"  {prompt} [{default}]: ").strip()
        return result if result else default
    return input(f"  {prompt}: ").strip()


def ask_yn(prompt, default="y"):
    result = ask(f"{prompt} (y/n)", default).lower()
    return result in ("y", "yes")


# ---------------------------------------------------------------------------
# Step 1: Case integrity
# ---------------------------------------------------------------------------

def check_case_integrity():
    step(1, "Verifying frozen case data")

    try:
        from config import EXPERIMENTAL_CASES, PRACTICE_CASES
    except ImportError:
        fail("Cannot import config.py from experiment_platform/")
        fail("Make sure you're running this from the project root.")
        return False

    n_exp = len(EXPERIMENTAL_CASES)
    n_pra = len(PRACTICE_CASES)
    print(f"  Found {n_exp} experimental cases + {n_pra} practice cases in config.py")

    if n_exp != 18:
        fail(f"Expected 18 experimental cases, got {n_exp}")
        return False
    if n_pra != 2:
        fail(f"Expected 2 practice cases, got {n_pra}")
        return False

    # Check lock file
    if os.path.exists(LOCK_FILE):
        from verify_cases import verify_cases
        try:
            verify_cases(EXPERIMENTAL_CASES, PRACTICE_CASES)
            success("Case integrity verified against lock file.")
        except RuntimeError as e:
            fail(str(e))
            return False
    else:
        warn("No lock file found. Creating one now...")
        from verify_cases import lock_cases
        h = lock_cases(EXPERIMENTAL_CASES, PRACTICE_CASES)
        success(f"Lock file created: {LOCK_FILE}")
        success(f"Hash: {h}")

    # Basic sanity checks on case content
    difficulties = set(c["difficulty_tier"] for c in EXPERIMENTAL_CASES)
    blocks = set(c["block"] for c in EXPERIMENTAL_CASES)
    y_values = [c["y_true"] for c in EXPERIMENTAL_CASES]

    if difficulties != {"easy", "medium", "hard"}:
        fail(f"Expected 3 difficulty tiers, got {difficulties}")
        return False
    if blocks != {"block_1", "block_2", "block_3"}:
        fail(f"Expected 3 blocks, got {blocks}")
        return False
    if sum(y_values) != 9:
        fail(f"Expected 9 defaults in 18 cases, got {sum(y_values)}")
        return False

    success("Case design: 18 cases, 3 difficulty tiers, 3 blocks, 9/9 default split.")
    return True


# ---------------------------------------------------------------------------
# Step 2: Secrets / credentials
# ---------------------------------------------------------------------------

def check_or_create_secrets():
    """Returns (url, key) or (None, None) for dry run."""
    step(2, "Supabase credentials")

    if os.path.exists(SECRETS_PATH):
        print(f"  Found existing secrets at {SECRETS_PATH}")
        if ask_yn("Use existing credentials?"):
            url, key = _read_secrets()
            if url and key:
                success(f"URL: {url[:40]}...")
                return url, key
            else:
                fail("Could not parse secrets file.")

    print()
    print("  Options:")
    print("    1) Enter Supabase credentials (existing or new project)")
    print("    2) Dry run (skip database, verify local artifacts only)")
    print()
    choice = ask("Choose (1 or 2)", "1")

    if choice == "2":
        print("  Proceeding in dry-run mode (no database).")
        return None, None

    print()
    print(textwrap.dedent("""
    To get your Supabase credentials:
      1. Go to https://supabase.com and create a project (or open existing)
      2. Go to Settings > API
      3. Copy the "Project URL" and "anon public" key
    """).strip())
    print()

    url = ask("Supabase Project URL")
    key = ask("Supabase anon key")

    if not url or not key:
        fail("URL and key are required.")
        return None, None

    # Write secrets file
    os.makedirs(os.path.dirname(SECRETS_PATH), exist_ok=True)
    with open(SECRETS_PATH, "w") as f:
        f.write("[supabase]\n")
        f.write(f'url = "{url}"\n')
        f.write(f'anon_key = "{key}"\n')

    success(f"Secrets written to {SECRETS_PATH}")
    warn("This file is gitignored and should NEVER be committed.")

    return url, key


def _read_secrets():
    """Parse the TOML secrets file manually (avoid toml dependency)."""
    url = None
    key = None
    try:
        with open(SECRETS_PATH) as f:
            for line in f:
                line = line.strip()
                if line.startswith("url"):
                    url = line.split("=", 1)[1].strip().strip('"').strip("'")
                elif line.startswith("anon_key"):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return url, key


# ---------------------------------------------------------------------------
# Step 3: Database connection test
# ---------------------------------------------------------------------------

def test_connection(url, key):
    step(3, "Testing database connection")

    try:
        from supabase import create_client
    except ImportError:
        fail("supabase package not installed. Run: pip install supabase")
        return None

    try:
        client = create_client(url, key)
        # Try a simple query
        result = client.table("participants").select("id").limit(1).execute()
        success("Connected to Supabase successfully.")
        success("'participants' table exists.")
        return client
    except Exception as e:
        error_str = str(e)
        if "relation" in error_str and "does not exist" in error_str:
            warn("Connected to Supabase, but tables don't exist yet.")
            return "NEEDS_SETUP"
        elif "Invalid API key" in error_str or "401" in error_str:
            fail("Invalid API key. Check your anon key.")
            return None
        elif "Could not resolve host" in error_str or "ConnectionError" in error_str:
            fail(f"Cannot reach Supabase at {url}. Check the URL.")
            return None
        else:
            warn(f"Connection issue: {error_str}")
            warn("Tables may not exist yet. Proceeding to schema setup.")
            return "NEEDS_SETUP"


# ---------------------------------------------------------------------------
# Step 4: Schema setup
# ---------------------------------------------------------------------------

def setup_schema(url, key):
    step(4, "Setting up database schema")

    if not os.path.exists(SQL_PATH):
        fail(f"SQL file not found at {SQL_PATH}")
        return False

    print(textwrap.dedent("""
    The database tables need to be created. You have two options:

    Option A (recommended): Run the SQL manually in Supabase Dashboard
      1. Open your project at https://supabase.com
      2. Go to SQL Editor
      3. Paste the contents of experiment_platform/setup_supabase.sql
      4. Click "Run"

    Option B: This script will attempt to run the SQL via the API
      (This requires the service_role key, not the anon key)
    """).strip())
    print()

    choice = ask("Did you already run the SQL? (y = already done / n = need help)", "n")

    if choice.lower() in ("y", "yes"):
        success("Schema assumed to be set up. Will verify in next step.")
        return True

    print()
    print("  Since running DDL via the anon key is restricted,")
    print("  please run the SQL manually in the Supabase SQL Editor.")
    print()
    print(f"  SQL file location: {SQL_PATH}")
    print()
    input("  Press Enter after you've run the SQL...")

    return True


# ---------------------------------------------------------------------------
# Step 5: Schema validation
# ---------------------------------------------------------------------------

def validate_schema(client):
    step(5, "Validating database schema")

    expected_tables = {
        "participants": [
            "id", "participant_number", "participant_group", "age_range",
            "education", "completed", "trust_rating", "self_reported_reliance",
            "ai_surprise_strategy", "total_cost", "optimal_cost", "session_id",
            "current_trial_index", "current_phase",
        ],
        "trials": [
            "id", "participant_id", "trial_index", "case_id", "protocol",
            "difficulty_tier", "y_true", "pred_prob", "decision_final",
            "prob_estimate_final", "total_trial_ms",
        ],
        "quiz_responses": [
            "id", "participant_id", "attempt", "question_id",
            "selected_answer", "is_correct",
        ],
    }

    all_ok = True
    for table, required_cols in expected_tables.items():
        try:
            # Attempt to select required columns
            cols = ",".join(required_cols[:3])  # just test a few
            result = client.table(table).select(cols).limit(0).execute()
            success(f"Table '{table}' exists and is accessible.")
        except Exception as e:
            fail(f"Table '{table}': {e}")
            all_ok = False

    if all_ok:
        # Check data state
        try:
            p_count = client.table("participants").select("id", count="exact").execute()
            t_count = client.table("trials").select("id", count="exact").execute()
            n_participants = p_count.count if hasattr(p_count, 'count') else len(p_count.data)
            n_trials = t_count.count if hasattr(t_count, 'count') else len(t_count.data)
            print(f"\n  Current data: {n_participants} participants, {n_trials} trials")
            if n_participants > 0:
                warn("Database contains existing data.")
                if ask_yn("Is this test data that should be cleared before deployment?", "n"):
                    print("\n  To reset, run in Supabase SQL Editor:")
                    print("    DELETE FROM quiz_responses;")
                    print("    DELETE FROM trials;")
                    print("    DELETE FROM participants;")
                    print("    ALTER SEQUENCE participants_participant_number_seq RESTART WITH 1;")
                    print()
                    input("  Press Enter after resetting (or skip)...")
        except Exception:
            warn("Could not count existing rows (non-critical).")

    return all_ok


# ---------------------------------------------------------------------------
# Step 6: Deployment readiness
# ---------------------------------------------------------------------------

def check_deployment_readiness():
    step(6, "Deployment readiness check")

    checks = []

    # Check requirements.txt
    req_path = os.path.join(PROJECT_ROOT, "requirements.txt")
    if os.path.exists(req_path):
        success("requirements.txt exists")
        checks.append(True)
    else:
        fail("requirements.txt missing")
        checks.append(False)

    # Check .gitignore
    gitignore_path = os.path.join(PLATFORM_DIR, ".gitignore")
    if os.path.exists(gitignore_path):
        success(".gitignore exists in experiment_platform/")
        # Check that secrets.toml is gitignored
        with open(gitignore_path) as f:
            content = f.read()
        if "secrets.toml" in content:
            success("secrets.toml is gitignored")
        else:
            warn("secrets.toml may not be gitignored!")
        checks.append(True)
    else:
        warn(".gitignore missing in experiment_platform/")
        checks.append(True)  # non-fatal

    # Check config.toml (theme)
    config_toml = os.path.join(PLATFORM_DIR, ".streamlit", "config.toml")
    if os.path.exists(config_toml):
        with open(config_toml) as f:
            content = f.read()
        if 'base = "light"' in content:
            success("Light theme forced in config.toml")
        else:
            warn("Theme may not be set to light in config.toml")
        checks.append(True)
    else:
        warn("config.toml missing — theme may vary across browsers")
        checks.append(True)

    # Check all platform files exist
    required_files = [
        "app.py", "config.py", "screens.py", "ui_components.py",
        "database.py", "experiment_logic.py", "utils.py",
    ]
    for f in required_files:
        path = os.path.join(PLATFORM_DIR, f)
        if os.path.exists(path):
            success(f"{f}")
        else:
            fail(f"{f} MISSING")
            checks.append(False)

    return all(checks)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    heading("CAPSTONE PROJECT SETUP")
    print("This script validates your project and sets up the experiment database.")
    print("It will guide you through each step interactively.\n")

    # Step 1: Cases
    cases_ok = check_case_integrity()
    if not cases_ok:
        fail("Case integrity check failed. Fix before proceeding.")
        sys.exit(1)

    # Step 2: Credentials
    url, key = check_or_create_secrets()
    dry_run = url is None

    if dry_run:
        step(3, "Dry run mode — skipping database steps")
        success("Local artifacts verified.")
        check_deployment_readiness()
        heading("DRY RUN COMPLETE")
        print("To fully set up, rerun this script and provide Supabase credentials.")
        return

    # Step 3: Connection
    client = test_connection(url, key)

    if client is None:
        fail("Cannot connect to Supabase. Check credentials and try again.")
        sys.exit(1)

    if client == "NEEDS_SETUP":
        # Step 4: Schema setup
        setup_schema(url, key)
        # Retry connection
        client = test_connection(url, key)
        if client is None or client == "NEEDS_SETUP":
            fail("Tables still not found. Please run the SQL manually and rerun setup.")
            sys.exit(1)

    # Step 5: Validate schema
    schema_ok = validate_schema(client)
    if not schema_ok:
        fail("Schema validation failed. Check the SQL setup.")
        sys.exit(1)

    # Step 6: Deployment readiness
    deploy_ok = check_deployment_readiness()

    # Summary
    heading("SETUP COMPLETE")
    print("Next steps:")
    print("  1. Deploy to Streamlit Cloud (or run locally: streamlit run experiment_platform/app.py)")
    print("  2. Run 3 end-to-end test sessions (one per group) in incognito")
    print("  3. Verify trials table has correct protocol assignments")
    print("  4. Reset test data (SQL above)")
    print("  5. Share the URL with participants")
    print()
    if not deploy_ok:
        warn("Some deployment checks had warnings — review above.")


if __name__ == "__main__":
    main()