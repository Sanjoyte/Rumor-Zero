# Test commands by part

Hands-on commands for trying each finished part yourself. Every part gets its own section, in
build order. Each command says where to run it: **Terminal** (PowerShell, or the VS Code terminal)
or **Browser**.

Conventions:
- Repo root is `C:\Users\Nafis\Downloads\Rumor-Zero`. Backend commands run in `backend\` with the
  venv active (`.\.venv\Scripts\Activate.ps1`; the prompt shows `(.venv)`).
- A server started with `runserver` keeps its window busy. Run everything else in a second window.
- Real env values are never pasted or printed. Commands that need a secret read it from your own
  `backend\.env` without displaying it.

---

## Part 0A: Backend foundation

### 1. Terminal: start the services

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero
docker compose up -d
docker compose ps                     # postgres and redis both say (healthy)
```

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py migrate              # "No migrations to apply" on a database that is already migrated
python manage.py createsuperuser      # prompts for Email, Username, Password
python manage.py runserver            # leave this window running
```

- The username can't be a reserved word (`admin`, `root`, `staff` and others are blocked). Use
  something like `nafis_admin`.
- Django Admin logs in with the **email**, not the username.

### 2. Browser: while `runserver` is running

| URL | Expect |
|---|---|
| http://localhost:8000/api/health/ | `{"status":"ok"}` |
| http://localhost:8000/admin/ | Login page. Sign in with your email and password. If it 404s, `ADMIN_URL_PATH` in `backend\.env` isn't `admin/`; use that path. |
| http://localhost:8000/admin/accounts/user/ | Your user, plus an "Add user" button |
| http://localhost:8000/admin/core/platformsettings/ | One row with 11 values; no add or delete |

Role check in the admin: add a second user, open it and set **Role = Moderator**, then save.

- "Is staff" (read-only) becomes ticked and Groups shows "Moderators".
- Senior moderator shows both groups; setting the role back to User clears them.
- Your superuser stays staff whatever its role.

### 3. Terminal (second window): deep health

Needs a request header, so it can't be done in the browser.

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero\backend
curl.exe -i http://localhost:8000/api/health/deep/
$secret = (Select-String -Path .\.env -Pattern '^INTERNAL_CRON_SECRET=(.*)$').Matches.Groups[1].Value
curl.exe -i -H "X-RZ-Cron-Secret: $secret" http://localhost:8000/api/health/deep/
```

- First request: **403** with `permission_denied`.
- Second request: **200** with `{"status":"ok","database":"ok","cache":"ok"}`. This proves Postgres
  and Redis.

### 4. Terminal: database rules

Venv active, in `backend\`.

```powershell
python manage.py shell -c "from apps.core.services import get_platform_settings as g; s=g(); print(s.report_threshold, s.emergency_min_reputation)"
python manage.py shell -c "from apps.accounts.models import User; u=User.objects.first(); print(u.reputation_score); User.objects.filter(pk=u.pk).update(reputation_score=150)"
```

- First command prints `5 40`.
- Second prints `50`, then a long traceback ending in
  `IntegrityError ... violates check constraint "accounts_user_reputation_score_range"`. That error
  is the expected result: the database refused a score above 100 and the user keeps 50. The
  traceback shows your email and the start of your password hash, so don't share it.

### 5. Terminal: automated checks

Venv active, in `backend\`. Needs the containers from step 1.

```powershell
python -m pytest                                    # 200 passed
python -m pytest --cov=apps --cov=rumor_zero        # same tests plus coverage (about 93%)
ruff check . ; ruff format --check .                # All checks passed! / files already formatted
python manage.py makemigrations --check --dry-run   # No changes detected
python manage.py check                              # System check identified no issues
```

### 6. Stop and clean up

- Stop the server: `Ctrl+C` in its window.
- Stop the containers and keep the data: `docker compose down` (repo root).
- Wipe the local database (destructive): `docker compose down -v` (repo root).

---

<!-- Add the next part below in the same shape: "## Part <ID>: <title>", then numbered steps,
     each saying Terminal or Browser, each with the exact command and the expected result. -->
