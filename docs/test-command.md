# Test commands by part

Hands-on commands for trying each finished part yourself, in build order (Parts 0A, 0B, 0D, 0C, 1, 2, 3, 4, 5, 6, 7, 7B, 8, 9).
The file has two complete guides. Pick the one for your computer and stay in it:

- [Guide 1: Linux (bash)](#guide-1-linux-bash)
- [Guide 2: Windows (PowerShell)](#guide-2-windows-powershell)

How to read a step:

- **Where** says which window to use: *Terminal window 1* (the server, which stays busy), *Terminal
  window 2* (where you type the commands), or the *Browser*.
- **What this does** says why you run it. **You should see** shows the output you should get and what
  it means. **If it differs** appears only where there is a known cause.
- Variables such as `access` or `id` live only in the terminal that set them. A step that needs one
  says which earlier step sets it. Opening a new terminal loses them, so redo that step.
- Real env values are never pasted or printed. Commands that need a secret read it from your own
  `backend/.env` without displaying it.
- Counts in the expected output (tests, packages, vulnerabilities) were recorded when each part was
  finished and drift later. The current totals are in `docs/agents/HANDOFF.md`.

---

## Guide 1: Linux (bash)

- Blocks assume a new terminal in the repo root (wherever you cloned it) and use paths relative to it.
  Backend commands run in `backend/` with the venv active (`source .venv/bin/activate`; the prompt
  shows `(.venv)`). JSON commands need `jq` (`sudo apt install jq`, SETUP.md A7). SETUP.md
  "Quick start" runs the same automated checks in one go.
- A server started with `runserver` keeps its window busy. Run everything else in a second window.
- Some recorded outputs were captured on Windows; where Linux prints something different (path
  separators, which address `localhost` resolves to), a note says so.

### Part 0A: Backend foundation

This part starts the local database and cache, runs the Django backend, and checks that it works.

| Window | Used for | Stays busy? |
|---|---|---|
| Terminal window 1 (server) | Steps 1 to 2: containers, migrate, create your admin user, `runserver` | Yes, `runserver` keeps it busy. Leave it running. |
| Terminal window 2 (commands) | Steps 3 to 5: health checks, database rules, tests | No |
| Browser | Step 2 | - |

#### Step 1: Start the services and the backend server

**Where:** Terminal window 1 (server), in the repo root first, then in `backend/`.

**What this does:** `docker compose` starts Postgres (the database) and Redis (the cache) in containers. Then you prepare the backend, create your own admin account and start the Django development server.

```bash
# from the repo root
docker compose up -d
docker compose ps                     # postgres and redis both say (healthy)
```

**You should see:** two rows, `postgres` and `redis`, both with `(healthy)`. If they say `starting`, wait a few seconds and run `docker compose ps` again.

```bash
cd backend
source .venv/bin/activate
python manage.py migrate              # "No migrations to apply" on a database that is already migrated
python manage.py createsuperuser      # prompts for Email, Username, Password
python manage.py runserver            # leave this window running
```

**You should see:** after `source .venv/bin/activate` the prompt starts with `(.venv)`. `migrate` ends with "No migrations to apply" if the database is already migrated (a fresh database lists many `Applying ...` lines instead). `createsuperuser` asks you for an email, a username and a password (the password is not shown while you type). `runserver` prints that it is running at `http://127.0.0.1:8000/` and then does not return to a prompt. That is normal: the window is now busy serving the backend.

- The username can't be a reserved word (`admin`, `root`, `staff` and others are blocked). Use
  something like `nafis_admin`.
- Django Admin logs in with the **email**, not the username.

#### Step 2: Look at the backend in the browser

**Where:** Browser, while `runserver` is running in window 1.

**What this does:** Opens the health page and Django Admin to confirm the server answers and that your admin account works.

| URL | Expect |
|---|---|
| http://localhost:8000/api/health/ | `{"status":"ok"}` |
| http://localhost:8000/admin/ | Login page. Sign in with your email and password. If it 404s, `ADMIN_URL_PATH` in `backend/.env` isn't `admin/`; use that path. |
| http://localhost:8000/admin/accounts/user/ | Your user, plus an "Add user" button |
| http://localhost:8000/admin/core/platformsettings/ | One row with 11 values; no add or delete |

Role check in the admin: add a second user, open it and set **Role = Moderator**, then save.

- "Is staff" (read-only) becomes ticked and Groups shows "Moderators".
- Senior moderator shows both groups; setting the role back to User clears them.
- Your superuser stays staff whatever its role.

#### Step 3: Check the deep health endpoint

**Where:** Terminal window 2 (commands), a new terminal in the repo root. Window 1 must still be running `runserver`.

**What this does:** The deep health check needs a secret request header, so it can't be done in the browser. The first request has no header and must be refused. The second sends the secret (read from your own `backend/.env` without printing it) and must succeed, which proves Postgres and Redis both answer.

```bash
cd backend                            # from the repo root
curl -i http://localhost:8000/api/health/deep/
secret=$(grep -m1 '^INTERNAL_CRON_SECRET=' .env | cut -d= -f2- | tr -d '\r')    # sets $secret for the next line; nothing is printed
curl -i -H "X-RZ-Cron-Secret: $secret" http://localhost:8000/api/health/deep/
```

**You should see:**

- First request: **403** with `permission_denied` (no secret, so refused, as intended).
- Second request: **200** with `{"status":"ok","database":"ok","cache":"ok"}`. This proves Postgres
  and Redis.

**If it differs:** a `Connection refused` means window 1 is not running `runserver`. An empty `$secret` (second request also 403) means `INTERNAL_CRON_SECRET` is missing from `backend/.env`.

#### Step 4: Check that the database refuses bad data

**Where:** Same terminal as step 3 (window 2), in `backend/` with the venv active (run `source .venv/bin/activate` if the prompt has no `(.venv)`).

**What this does:** Reads the platform settings, then tries to write a credibility score of 150 (the allowed range is 0 to 100). The database must refuse it.

```bash
python manage.py shell -c "from apps.core.services import get_platform_settings as g; s=g(); print(s.report_threshold, s.emergency_min_reputation)"
python manage.py shell -c "from apps.accounts.models import User; u=User.objects.first(); print(u.reputation_score); User.objects.filter(pk=u.pk).update(reputation_score=150)"
```

**You should see:**

- First command prints `5 40`.
- Second prints `50`, then a long traceback ending in
  `IntegrityError ... violates check constraint "accounts_user_reputation_score_range"`. That error
  is the expected result: the database refused a score above 100 and the user keeps 50. The
  traceback shows your email and the start of your password hash, so don't share it.

#### Step 5: Run the automated checks

**Where:** Same terminal as step 3 (window 2), in `backend/` with the venv active. Needs the containers from step 1.

**What this does:** Runs the backend test suite, the code-style checks and the Django consistency checks. The test run takes a little while and prints dots as it goes.

```bash
python -m pytest                                    # 200 passed
python -m pytest --cov=apps --cov=rumor_zero        # same tests plus coverage (about 93%)
ruff check . ; ruff format --check .                # All checks passed! / files already formatted
python manage.py makemigrations --check --dry-run   # No changes detected
python manage.py check                              # System check identified no issues
```

**You should see:** the result in each comment above. The first two commands end with a summary line; the others print one short sentence.

#### Step 6: Stop and clean up

**Where:** Window 1 for the server, then any terminal in the repo root.

- Stop the server: `Ctrl+C` in its window.
- Stop the containers and keep the data: `docker compose down` (repo root).
- Wipe the local database (destructive): `docker compose down -v` (repo root).

---

### Part 0B: Frontend foundation & design system

Everything here runs in `frontend/`. No backend, Docker container or
secret is needed: these pages make no API calls. (Next loads your `frontend/.env.local`
by itself; you never open or print it.)

| Window | Used for | Stays busy? |
|---|---|---|
| Terminal window 1 (server) | Steps 4 and 7: `npm run dev`, later `npm start` | Yes, leave it running while you use the browser |
| Terminal window 2 (commands) | Steps 1 to 3, the second half of step 7, and step 8 | No |
| Browser | Steps 5 to 7 | - |

Steps 1 to 3 need only one terminal. Open a second one when step 4 starts the server.

#### Step 1: Install and check the tools

**Where:** Terminal (the one you will use for the checks), in the repo root first.

**What this does:** Confirms Node is the right version and installs the frontend packages.

```bash
cd frontend                           # from the repo root
node -v                               # v24.x.x (the project pins Node 24)
npm install                           # "up to date, audited 449 packages" and "found 0 vulnerabilities"
```

**You should see:** a Node version starting with `v24`, then npm's summary lines as in the comments. `npm install` can be quiet for a few seconds.

- npm also prints `npm warn allow-scripts ... unrs-resolver`. It is harmless.
- On a fresh clone the first install can stop with `ERR_SSL_CIPHER_OPERATION_FAILED` on this
  network. Run `npm cache verify`, then `npm install` again. Don't turn TLS checks off.

#### Step 2: Run the automated checks

**Where:** Same terminal as step 1, same folder. Nothing else needs to be running.

**What this does:** Runs the linter, the design-token guard, the type checker, the formatter check and the unit tests.

```bash
npm run lint                          # only the npm header, no findings
npm run lint:tokens                   # lint:tokens OK (no default palette, raw hex, stray radius, shadow or type size)
npm run typecheck                     # only the npm header, no type errors
npm run format:check                  # All matched files use Prettier code style!
npm test                              # Test Files  32 passed (32) / Tests  251 passed (251)
```

**You should see:** the result in each comment. "Only the npm header" means a couple of lines starting with `>` and nothing after them: no news is good news.

#### Step 3: Try to break the design-token guard

**Where:** Same terminal as step 1, in `frontend/`.

**What this does:** `lint:tokens` rejects anything outside the Stitch design system. You add a file that breaks two rules, watch the guard complain, then delete the file and watch it pass again.

```bash
printf '%s\n' 'export const x = "bg-blue-500 rounded-md";' > src/tmp-token-check.tsx   # creates the bad file
npm run lint:tokens                   # must fail
rm src/tmp-token-check.tsx            # removes the bad file
npm run lint:tokens                   # must pass again
```

**You should see:**

- First run exits with code 1 and prints
  `src/tmp-token-check.tsx:1  Tailwind default palette colour: bg-blue-500`,
  `src/tmp-token-check.tsx:1  radius other than rounded-lg / rounded-full: rounded-md` and
  `lint:tokens found 2 problem(s).`
- Second run (file removed) is back to `lint:tokens OK ...`. Nothing is left behind.

#### Step 4: Start the dev server

**Where:** Terminal window 1 (server), in `frontend/`.

**What this does:** Starts the Next.js development server so you can open the pages in the browser.

```bash
npm run dev                           # leave this window running
```

**You should see:**

- `▲ Next.js 16.3.8 (Turbopack)`, `- Local:         http://localhost:3000`,
  `- Environments: .env.local` and `✓ Ready in` a few hundred milliseconds. The window then stays busy. That is normal.
- It must not create `frontend/AGENTS.md` or `frontend/CLAUDE.md` (see step 8).

#### Step 5: Look at the pages and try the controls

**Where:** Browser, while `npm run dev` is running in window 1.

**What this does:** Checks the home page, the UI gallery and the 404 page, then tries each control in the gallery.

| URL | Expect |
|---|---|
| http://localhost:3000/ | Heading "Frontend foundation" and one sentence ("The design system is in place. ..."). Tab title "Rumor Zero". |
| http://localhost:3000/dev/ui | The gallery. Tab title and heading "UI gallery", a row of section links, and 13 sections from Icon down to "Stitch b2 and d1: modals". |
| http://localhost:3000/nope | Next's standard 404 page |

On `/dev/ui` (a 1280 px wide window shows it as designed), check the look first:

- Page background is a pale lavender; headings are a serif (Newsreader), body text is Inter, small
  caps labels are monospace.
- Icons are glyphs. If you read words like `check_circle` instead, the icon font didn't load.

Then try each control:

| Do this | Expect |
|---|---|
| Tabs: click **Recent**, or focus a tab and press the right arrow | Recent is selected, the blue underline moves under it, the text below reads "Panel for recent" |
| Post type control: click **Fact** | Nothing is chosen at first; after the click Fact is the raised white pill and Opinion is not |
| Password field (in the "TextField, PasswordField, Textarea" section): click the eye icon | The dots turn into the text `hunter2hunter2`; the button now says "Hide password" |
| "Try a password" box: type `abc`, then `abcdefg1`, then `abcdefg1X`, then `correct horse battery 9` | The label under the bar reads **Weak** (red), **Fair** (amber), **Good** (teal), **Strong** (teal), filling 1, 2, 3 and 4 segments |
| Toggle row: click the first (off) toggle | It switches on. The third toggle is violet (emergency), the last is greyed out and does nothing |
| Radio list ("Why are you reporting this post?"): click **Spam or fake accounts** | Its card gets the blue border and the first card loses it |
| Avatar section, "a photo that fails to load" | Two dark circles with the initials **GH** and **RU**. No broken-image icon. |
| Red alert "Could not log in": click the **×** | The alert disappears |
| **Show a live toast** | A dark toast "Saved just now" appears bottom-centre and is gone after about 4 seconds |

The post cards under "Stitch b1: PostCard" (eight of them, in this order):

- Verified 94%: teal stripe, `VERIFIED 94%`.
- FALSE 88%: red stripe, `FALSE 88%`. The claim is not struck through.
- Emergency: the only card with a **violet** stripe, with `CHECKING FACTS…` and `EMERGENCY` chips.
- Under review: amber stripe, `UNDER REVIEW` and `APPEAL PENDING`.
- Opinion: grey stripe, italic serif text, an `OPINION` chip and no status badge.
- Moderator-verified: `VERIFIED · REVIEWED`, no percentage.
- Moderator-FALSE, emergency over: red again, `FALSE · REVIEWED`, no `EMERGENCY` chip.
- Removed: a small box "Removed by a moderator", with no text, stripe or chips.

The word "debunked" appears nowhere. For a side-by-side look, open
`design/stitch/stitch_website_sitemap_grid_builder/b1_home_feed/code.html`
next to the gallery.
Stitch also shows an affiliation line, an evidence drawer and an action bar (later parts) and
strikes FALSE claims through (deliberately not copied).

#### Step 6: Try the two modals

**Where:** Browser, still on `/dev/ui`. Scroll to "Stitch b2 and d1: modals".

**What this does:** Opens the post composer and the report dialog and checks their behaviour (focus, Esc, counters).

| Do this | Expect |
|---|---|
| Click **Open the composer (b2)** | A 620 px dialog, centred, over a dimmed and slightly blurred page. Header "New post". The cursor is already in the large serif text box, with `0 / 500 characters` under it. Fact is selected, the violet Emergency toggle is on with a violet "Misuse has consequences." callout, and there is a Source field. Footer: "7 of 10 fact posts left today", Cancel, **Post fact, will be checked**. |
| Type `Solar capacity grew 30% last year.` | The counter reads `34 / 500 characters` |
| Click **Opinion** | The button becomes **Post opinion** and the Emergency toggle and Source field disappear |
| Press Tab over and over | Focus cycles through the dialog's own controls and never reaches the page behind it. After the last button it leaves the page for the browser's own controls, then comes back to Close. |
| Press Esc | The dialog closes and focus is back on **Open the composer (b2)** |
| Click **Open the report modal (d1)** | Header "Report this post" with a small "REPORT" line above it, a quoted claim with a dark left edge, five radio cards (the first selected, blue border), a blue "What happens next" note, and a white footer with Cancel and **Submit report**. Focus starts on the × button. |
| Press Esc | The dialog closes and focus returns to **Open the report modal (d1)** |

#### Step 7: Check that the production build hides the gallery

**Where:** Terminal window 1 (server). First stop the dev server with `Ctrl+C`, then run the commands in `frontend/`. The checks afterwards go in window 2.

**What this does:** Builds the production version and starts it. In production the `/dev/ui` gallery must answer 404 while the home page still works.

```bash
npm run build                         # takes a little while; prints a route list at the end
npm start                             # leave this window running
```

**You should see:**

- Build: `✓ Compiled successfully in` a few seconds, `Generating static pages ... (4/4)`, and a
  route list with `/`, `/_not-found` and `/dev/ui`, all marked `○ (Static)`. The route is listed
  but answers 404 at runtime, as the next commands show.
- Start: `▲ Next.js 16.3.8`, `- Local:         http://localhost:3000`, `✓ Ready in` about 100 ms. The window stays busy.

Now in **Terminal window 2 (commands)**, a second terminal:

```bash
curl -s -o /dev/null -w '/        %{http_code}\n' http://localhost:3000/
curl -s -o /dev/null -w '/dev/ui  %{http_code}\n' http://localhost:3000/dev/ui
```

**You should see:**

- `/        200` and `/dev/ui  404`.
- Browser: http://localhost:3000/dev/ui shows "This page could not be found", while
  http://localhost:3000/ still shows "Frontend foundation".

#### Step 8: Repository checks

**Where:** Terminal window 2 (commands), any folder inside the repo.

**What this does:** Confirms the example env file is tracked by git and that `create-next-app` did not leave agent instruction files in `frontend/`.

```bash
cd "$(git rev-parse --show-toplevel)"              # the repo root, from any folder inside it
git check-ignore frontend/.env.example             # prints nothing: the example env file is tracked
for f in frontend/AGENTS.md frontend/CLAUDE.md; do [ -e "$f" ] && echo True || echo False; done   # False, then False
```

**You should see:** nothing from `git check-ignore`, then `False` and `False`.

#### Step 9: Stop and clean up

**Where:** Terminal window 1 for the server.

- Stop the server: `Ctrl+C` in its window.
- Nothing else is running for this part: no containers, no backend.
- Optional: `rm -rf frontend/.next`
  deletes the build output. It is recreated by the next `npm run dev` or `npm run build`.

---

### Part 0D: Brand assets & Logo component

Everything here runs in `frontend/` unless a step says otherwise. No backend, Docker container or
secret is needed. (Next loads your `frontend/.env.local` by itself; you never open or print it.)
The master logo is `design/logo.svg`. It is read-only: nothing below changes it.

| Window | Used for | Stays busy? |
|---|---|---|
| Terminal window 1 (server) | Step 8: `npm run dev` | Yes, leave it running through step 9 |
| Terminal window 2 (commands) | Steps 1 to 7, the fetch part of step 8, steps 10 to 11 | No |
| Browser | Step 9 | - |

Steps 1 to 7 need just one terminal, in `frontend/`.

#### Step 1: Check the tools

**Where:** Terminal window 2 (commands), in the repo root first.

**What this does:** Installs the frontend packages and confirms `sharp` (the image library that draws the PNGs) is present.

```bash
cd frontend                           # from the repo root of your clone
npm install                           # "up to date, audited 449 packages" and "found 0 vulnerabilities"
npm ls sharp --depth=0                # `-- sharp@0.35.5
```

**You should see:** the summary lines in the comments.

- npm also prints `npm warn allow-scripts ... unrs-resolver`. It is harmless.
- `sharp` is the image library that draws the PNGs. Only the brand script uses it.

#### Step 2: Build every logo asset

**Where:** Same terminal as step 1, in `frontend/`.

**What this does:** Reads the master logo and generates all icons, social images and the admin logo from it. It can pause for a moment while images are drawn.

```bash
npm run brand:build
```

**You should see:**

- `brand:build read design/logo.svg and wrote 16 files:` and a list: `logo.svg`, `mark.svg`,
  `icon-192.png`, `icon-512.png`, `icon-maskable-512.png`, `email-logo.png` and
  `google-oauth-logo.png` under `frontend/public/brand/`; `icon.svg`, `favicon.ico`, `apple-icon.png`,
  `opengraph-image.png`, `twitter-image.png` and the two `.alt.txt` files under `frontend/src/app/`;
  `frontend/src/lib/brand-assets.json`; and `backend/apps/core/static/core/brand/logo-admin.png`.
- Then the contrast table, which must read exactly like the one in `docs/ARCHITECTURE.md` section 14:

```text
Contrast on                       grey letters  cyan "0"
surface-container-lowest #ffffff  3.45 : 1      2.42 : 1
surface #faf8ff                   3.28 : 1      2.30 : 1
inverse-surface #283044           3.81 : 1      5.43 : 1
on-surface #131b2e                4.97 : 1      7.09 : 1
```

- The last line is `The contrast table matches ARCHITECTURE 14.` If you ever change the logo's colours and see
  `DIFFERS from ARCHITECTURE 14` instead, update that section.

#### Step 3: Check that nothing under `design/` changes, and a second run changes nothing

**Where:** Same terminal as step 1, in `frontend/`.

**What this does:** Takes a checksum of every generated file, builds again, and compares. Identical checksums mean the build is repeatable. It also confirms git sees no change under `design/`. The variables `paths`, `h1` and `h2` are set inside this block, so run the whole block in one go.

```bash
paths=(public/brand/* src/app/favicon.ico src/app/icon.svg src/app/apple-icon.png src/app/opengraph-image.png src/app/twitter-image.png src/lib/brand-assets.json ../design/logo.svg ../backend/apps/core/static/core/brand/logo-admin.png)
h1=$(sha256sum "${paths[@]}")
printf '%s\n' "$h1" | wc -l           # 15
npm run brand:build > /dev/null       # runs the build again, output hidden
h2=$(sha256sum "${paths[@]}")
printf '%s\n' "$h2" | grep -vxFf <(printf '%s\n' "$h1") | wc -l    # 0
cd ..
git status --short design             # prints nothing
cd frontend
```

**You should see:**

- `15` files hashed, and `0` differences: building again gives the same bytes, including
  `design/logo.svg`.
- `git status --short design` prints nothing: the master was only read.

#### Step 4: Check that the build refuses an unsafe logo

**Where:** Same terminal as step 1, in `frontend/`.

**What this does:** The script takes `--master <file>` so you can try another SVG. Each bad file below is a copy of the
real logo with one thing added, kept in your temp folder (`/tmp/rz-bad-logo.svg`). The build must refuse all three. The variable `bad` is set in the first block and reused in the next two, so use the same terminal throughout.

```bash
bad=/tmp/rz-bad-logo.svg
sed -E 's|<defs>|<script>alert(1)</script><text>x</text><defs>|g' ../design/logo.svg > "$bad"
npm run brand:build -- --master "$bad"
echo $?
```

**You should see:** `brand:build failed: rz-bad-logo.svg failed the safety check, so nothing was built:` with
`- <script> element (line 3)` and `- <text> element (line 3)`. The exit code (`echo $?`) is `1`.

```bash
sed -E 's|<defs>|<use href="https://evil.example/x.svg#a"/><defs>|g' ../design/logo.svg > "$bad"
npm run brand:build -- --master "$bad"
```

**You should see:** it fails with `- external href="https://evil.example/x.svg#a" on <use> (line 3)`.

```bash
sed -E 's|viewBox="0 0 1000 1000"||g' ../design/logo.svg > "$bad"
npm run brand:build -- --master "$bad"
rm "$bad"                             # deletes the temporary bad file
```

**You should see:** it fails with `- the <svg> root has no viewBox`.

- In all three, no asset is written and `design/logo.svg` is untouched. Running plain
  `npm run brand:build` again afterwards still works.

**If it differs:** if `$bad` is empty ("No such file" or the script reads the wrong file), you opened a new terminal after the first block. Set `bad=/tmp/rz-bad-logo.svg` again.

#### Step 5: Run the automated checks

**Where:** Same terminal as step 1, in `frontend/`. Nothing else needs to be running.

**What this does:** Runs lint, the token guard, type check, format check and the unit tests.

```bash
npm run lint                          # only the npm header, no findings
npm run lint:tokens                   # lint:tokens OK (no default palette, raw hex, stray radius, shadow or type size)
npm run typecheck                     # only the npm header, no type errors
npm run format:check                  # All matched files use Prettier code style!
npm test                              # Test Files  40 passed (40) / Tests  329 passed (329)
```

**You should see:** the result in each comment.

- The new tests are the SVG safety check, the ICO writer, the contrast table (compared with
  `docs/ARCHITECTURE.md`), the PNG sizes, a full build into a scratch folder, `Logo`, `manifest.ts` and
  the brand guard.

#### Step 6: Try to break the brand guard

**Where:** Same terminal as step 1, in `frontend/`.

**What this does:** Only `Logo.tsx`, `brand-assets.json` and `manifest.ts` may know where the logo files are, and nobody
may re-create the old text wordmark. You add two files that break the rules, run the guard test (it must fail), delete the files and run it again (it must pass).

```bash
printf '%s\n' 'export const X = () => <span className="font-headline-sm">Rumor Zero</span>;' > src/tmp-wordmark.tsx
printf '%s\n' 'export const src = "/brand/logo.svg";' > src/tmp-logo-ref.ts
npx vitest run src/lib/brand-guard.test.ts     # must show failures
rm src/tmp-wordmark.tsx src/tmp-logo-ref.ts    # removes both bad files
npx vitest run src/lib/brand-guard.test.ts     # must pass
```

**You should see:**

- First run: `Tests  3 failed | 3 passed (6)`. The failures name `tmp-logo-ref.ts` (twice: it refers to
  `/brand/` and names a logo image) and `tmp-wordmark.tsx` (it re-creates the text wordmark).
- Second run (files removed): `Tests  6 passed (6)`. Nothing is left behind.

#### Step 7: Check that the production build carries the icon tags

**Where:** Same terminal as step 1, in `frontend/`.

**What this does:** Builds the site and searches the generated home page for the icon, manifest and social-share tags.

```bash
npm run build                         # takes a little while
grep -oE '<link rel="(icon|apple-touch-icon|manifest)"[^>]*>' .next/server/app/index.html
grep -oE '<meta (property|name)="(og:image|twitter:image|twitter:card|og:site_name)"[^>]*>' .next/server/app/index.html
```

**You should see:**

- Build: `✓ Compiled successfully`, `Generating static pages ... (10/10)`, and a route list that now also
  has `/apple-icon.png`, `/icon.svg`, `/manifest.webmanifest`, `/opengraph-image.png` and
  `/twitter-image.png`, all `○ (Static)`.
- The links:

```text
<link rel="manifest" href="/manifest.webmanifest"/>
<link rel="icon" href="/favicon.ico?favicon.<hash>.ico" sizes="48x48" type="image/x-icon"/>
<link rel="icon" href="/icon.svg?icon.<hash>.svg" sizes="any" type="image/svg+xml"/>
<link rel="apple-touch-icon" href="/apple-icon.png?apple-icon.<hash>.png" sizes="180x180" type="image/png"/>
```

- The meta tags: `og:site_name` is `Rumor Zero`, `twitter:card` is `summary_large_image`, and `og:image` and
  `twitter:image` are full URLs built from `NEXT_PUBLIC_SITE_URL` (`http://localhost:3000/opengraph-image.png?...`
  with the value from your `.env.local`).
- `<hash>` differs from run to run.

#### Step 8: Start the dev server and fetch every asset

**Where:** `npm run dev` in Terminal window 1 (server); the `curl` commands in Terminal window 2 (commands).

**What this does:** Starts the dev server, then requests every generated file to confirm each one is served with the right content type.

```bash
npm run dev                           # leave this window running
```

**You should see:** the Next.js start-up lines, then a busy window. That is normal.

Second window (window 2):

```bash
cd frontend                           # from the repo root of your clone
for u in /favicon.ico /icon.svg /apple-icon.png /manifest.webmanifest /opengraph-image.png /twitter-image.png /brand/logo.svg /brand/mark.svg /brand/icon-192.png /brand/icon-512.png /brand/icon-maskable-512.png /brand/email-logo.png /brand/google-oauth-logo.png; do
  curl -s -o /dev/null -w "$u  %{http_code}  %{content_type}\n" "http://localhost:3000$u"
done
curl -s http://localhost:3000/manifest.webmanifest; echo
curl -s -o /dev/null -w "/brand/nope.png  %{http_code}\n" http://localhost:3000/brand/nope.png
```

**You should see:**

- All 13 lines say `200`. Content types: `image/x-icon` for the .ico, `image/svg+xml` for the three SVGs,
  `application/manifest+json` for the manifest, and `image/png` for the rest.
- The manifest is one line of JSON: name and short name `Rumor Zero`, `"start_url":"/"`,
  `"display":"standalone"`, `theme_color` and `background_color` both `#283044`, and three icons:
  `192x192` (`any`), `512x512` (`any`) and `512x512` (`maskable`).
- The last line says `404`: only generated files exist.

#### Step 9: Look at the logo and icons in the browser

**Where:** Browser, while `npm run dev` is running in window 1.

**What this does:** Checks by eye that the logo renders correctly at each size and on each background, and that every generated image looks right.

| URL | Expect |
|---|---|
| http://localhost:3000/ | Heading "Frontend foundation". The tab shows a dark rounded square with a cyan "0" as its icon (a hard refresh, Ctrl+F5, helps if the old icon is cached). |
| http://localhost:3000/dev/ui#logo | The "Logo" section: three panels, "ON SURFACE" (pale lavender), "ON SURFACE-CONTAINER-LOWEST" (white) and "ON INVERSE-SURFACE" (dark navy). |

In each of the three panels:

- Row one: the wordmark "Rum0r" at **sm, md and lg**, three clearly different sizes (24, 36 and 48 px tall). The letters
  are grey, the "0" and the underline are cyan.
- Row two: the cyan "0" mark alone at sm, md and lg.
- Last line: a small "0" followed by "Rumor Zero (decorative mark: the name is written next to it)".
- On the dark panel the grey letters look dimmer but readable; the cyan stands out.
- The labels under the logos are plain text, not part of the images.

Check the sizes and names in the page itself: press F12, open the **Console** and paste

```js
[...document.querySelectorAll('#logo img')].map(i => [i.alt, i.width, i.height].join(' | ')).slice(0, 7)
```

- Expect `Rumor Zero | 79 | 24`, `Rumor Zero | 119 | 36`, `Rumor Zero | 158 | 48`, `Rumor Zero | 24 | 24`,
  `Rumor Zero | 36 | 36`, `Rumor Zero | 48 | 48` and ` | 24 | 24` (the decorative one has an empty alt).

Now open each generated image in the browser and check what you see:

| URL | Expect |
|---|---|
| http://localhost:3000/brand/logo.svg | The full wordmark on a transparent background, tightly cropped |
| http://localhost:3000/brand/mark.svg | The cyan "0" alone on a transparent background |
| http://localhost:3000/brand/icon-512.png | A dark navy rounded square with a large cyan "0" in the middle; the four corners are transparent |
| http://localhost:3000/brand/icon-maskable-512.png | A full-bleed navy square, the "0" smaller and well inside the middle, no rounded corners |
| http://localhost:3000/apple-icon.png | A full-bleed navy square with the "0" (iOS rounds it itself) |
| http://localhost:3000/opengraph-image.png | A wide navy picture with the whole wordmark centred, grey letters, cyan "0" and underline |
| http://localhost:3000/brand/email-logo.png | A small navy banner with the wordmark |
| http://localhost:3000/brand/google-oauth-logo.png | A small navy square with the wordmark across the middle |

Last, the manifest as the browser reads it: F12 → **Application** → **Manifest**. It shows the name
"Rumor Zero", theme and background colour `#283044`, and the three icons, including one marked
"maskable".

#### Step 10: Check the exact sizes of the generated files

**Where:** Terminal window 2 (commands), in `frontend/`. Stop the dev server first (`Ctrl+C` in window 1), or just use this new window.

**What this does:** A small Python script reads each PNG's width and height and the icon sizes inside `favicon.ico`, and prints them with the file sizes.

```bash
python3 - <<'EOF'
import os
import struct

pngs = ['src/app/apple-icon.png', 'public/brand/icon-192.png', 'public/brand/icon-512.png', 'public/brand/icon-maskable-512.png', 'src/app/opengraph-image.png', 'src/app/twitter-image.png', 'public/brand/google-oauth-logo.png', 'public/brand/email-logo.png', '../backend/apps/core/static/core/brand/logo-admin.png']
for p in pngs:
    with open(p, 'rb') as f:
        head = f.read(24)
    w, h = struct.unpack('>II', head[16:24])
    print('%-62s %d x %d  %d bytes' % (p, w, h, os.path.getsize(p)))
with open('src/app/favicon.ico', 'rb') as f:
    b = f.read()
print('ico: images=%d; sizes=%s' % (struct.unpack('<H', b[4:6])[0], ','.join(str(x) for x in (b[6], b[22], b[38]))))
EOF
```

**You should see** (recorded output):

```text
src\app\apple-icon.png               180 x 180  2333 bytes
public\brand\icon-192.png            192 x 192  3904 bytes
public\brand\icon-512.png            512 x 512  12022 bytes
public\brand\icon-maskable-512.png   512 x 512  6262 bytes
src\app\opengraph-image.png          1200 x 630  12839 bytes
src\app\twitter-image.png            1200 x 630  12839 bytes
public\brand\google-oauth-logo.png   120 x 120  1605 bytes
public\brand\email-logo.png          320 x 96  3541 bytes
..\backend\apps\core\static\core\brand\logo-admin.png   158 x 64  1879 bytes
ico: images=3; sizes=16,32,48
```

- The sizes are exact; the byte counts can differ a little on another machine.
- On Linux the paths print with `/` instead of `\` (the recorded output above came from Windows); the sizes, byte counts and the `ico:` line are the same.
- The Google logo is far under 1 MB. The apple icon is also opaque (its PNG has no alpha channel);
  the automated tests check that.

#### Step 11: Repository checks

**Where:** Terminal window 2 (commands), in `frontend/`.

**What this does:** Confirms git does not ignore the generated files, marks the binary ones correctly, and that `design/` and `frontend/` have no unexpected changes or files.

```bash
cd ..                                 # the repo root (you are in frontend/)
git check-ignore frontend/src/app/favicon.ico frontend/public/brand/logo.svg backend/apps/core/static/core/brand/logo-admin.png   # prints nothing: none of them is ignored
git check-attr binary -- frontend/src/app/favicon.ico frontend/src/app/apple-icon.png     # both: binary: set
git status --short design             # prints nothing: design/ is untouched
for f in frontend/AGENTS.md frontend/CLAUDE.md; do [ -e "$f" ] && echo True || echo False; done   # False, then False
```

**You should see:** nothing from the first `git` command, two lines saying `binary: set`, nothing from `git status`, then `False` and `False`.

#### Step 12: Stop and clean up

**Where:** Terminal window 1 for the server.

- Stop the server: `Ctrl+C` in its window.
- Nothing else is running for this part: no containers, no backend.
- The generated files are meant to be committed; do not delete them. To change the logo later:
  replace `design/logo.svg` yourself, check that `markSelector` in
  `frontend/scripts/brand/brand.config.json` still picks the "0" (the build fails if it does not
  match exactly one shape), run `npm run brand:build`, and compare the contrast table with
  `docs/ARCHITECTURE.md` section 14.
### Part 0C: App shell, API relay, API client, CI

Needs Part 0A's containers and virtualenv, and your own `backend/.env` and `frontend/.env.local`.
The relay reads `BACKEND_ORIGIN` and `PROXY_SHARED_SECRET` from `frontend/.env.local`. The secret
must be the same as the one in `backend/.env` (ENV_GUIDE §1.2). Nobody can log in yet (Part 1), so
the app pages show the logged-out shell; `/dev/shell` shows the logged-in one with a sample user.

The blocks below assume each new terminal starts in the repo root (the folder that holds
`backend/` and `frontend/`).

**Windows used in this part** (a "window" is one terminal window or tab):

| Window | What it does | Busy? |
|---|---|---|
| Window 1 | Django server (`runserver`), later the stand-in backend (step 5) | Yes: leave it running |
| Window 2 | Frontend dev server (`npm run dev`), or one-off commands when no server is needed | Yes while the dev server runs |
| Window 3 | Extra window for `curl` commands (steps 4 and 5) | No |
| Browser | Steps 6 and 11 | n/a |

A server started with `runserver` or `npm run dev` keeps its window busy until you press `Ctrl+C`.
Open a new window whenever you need to type more commands.

#### Step 1: Install the new tools

**Where:** Any terminal, starting in the repo root.

**What this does:** Installs the frontend packages and downloads the browser (Chromium) that the
end-to-end tests drive, then prints the tool versions so you know they are present.

```bash
cd frontend                       # from the repo root
npm install                       # up to date, audited 735 packages ... found 0 vulnerabilities
npx playwright install chromium   # first time: downloads Chromium for the E2E test; later: prints nothing
npx wrangler --version            # 4.145.0
npx playwright --version          # Version 1.63.0
```

**You should see:**

- `npm install`: `up to date, audited 735 packages ... found 0 vulnerabilities`. It can take a
  while the first time.
- `npx playwright install chromium`: a download progress bar the first time (slow, be patient);
  nothing on later runs.
- `4.145.0` from wrangler (Cloudflare's tool) and `Version 1.63.0` from Playwright.

- `npm install` also prints an `allow-scripts` warning: it did not run the install scripts of
  `workerd`, `esbuild` and `unrs-resolver`. That is expected. Their programs come from separate
  platform packages and work without those scripts.
- Don't run `npm run preview`, `deploy` or `upload` on your own machine. They are for CI and
  Cloudflare, and they would copy your real `.env.local` into the Worker bundle.

**If it differs:** If the E2E test later fails because Chromium reports missing shared libraries,
run `npx playwright install-deps chromium` once (it installs system packages with `sudo`).

#### Step 2: Run the automated frontend checks

**Where:** Same terminal as step 1 (you are in `frontend/`).

**What this does:** Runs the linter, the design-token check, the type checker, the formatter check,
the unit tests and a production build. All of them must pass.

```bash
npm run lint             # no output after the command line
npm run lint:tokens      # lint:tokens OK (no default palette, raw hex, stray radius, shadow or type size)
npm run typecheck        # no output after the command line
npm run format:check     # All matched files use Prettier code style!
npm test                 # Test Files  51 passed (51) / Tests  412 passed (412)
npm run build            # slow (up to a minute or more); ends with a route list
```

**You should see:** The comment on each line is the expected result. "No output" means success for
`lint` and `typecheck`. The build ends with a route list. These lines matter:

```text
┌ ○ /
├ ƒ /api/[...path]
├ ○ /home
├ ○ /login
├ ○ /signup
└ ƒ /u/[username]
```

- `○` means prerendered at build time; `ƒ` means it runs per request. The relay (`/api/[...path]`)
  must be `ƒ`; the landing and auth pages must be `○`.

#### Step 3: Start Django and the frontend

**Where:** Terminal window 1 (server), then terminal window 2.

**What this does:** Starts the database containers and the Django backend (window 1), then the
Next.js dev server (window 2), so the site is reachable at http://localhost:3000.

Window 1:

```bash
docker compose up -d              # from the repo root
cd backend
source .venv/bin/activate
python manage.py runserver        # leave this window running
```

Window 2:

```bash
cd frontend                       # from the repo root
npm run dev                       # ✓ Ready in about 0.5 s, then "✓ Running next.config.ts took" 1 to 5 s
```

**You should see:** In window 1 Django prints its "Starting development server at
http://127.0.0.1:8000/" lines. In window 2 `✓ Ready in about 0.5 s`, then
`✓ Running next.config.ts took` 1 to 5 s. Both windows stay busy; that is correct.

- The extra seconds start `workerd`, Cloudflare's local runtime, for the OpenNext dev setup. Linux
  does not ask about firewall access.

#### Step 4: Check the relay

**Where:** Terminal window 3 (a new window).

**What this does:** Sends requests to the frontend on port 3000 and checks that the relay passes
them to Django on port 8000 and handles errors the right way.

```bash
curl -i http://localhost:3000/api/health/
curl -s -i http://localhost:3000/api/health | grep -iE '^HTTP|^location'
curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:3000/api/a%2Fb/"
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/api/nope/
curl -s -o /dev/null -w "%{http_code} %{redirect_url}\n" http://localhost:3000/home/
```

**You should see:** One result per command, in order:

1. `HTTP/1.1 200 OK` and the body `{"status":"ok"}`. That is Django's answer, fetched through the
   relay on port 3000, with no redirect.
2. `HTTP/1.1 301 Moved Permanently` and `location: /api/health/`. That is Django adding the
   missing slash; the relay keeps the target relative, so it stays on port 3000.
3. `400` (an encoded `/` is refused).
4. `404` (Django has no such path).
5. `308 http://localhost:3000/home`. Page URLs drop a trailing slash; API URLs keep it.

Now stop Django (`Ctrl+C` in window 1) and ask again from window 3:

```bash
curl -s -i http://localhost:3000/api/health/ | grep -iE '^HTTP|^retry-after|^cache-control|code'
```

```text
HTTP/1.1 503 Service Unavailable
cache-control: no-store
retry-after: 30
{"detail":"The server is waking up. Try again in a minute.","code":"backend_waking"}
```

It answers at once, because nothing is listening on port 8000. Start `python manage.py runserver`
again in window 1.

#### Step 5: See what the backend receives (stand-in backend)

**Where:** Windows 1, 2 and 3, as marked below.

**What this does:** Django removes the `X-RZ-*` headers before any code can see them, so this check
uses a small stand-in backend. It reports what arrived as true/false and names only. It uses the
made-up value `echo-check-secret`, never your real secret.

First stop `npm run dev` (`Ctrl+C` in window 2): Next runs only one dev server per folder. Then
stop `runserver` in window 1 too; it isn't needed here.

Window 1, the stand-in backend (it keeps the window busy):

```bash
cat > /tmp/rz-echo.cjs <<'EOF'
// Stand-in backend for the Part 0C relay check. It prints header NAMES and true/false only.
const http = require("node:http");
http.createServer((req, res) => {
  const chunks = [];
  req.on("data", (chunk) => chunks.push(chunk));
  req.on("end", () => {
    const path = new URL(req.url, "http://x").pathname;
    if (path === "/api/cookies/") {
      res.setHeader("set-cookie", ["first=1; Path=/; HttpOnly", "second=2; Path=/api/auth/; SameSite=Lax"]);
      return res.end("{}");
    }
    if (path === "/api/etag/") {
      res.setHeader("etag", '"v1"');
      res.setHeader("cache-control", "public, max-age=31536000, immutable");
      if (req.headers["if-none-match"] === '"v1"') { res.statusCode = 304; return res.end(); }
      return res.end("cached body");
    }
    res.setHeader("content-type", "application/json");
    res.end(JSON.stringify({
      method: req.method,
      secretMatches: req.headers["x-rz-proxy-secret"] === "echo-check-secret",
      clientIp: req.headers["x-rz-client-ip"] ?? null,
      forwardedHost: req.headers["x-forwarded-host"] ?? null,
      contentLength: req.headers["content-length"] ?? null,
      chunked: req.headers["transfer-encoding"] === "chunked",
      bodyBytes: Buffer.concat(chunks).length,
    }));
  });
}).listen(8765, "127.0.0.1", () => console.log("stand-in backend on http://127.0.0.1:8765"));
EOF
node /tmp/rz-echo.cjs             # stand-in backend on http://127.0.0.1:8765
```

The first command writes the script file (no output); the second runs it and prints
`stand-in backend on http://127.0.0.1:8765`.

Window 2, a dev server pointed at it. The `export` values last only for this window;
`.env.local` is not changed:

```bash
cd frontend                       # from the repo root
export BACKEND_ORIGIN="http://127.0.0.1:8765" PROXY_SHARED_SECRET="echo-check-secret"
npx next dev -p 3100
```

Window 3, the checks:

```bash
curl -s -H "X-RZ-Proxy-Secret: spoofed" -H "X-RZ-Client-IP: 6.6.6.6" -H "X-Forwarded-Host: evil.example" http://localhost:3100/api/echo/
curl -s -H "Content-Type: text/plain" --data "hello relay" http://localhost:3100/api/echo/
curl -s -i http://localhost:3100/api/cookies/ | grep -iE '^set-cookie'
curl -s -i http://localhost:3100/api/etag/ | grep -iE '^HTTP|^etag|^cache-control'
curl -s -i -H 'If-None-Match: "v1"' http://localhost:3100/api/etag/ | grep -iE '^HTTP|^etag|^cache-control'
```

**You should see:** One block of output per command, in order (lines 1 to 2 are the first two
commands, then the cookies, then the two etag requests):

```text
{"method":"GET","secretMatches":true,"clientIp":"::1","forwardedHost":null,"contentLength":null,"chunked":false,"bodyBytes":0}
{"method":"POST","secretMatches":true,"clientIp":"::1","forwardedHost":null,"contentLength":"11","chunked":false,"bodyBytes":11}
set-cookie: first=1; Path=/; HttpOnly
set-cookie: second=2; Path=/api/auth/; SameSite=Lax
HTTP/1.1 200 OK
cache-control: public, max-age=31536000, immutable
etag: "v1"
HTTP/1.1 304 Not Modified
cache-control: public, max-age=31536000, immutable
etag: "v1"
```

- **Spoofing:** the faked `X-RZ-Proxy-Secret`, `X-RZ-Client-IP` and `X-Forwarded-Host` never
  arrive. The backend gets the relay's own secret (`secretMatches: true`) and your real address
  (`::1` is this machine; on Linux you may see `127.0.0.1` or `::ffff:127.0.0.1` instead, which is
  also this machine).
- **Body:** it arrives with its length (`contentLength: "11"`), never chunked, which Django needs.
- **Cookies and caching:** both cookies and the `304 Not Modified` come back with `etag` and
  `cache-control` unchanged.
- In bash no escaping is needed for `If-None-Match`: the command uses plain `"v1"` inside single
  quotes.

**Clean up:** Stop both servers (`Ctrl+C` in windows 1 and 2), then close window 2 so its
environment values are gone (or run `unset BACKEND_ORIGIN PROXY_SHARED_SECRET` in that window).
Delete the script:

```bash
rm /tmp/rz-echo.cjs
```

#### Step 6: Look at the layouts in the browser

**Where:** Terminal windows 1 and 2, then the browser.

**What this does:** Starts the normal servers again and lets you check by eye that every page and
screen size looks right.

Start the normal servers again: `python manage.py runserver` in window 1, and in a **new** window 2
`npm run dev` (in `frontend/`).

| URL | Expect |
|---|---|
| http://localhost:3000/ | Placeholder landing page. Top: the logo, "How it works", "Log in" and a blue "Sign up" button. Footer: the small logo, How verification works · Privacy · Terms, and "© 2026 Rumor Zero". Tab title "Rumor Zero". |
| http://localhost:3000/home | The logged-out app shell. Left rail: the logo, Home (blue) and Search; Log in and Sign up at the bottom. Top bar: "Search posts and people" and a Log in link. Tab title "Home · Rumor Zero". |
| http://localhost:3000/home/ | Redirects to `/home` |
| http://localhost:3000/dev/shell | The logged-in shell with the sample user Ada Lovelace: Home, Search, Notifications, Profile, Bookmarks, a blue "New post" button; Moderation and Settings at the bottom; the user card with "AL" and `@ada` |
| http://localhost:3000/dev/shell?user=none | The same page with the logged-out shell |
| http://localhost:3000/login and /signup | A centred white card with the large logo, "Welcome back" or "Create your account" |
| http://localhost:3000/no-such-page | "Page not found" card with the logo and "Go to the home page" |
| http://localhost:3000/dev/ui | The intro text now links to /dev/shell |

On http://localhost:3000/dev/shell:
- Type in the search box and press Enter: the address becomes `/search?q=…` and the page title is
  Search.
- Click `•••` in the user card: a small menu with Profile and Settings opens above it. `Esc` closes
  it.
- Reload, then press `Tab` once: a blue "Skip to content" link appears at the top left.
- The round "N" button at the bottom left is Next's dev indicator; it doesn't exist in production.

Narrower screens: open DevTools (`F12`), switch on the device toolbar (`Ctrl+Shift+M`) and set the
width. The layout switches at 1280 and 768 px.

| Width | Expect on /dev/shell |
|---|---|
| 1280 | The full 256 px rail with labels |
| 1024 | An icon dock: the cyan "0" mark at the top, icons only (hovering shows each name), the "AL" avatar at the bottom |
| 390 | A top bar with the small logo and the "AL" avatar; a bottom bar with Home · Search · New post · Notifications · Profile. Tapping the avatar opens a sheet from the bottom with Bookmarks, Settings and Moderation; `Esc` or a tap outside closes it. No sideways scrolling. |

Compare with Stitch: open
`design/stitch/stitch_website_sitemap_grid_builder/b1_home_feed/code.html` in the repo root
in the browser (it needs internet for its Tailwind script), next to /dev/shell, both at 1280.
- The rail width, item positions, blue Home item, top bar height and search box line up.
- Expected differences: the logo image instead of the "Rumor Zero" text; Bookmarks added; "New
  post" instead of "Submit Claim"; Moderation instead of "Audit Queue"; no "Verification Ledger"
  pill; and sample cards instead of Stitch's feed.

#### Step 7: Run the E2E smoke test

**Where:** A terminal in `frontend/` (any free window, for example window 3).

**What this does:** Playwright opens a real Chromium browser and clicks through the main pages
automatically. It needs the containers from step 3. Django and the dev server may be running or
not: Playwright starts what is missing and reuses what is already running. A reused dev server
keeps its own `BACKEND_ORIGIN`.

```bash
cd frontend                       # from the repo root
npm run test:e2e                  # takes about 10 s once started
```

**You should see:** A list of 8 passing tests and `8 passed`:

```text
Running 8 tests using 6 workers

  ok 1 [chromium] › e2e\smoke.spec.ts:8:5 › the relay forwards /api/health/ to Django (120ms)
  ok 5 [chromium] › e2e\smoke.spec.ts:14:5 › the landing page shows the logo and the footer (1.4s)
  ok 7 [chromium] › e2e\smoke.spec.ts:73:5 › the auth card shows the large logo (1.7s)
  ok 2 [chromium] › e2e\smoke.spec.ts:25:5 › page URLs drop a trailing slash (2.2s)
  ok 3 [chromium] › e2e\smoke.spec.ts:31:5 › the app shell has the full rail at 1280px (2.2s)
  ok 6 [chromium] › e2e\smoke.spec.ts:60:5 › the app shell has a top bar and bottom bar at 390px (2.0s)
  ok 8 [chromium] › e2e\smoke.spec.ts:82:5 › an unknown URL shows the 404 page with the logo (745ms)
  ok 4 [chromium] › e2e\smoke.spec.ts:44:5 › the app shell has the icon dock at 1024px (2.3s)

  8 passed (9.3s)
```

- The order and timings vary (six tests run in parallel). `[WebServer]` lines are Django's request
  log.
- On Linux the paths read `e2e/smoke.spec.ts`, the passing mark is `✓` instead of `ok`, and the
  number of workers depends on your CPU.

#### Step 8: Run the same test the way CI runs it

**Where:** A terminal in `frontend/`.

**What this does:** CI tests the production build and starts its own servers. First stop
`npm run dev` and `runserver` (`Ctrl+C`); in this mode Playwright won't reuse them.

```bash
cd frontend                       # from the repo root
npm run build                     # slow, no need to watch it
export CI=1
npm run test:e2e         # 8 passed, this time against `next start`
unset CI
```

**You should see:** `8 passed`. `export CI=1` only lasts for this window; `unset CI` removes it
again.

#### Step 9: Check the backend is unchanged and still passes

**Where:** Any terminal; this one needs the virtualenv.

**What this does:** Part 0C touched only the frontend, so the backend tests and lint must still
pass exactly as before.

```bash
cd backend                                          # from the repo root
source .venv/bin/activate
python -m pytest                                    # 200 passed
ruff check . ; ruff format --check .                # All checks passed! / 43 files already formatted
python manage.py makemigrations --check --dry-run   # No changes detected
```

**You should see:** `200 passed`, then `All checks passed!` and `43 files already formatted`, then
`No changes detected` (no new database changes are pending).

#### Step 10: Repository checks

**Where:** Any terminal, in the repo root.

**What this does:** Confirms that `design/` was not modified, that no unwanted agent files appeared
in `frontend/`, and that git ignores the test reports but not the config files.

```bash
# run from the repo root
git status --short design                          # prints nothing: design/ is untouched
for f in frontend/AGENTS.md frontend/CLAUDE.md; do [ -e "$f" ] && echo True || echo False; done   # False, then False
git check-ignore frontend/playwright-report frontend/test-results   # prints both: test reports are never committed
git check-ignore .github/workflows/ci.yml frontend/wrangler.jsonc frontend/playwright.config.ts   # prints nothing: all three are committed
```

**You should see:** Nothing for the first command; `False` and `False`; the two report paths; then
nothing for the last command.

#### Step 11: CI on GitHub (after you push)

**Where:** Browser.

**What this does:** This is the one check the agent could not run, because only you push.

| URL | Expect |
|---|---|
| Your repository's **Actions** tab on github.com | A "CI" run for your push with three green jobs: "Backend (ruff, migrations, pytest)", "Frontend (lint, types, tests, OpenNext build)" and "E2E (Playwright, Chromium)" |

- The frontend job's last step, "OpenNext build", proves the Cloudflare build works on Linux.
- If the E2E job fails, its run page has a "playwright-report" artifact (kept 7 days) that shows
  why.
- Seen on 2026-10-01: the first run failed at "OpenNext build" (`Cannot find package 'esbuild'`).
  The run on `60cfffc` ("Fix: add missing esbuild dependency") had all three jobs green.
- Optional, only if you install the GitHub CLI (`gh`; on Linux it has to be installed too):
  `gh run list --workflow ci.yml --limit 1` shows `completed` and `success`.

#### Step 12: Stop and clean up

**Where:** Every terminal window you still have open.

**What this does:** Shuts everything down.

- Stop the servers: `Ctrl+C` in each window.
- If `npm run dev` later says "Another next dev server is already running" with a PID, the old
  server is still alive. End it with `kill <that PID>` (`pgrep -af 'next|workerd'` lists
  leftover dev servers, and `ss -ltnp | grep -E ':(3000|8000)\b'` shows what holds the ports).
- Stop the containers and keep the data: `docker compose down` (repo root).
- `frontend/playwright-report` and `frontend/test-results` are git-ignored; delete them whenever
  you like.

---

### Part 1: Auth core (sign up, log in, tokens, log out)

Needs Part 0A's containers and virtualenv, Part 0C's frontend, and your own `backend/.env` and
`frontend/.env.local`. Both keep Cloudflare's Turnstile **test** keys (ENV_GUIDE §1.5). Two things
to know first:

- Sign-up calls Cloudflare even with the test keys (the widget in the browser, siteverify from
  Django), so it needs internet.
- Open the site as **http://localhost:3000**. Every `/api/auth/` request must carry exactly the
  `Origin` in `FRONTEND_ORIGIN` (`http://localhost:3000`); `http://127.0.0.1:3000` gets 403
  `csrf_failed`.

**Windows used in this part:**

| Window | What it does | Busy? |
|---|---|---|
| Window 1 | Django server (`runserver`, venv active, in `backend/`) | Yes: leave it running |
| Window 2 | Commands: `curl` checks in steps 3 to 5 (variables like `$h` and `$access` live here; do not close it between steps 3 and 4) | No |
| Window 3 | Frontend dev server (`npm run dev`, in `frontend/`), needed from step 5 | Yes |
| Browser | Steps 6, 7 and 11 | n/a |

A server started with `runserver` or `npm run dev` keeps its window busy until you press `Ctrl+C`.

#### Step 1: Migrate and check the settings

**Where:** Terminal window 1 (it will become the server window in step 3).

**What this does:** Starts the database, applies the new Part 1 database changes, runs Django's
self-check, and checks your JWT signing key length without showing the key.

```bash
# start in the repo root
docker compose up -d
cd backend
source .venv/bin/activate
python manage.py migrate
python manage.py check                # System check identified no issues (0 silenced).
v=$(grep -m1 '^JWT_SIGNING_KEY=' .env | cut -d= -f2- | tr -d '\r')
printf %s "$v" | wc -c
unset v
python manage.py shell -c "from apps.accounts.models import User; print([(u.is_email_verified, list(u.emailaddress_set.values_list('verified', 'primary'))) for u in User.objects.filter(is_superuser=True)])"
```

**You should see:**

- `migrate`, the first time after Part 1: `Applying account.0001_initial... OK` through
  `Applying account.0009_emailaddress_unique_primary_email... OK`, then
  `Applying accounts.0002_verify_superuser_emails... OK`. Later runs: `No migrations to apply.`
- `check`: `System check identified no issues (0 silenced).`
- The length line prints only a number (`67` here). Under 32, Django refuses to start with
  `JWT_SIGNING_KEY must be at least 32 characters`; make a new key with ENV_GUIDE §1.2. Only the
  length is shown, never the key.
- The last command prints `9 objects imported automatically`, then `[(True, [(True, True)])]`: your
  superuser from 0A now counts as verified and has a verified, primary email address (the backfill
  migration).

#### Step 2: Run the automated backend checks

**Where:** Same terminal as step 1 (`backend/`, venv active).

**What this does:** Runs the whole backend test suite plus lint and the migration check.

```bash
python -m pytest                                    # 440 passed
python -m pytest apps/accounts                      # 327 passed (the auth tests)
ruff check . ; ruff format --check .                # All checks passed! / 66 files already formatted
python manage.py makemigrations --check --dry-run   # No changes detected
python -m pytest apps/accounts/tests/test_permissions.py -v   # 4 passed
```

**You should see:** The count in each comment. The full test run takes a while.

- Four of the auth tests run refreshes and logouts in two threads at once. One of them is a control
  run: allauth's stock token strategy loses a tab's token, ours doesn't.
- Verified-only endpoints arrive with posts in Part 4, so the last command checks the permission on
  a test-only view: unverified → 403 `email_unverified`, verified → 201, anonymous → 401.

#### Step 3: Sign up against Django

**Where:** Terminal window 1 (server), then terminal window 2 (commands).

**What this does:** Creates a real account by calling Django's sign-up endpoint with `curl`,
shows the cookies Django sets (the refresh token is hidden), and reads your profile with the access
token.

Window 1: `python manage.py runserver` (in `backend/`, venv active). Leave it running.

Window 2 (no venv needed; it needs `jq`, which the Linux setup guide installs). **Keep this window
open until the end of step 4**: it sets the variables `id`, `h`, `json`, `out`, `body` and `access`
that step 4 reuses:

```bash
cd backend                            # from the repo root
id=$(date +%H%M%S)
h=(-H 'Origin: http://localhost:3000' -H 'X-Requested-With: rumor-zero')
json=$(jq -nc --arg id "$id" '{email: "part1-\($id)@example.test", username: "part1_\($id)", password: "correct-horse-battery-42", turnstile_token: "XXXX.DUMMY.TOKEN.XXXX"}')
out=$(curl -s -i -c /tmp/rz-jar.txt "${h[@]}" -H "Content-Type: application/json" --data-binary "$json" http://localhost:8000/api/auth/app/v1/auth/signup | tr -d '\r')
printf '%s\n' "$out" | grep -iE '^(HTTP|Set-Cookie|Cache-Control)' | sed -E 's/rz_refresh=[^;]+/rz_refresh=<token>/'
body=$(printf '%s\n' "$out" | sed -n '$p')
access=$(printf '%s' "$body" | jq -r .meta.access_token)
printf '%s' "$body" | jq -r '"user: \(.data.user.username); meta fields: \(.meta | keys_unsorted | join(", ")); access token: \(.meta.access_token | length) characters"'
curl -s -H "Authorization: Bearer $access" http://localhost:8000/api/v1/me/; echo
```

**You should see:** The first four lines are the HTTP status and headers (from the `printf ... grep`
line), the fifth is the summary (from the `jq` line), and the last is your profile (from the final
`curl`):

```text
HTTP/1.1 200 OK
Cache-Control: max-age=0, no-cache, no-store, must-revalidate, private
Set-Cookie:  rz_refresh=<token>; expires=…; HttpOnly; Max-Age=1209600; Path=/api/auth/; SameSite=Lax
Set-Cookie:  rz_session=1; expires=…; Max-Age=1209600; Path=/; SameSite=Lax
user: part1_014515; meta fields: is_authenticated, access_token; access token: 373 characters
{"id":"…","username":"part1_014515","display_name":"","email":"part1-014515@example.test","is_email_verified":false,"role":"user","has_usable_password":true,"google_connected":false,"avatar_url":null}
```

Sanity check that `access` is set: `echo ${#access}` should print a number near `373`. If it prints
`0` or `null`, redo this step (usually Django is not running in window 1, or you are offline).

- The number in the name is the time you ran it. bash keeps the quotes, so the command builds the
  JSON with `jq` and passes it to curl directly (no file).
- `meta` has only `is_authenticated` and `access_token`: no `refresh_token` and no
  `session_token`. The refresh token lives only in the HttpOnly cookie (no `Domain`,
  `Path=/api/auth/`). `Secure` is missing because `AUTH_COOKIE_SECURE=False` locally.
- `rz_session=1` is the readable hint that tells the frontend there is a session to restore.
- The `sed` hides the cookie value. The access token stays in `$access` and is never printed.
- `XXXX.DUMMY.TOKEN.XXXX` is the token Cloudflare's test widget produces. Django checked it with
  siteverify, using the test secret.

Window 1 now shows the verification email:

```text
Subject: [Rumor Zero] Please Confirm Your Email Address
From: Rumor Zero <no-reply@example.com>
To: part1-014515@example.test
...
To confirm this is correct, go to http://localhost:3000/verify-email/<key>
```

- The link points at the frontend (the page itself arrives in Part 2).
- The text still says "Hello from localhost:8000!": allauth's default wording, which Part 2's
  branded templates replace.

Still in window 2, the live username check (it uses `id` from above):

```bash
for u in Ada_Lovelace ADMIN ab "part1_$id"; do curl -s "http://localhost:8000/api/v1/auth/username-available/?u=$u"; echo; done
```

```text
{"username":"ada_lovelace","available":true,"reason":null,"message":"Available"}
{"username":"admin","available":false,"reason":"reserved","message":"This username is reserved."}
{"username":"ab","available":false,"reason":"invalid","message":"Usernames are 3–30 characters: lowercase letters, numbers and underscores only."}
{"username":"part1_014515","available":false,"reason":"taken","message":"That username is taken."}
```

Four lines, one per name: free, reserved, invalid format, taken (your own new account).

- A Linux terminal in UTF-8 (the default) shows the dash in `3–30` correctly.

#### Step 4: Refresh, rotation, the CSRF guard and log out

**Where:** Same terminal as step 3 (window 2).

**What this does:** Shows how the refresh cookie rotates, that the old cookie works for 60 seconds,
that requests without the right headers are refused, and what log out does.

This window must still have `h`, `access`, `id` and the cookie jar `/tmp/rz-jar.txt` from step 3.
Sanity check: `echo "${h[@]}"` prints the two headers and `ls /tmp/rz-jar.txt` finds the file. If
not, redo step 3.

```bash
refresh=http://localhost:8000/api/auth/app/v1/tokens/refresh
get_refresh_cookie() { grep rz_refresh /tmp/rz-jar.txt | cut -f7 | sed -n '$p'; }
first=$(get_refresh_cookie)
curl -s -w '\n' -b /tmp/rz-jar.txt -c /tmp/rz-jar.txt "${h[@]}" -X POST "$refresh" | sed -E 's/"access_token": "[^"]+"/"access_token": "<token>"/'
echo
[ "$first" != "$(get_refresh_cookie)" ] && rotated=True || rotated=False
echo "cookie rotated: $rotated"
curl -s -o /dev/null -w 'old cookie at once: %{http_code}\n' "${h[@]}" -X POST -b "rz_refresh=$first" "$refresh"
sleep 61                              # nothing prints for 61 seconds: this wait is on purpose
curl -s -w ' %{http_code}\n' "${h[@]}" -X POST -b "rz_refresh=$first" "$refresh"
curl -s -o /dev/null -w 'current cookie: %{http_code}\n' -b /tmp/rz-jar.txt -c /tmp/rz-jar.txt "${h[@]}" -X POST "$refresh"
```

**You should see:**

```text
{"status": 200, "data": {"access_token": "<token>"}}

cookie rotated: True
old cookie at once: 200
{"status": 400} 400
current cookie: 200
```

- Line 1: the first refresh succeeded. `cookie rotated: True`: the cookie in the jar changed.
- `old cookie at once: 200`: the old cookie still works right away.
- After the 61 s wait, `{"status": 400} 400`: the old cookie is dead. `current cookie: 200`: the new
  one works.
- Every refresh replaces the cookie. The old one keeps working for 60 seconds, so two tabs
  refreshing together, or a reply lost on a bad connection, never log you out. After that minute it
  is dead (400).

Without the `Origin` or the `X-Requested-With` header:

```bash
curl -s -w ' %{http_code}\n' -b /tmp/rz-jar.txt -H 'X-Requested-With: rumor-zero' -X POST "$refresh"
curl -s -w ' %{http_code}\n' -b /tmp/rz-jar.txt -H 'Origin: http://localhost:3000' -X POST "$refresh"
curl -s -w ' %{http_code}\n' -b /tmp/rz-jar.txt -H 'Origin: http://localhost:3000' -X POST http://localhost:8000/api/auth/logout/
```

- All three print
  `{"status": 403, "errors": [{"code": "csrf_failed", "message": "Reload the page and try again."}]} 403`.
- Login and signup are guarded the same way.

Log out:

```bash
last=$(get_refresh_cookie)
curl -s -i -b /tmp/rz-jar.txt -c /tmp/rz-jar.txt "${h[@]}" -X POST http://localhost:8000/api/auth/logout/ | tr -d '\r' | grep -iE '^(HTTP|Set-Cookie)'
curl -s -w ' %{http_code}\n' "${h[@]}" -X POST -b "rz_refresh=$last" "$refresh"
curl -s -w ' %{http_code}\n' "${h[@]}" -X POST "$refresh"
curl -s -o /dev/null -w 'logout again: %{http_code}\n' "${h[@]}" -X POST http://localhost:8000/api/auth/logout/
curl -s -o /dev/null -w 'access token after logout: %{http_code}\n' -H "Authorization: Bearer $access" http://localhost:8000/api/v1/me/
curl -s -w ' %{http_code}\n' "${h[@]}" -X POST http://localhost:8000/api/auth/app/v1/auth/session
```

```text
HTTP/1.1 204 No Content
Set-Cookie:  rz_refresh=""; expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly; Max-Age=0; Path=/api/auth/; SameSite=Lax
Set-Cookie:  rz_session=""; expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=0; Path=/; SameSite=Lax
{"status": 400} 400
{"status": 401} 401
logout again: 204
access token after logout: 200
{"status": 404, "errors": [{"code": "not_found", "message": "Not found."}]} 404
```

- The first three lines come from the logout call itself (204 and both cookies cleared).
- `400`: the last refresh cookie now fails. `401`: with no cookie at all. `logout again: 204`:
  logging out twice is fine.
- `access token after logout: 200`: the access token keeps working until it expires (at most 15
  minutes after step 3; after that the line says 401). That's by design: access tokens are checked
  by signature and expiry only, and the browser forgets its copy at once.
- Only login, signup, refresh and logout exist under `/api/auth/`. allauth's other endpoints, like
  `auth/session` here, answer 404.

#### Step 5: Failed logins are limited per real client IP, through the relay

**Where:** Terminal window 3 (frontend), then window 2 (commands).

**What this does:** Sends 11 wrong logins through the frontend relay to show that Django limits
them by your real address, and that a different address is not blocked.

Window 3: `npm run dev` (in `frontend/`). It keeps the window busy. Back in window 2 (it uses `h`
from step 3; sanity check: `echo "${h[@]}"` prints the two headers):

```bash
for i in $(seq 1 11); do
  login=$(printf '{"email": "nobody%s@example.test", "password": "wrong-password"}' "$i")
  r=$(curl -s "${h[@]}" -H "Content-Type: application/json" --data-binary "$login" http://localhost:3000/api/auth/app/v1/auth/login)
  printf '%2d  ' "$i"
  printf '%s' "$r" | jq -r '"\(.status)  \(.errors[0].code)"'
done
curl -s --interface 127.0.0.2 "${h[@]}" -H "Content-Type: application/json" --data-binary "$login" http://127.0.0.1:8000/api/auth/app/v1/auth/login; echo
```

**You should see:** Eleven numbered lines, then Django's answer to the last request:

```text
 1  400  email_password_mismatch
 2  400  email_password_mismatch
 3  400  email_password_mismatch
 4  400  email_password_mismatch
 5  400  email_password_mismatch
 6  400  email_password_mismatch
 7  400  email_password_mismatch
 8  400  email_password_mismatch
 9  400  email_password_mismatch
10  400  email_password_mismatch
11  400  too_many_login_attempts
{"status": 400, "errors": [{"message": "The email address and/or password you specified are not correct.", "code": "email_password_mismatch", "param": "password"}]}
```

- The first eleven go through the relay on port 3000. Each uses another email, so only the
  per-address limit (10 failures a minute) is hit (line 11); the per-account limit is 5 failures in
  5 minutes.
- The relay passed your real address to Django with the shared secret; on Linux `localhost` may
  resolve to `127.0.0.1` or `::1`. The last request goes straight to Django from a different
  address, so it isn't blocked (it gets the normal "not correct" answer). The command adds
  `--interface 127.0.0.2` (another loopback address), because plain `127.0.0.1` could be the very
  address the relay reported.
- Within that minute, logging in at http://localhost:3000/login, even with a right password, shows
  the red banner "Too many attempts. Try again in a few minutes."

#### Step 6: Browser: sign up, stay logged in, log out

**Where:** Browser. Window 3's `npm run dev` and window 1's `runserver` must be running.

**What this does:** Walks through the real sign-up screens. Wait a minute after step 5 so the
login limit has cleared.

| Do this | Expect |
|---|---|
| Open http://localhost:3000/signup | The a2 card: the logo, "Create your account", Email address, Username, Password with a bar labelled "Password strength", the Cloudflare widget, a blue "Create account", the Terms/Privacy note and "Already have an account? Log in". No Google button yet (Part 3). |
| Look at the widget | It says "Success!" after a second or two, with a red "For testing only…" line: that is the test key. "Create account" is pale (disabled) until then. |
| Type a username, e.g. `Ada_Lovelace` | After a short pause, a teal "Available: @ada_lovelace" and a check mark in the field. `admin` says "This username is reserved."; `ab` shows the format rule at once. |
| Fill a new email, a username and `correct-horse-battery-42`, then click **Create account** | The button spins briefly, then /home: the shell with your @username in the rail and an amber banner "Verify your email to post, comment and report. Check your inbox for the link." The email appears in window 1. |
| F12 → Application → Cookies → http://localhost:3000 | `rz_refresh` (HttpOnly ✓, SameSite Lax, Path `/api/auth/`) and `rz_session` = `1` (Path `/`, not HttpOnly). Local storage and Session storage are empty. |
| F12 → Console: `document.cookie` | `'rz_session=1'`. Scripts can't see the refresh token. |
| Reload (F5) | Still logged in. The account area at the bottom of the rail shows grey placeholders for a moment while the session is restored. |
| Open http://localhost:3000/home in a second tab | Logged in there too |
| First tab: `•••` in the user card | A menu with Profile, Settings and **Log out** |
| Click **Log out** | You land on /login, both cookies are gone (Application → Cookies), and the second tab switches to the logged-out shell by itself. |
| Open http://localhost:3000/settings | It redirects to `/login?next=%2Fsettings`. Log in with the same email and password: you are back on /settings. |
| Phone width (F12 → device toolbar, 390 px): tap the avatar at the top right | The account sheet ends with Log out |

#### Step 7: Browser: the error states

**Where:** Browser, still on http://localhost:3000; one part needs window 1.

**What this does:** Triggers each sign-up and login error on purpose to see the messages.

| Do this | Expect |
|---|---|
| /signup with the email from step 6 and a new username | Under Email: "A user is already registered with this email address." |
| /signup with the username from step 6 | While typing: "That username is taken." |
| /signup with the password `password123` | After Create account: "This password is too common." under Password. The strength bar says Fair: it is only advice; Django decides. |
| Any failed sign-up | The widget runs again ("Verifying…"), and Create account waits for its new token: each token works once. |
| /login with a wrong password | A red banner "That email and password don't match." with an × that closes it |

A failed bot check needs Cloudflare's always-fail **test** secret on the backend. Stop `runserver`
in window 1 (`Ctrl+C`), then in window 1 (in `backend/`, venv active):

```bash
TURNSTILE_SECRET_KEY="2x0000000000000000000000000000000AA" python manage.py runserver
```

- Sign up with a new email and username: under the widget, "The bot check didn't pass. Try it
  again.", and the widget starts over.
- The `TURNSTILE_SECRET_KEY=…` in front of the command lasts only for that one command, and
  `backend/.env` is not changed. Stop the server (`Ctrl+C`) and start `python manage.py runserver`
  normally again (you can keep the same window).

#### Step 8: Run the automated frontend checks

**Where:** A terminal in `frontend/`. Stop `npm run dev` first (`Ctrl+C` in window 3), then you can
reuse window 3.

**What this does:** The same lint, type, format and unit-test checks as Part 0C, now with the auth
tests included, plus a production build.

```bash
npm run lint             # no output after the command line
npm run lint:tokens      # lint:tokens OK (no default palette, raw hex, stray radius, shadow or type size)
npm run typecheck        # no output after the command line
npm run format:check     # All matched files use Prettier code style!
npm test                 # Test Files  59 passed (59) / Tests  562 passed (562)
npm run build            # slow; ends with the route list below
```

**You should see:** The comment on each line is the expected result. The build's route list still
has these lines:

```text
├ ƒ /api/[...path]
├ ○ /login
├ ○ /signup
```

- The auth pages stay prerendered (`○`); the relay runs per request (`ƒ`).

#### Step 9: The E2E tests, dev mode and CI mode

**Where:** A terminal in `frontend/` (window 3).

**What this does:** Playwright drives a real browser through sign-up, reload and log out.

Stop `runserver` too (`Ctrl+C` in window 1): Playwright then starts its own Django with an
in-memory cache, so step 5's rate limit can't get in the way.

```bash
npm run test:e2e
```

**You should see:** 11 passed:

```text
Running 11 tests using 6 workers

  ok  6 [chromium] › e2e\smoke.spec.ts:8:5 › the relay forwards /api/health/ to Django (79ms)
  ...
  ok  2 [chromium] › e2e\auth.spec.ts:122:5 › two tabs open at token expiry both stay logged in (6.3s)
  ok  3 [chromium] › e2e\auth.spec.ts:106:5 › two tabs that load at once, then reload together, stay logged in (6.8s)
  ok  5 [chromium] › e2e\auth.spec.ts:43:5 › sign up, stay logged in across a reload, log out (7.8s)

  11 passed (14.5s)
```

- On Linux Playwright prints the spec paths with `/` (`e2e/smoke.spec.ts`). The timings and the
  worker count vary from machine to machine.
- The eight 0C smoke tests are unchanged. The three new ones sign up with the test widget, check
  the cookie flags and that storage is empty, reload, log out, try the dead cookie (400) and a
  refresh without the header (403), and use `/settings` → `/login?next=` → back.
- "At token expiry" fast-forwards both tabs' clocks by 14½ minutes, so both refresh at the same
  moment.

Then the way CI runs it:

```bash
npm run build
CI=1 npm run test:e2e    # 11 passed, this time against `next start`
```

#### Step 10: Repository checks

**Where:** Any terminal.

**What this does:** Confirms `design/` is untouched, no unwanted agent files appeared, and that
saved test emails are git-ignored.

```bash
cd "$(git rev-parse --show-toplevel)"              # the repo root, from any folder inside it
git status --short design                          # prints nothing: design/ is untouched
for f in frontend/AGENTS.md frontend/CLAUDE.md; do [ -e "$f" ] && echo True || echo False; done   # False, then False
git check-ignore backend/tmp/mail/example.eml      # prints the path: emails written by EMAIL_PROVIDER=file are never committed
```

**You should see:** Nothing; `False` and `False`; then `backend/tmp/mail/example.eml`.

#### Step 11: CI on GitHub (after you push)

**Where:** Browser.

**What this does:** Checks that GitHub's automatic build passes after you push.

| URL | Expect |
|---|---|
| Your repository's **Actions** tab on github.com | A "CI" run for your push with three green jobs |

- New in this part: the E2E job signs up with the Turnstile test key, so the GitHub runner must reach
  `challenges.cloudflare.com` (the browser and Django both call it). If the sign-up tests fail at
  the widget, the run's "playwright-report" artifact shows the page.
- The agent couldn't run CI: only you push.

#### Step 12: Stop and clean up

**Where:** Every terminal window you still have open.

**What this does:** Shuts everything down and removes helper files.

- Stop the servers: `Ctrl+C` in each window. If `npm run dev` later says "Another next dev server is
  already running" with a PID, end it with `kill <that PID>` (`pgrep -af 'next|workerd'`
  lists leftover dev servers, and `ss -ltnp | grep -E ':(3000|8000)\b'` shows what holds the ports).
- Delete the helper files. The commands above create only the cookie jar:
  `rm -f /tmp/rz-jar.txt`.
- The test accounts stay in your local database: `part1_…` from step 3, the E2E's `e2e_…`,
  `tabs_…` and `expiry_…`, and the agent's own checks (`manual_check`, `visual_…`, `tf_…`,
  `phone_…`). Delete them in Django Admin → Users if you like.
  `docker compose down -v` (repo root) wipes the whole local database, which is destructive.
- Stop the containers and keep the data: `docker compose down` (repo root).
### Part 2: Email verification & password reset

Needs Part 0A's containers and virtualenv, Part 0C's frontend, and your own `backend/.env` and
`frontend/.env.local`. `EMAIL_PROVIDER=console` (the default) prints every email in the `runserver`
terminal. Part 2 adds no migration, no dependency and no env variable.

**Which terminal window for what.** Open the windows once and keep using the same ones:

| Window | What runs in it | Used in steps |
|---|---|---|
| Window 1 (server) | `python manage.py runserver` in `backend/`, venv active. Leave it running. Every email the app "sends" is printed here. | 3 to 9 (step 9 restarts it) |
| Window 2 (commands) | All the `curl` commands. **Use the same window for steps 3 to 7**: the variables you set in step 3 (`id`, `h`, `access`, `resend`) and later (`raw`, `key`, `verify`, `rp`, `login`, `refresh`, `rk`, `reset`) only live in that one terminal. If you close it, or open a new one, redo step 3. Needs `jq`. | 1 to 7, 9, 12 |
| Window 3 (frontend) | `npm run dev` in `frontend/`. Leave it running. | 8 (stopped before step 10) |

Things to know first:

- Sign-up still calls Cloudflare (Turnstile test keys), so it needs internet.
- Open the site as **http://localhost:3000**, as in Part 1.
- The outputs below were recorded on Linux on 2026-10-07. Numbers in names and times differ per run.
- A link in an email carries a key: the verification key has two `:` that arrive as `%3A`, and the
  commands below turn them back (`${raw//%3A/:}`). A browser does this for you.
- The limits count per address and per IP, and your local Redis remembers them for up to a day.
  Every command here uses a new address, so repeated runs are fine; if you test the per-IP limit of
  50 reset requests a day by hand, wait a day or restart Redis (`docker compose restart redis`).

#### Step 1: Check that nothing needs migrating and the email templates are in place

**Where:** Terminal window 2 (commands), starting in the repo root.

**What this does:** Starts the database containers, activates the Python environment and confirms
Django has nothing to migrate (Part 2 adds no tables) and that the new email templates exist.

```bash
# start in the repo root
docker compose up -d
cd backend
source .venv/bin/activate
python manage.py migrate                          # No migrations to apply.
python manage.py check                            # System check identified no issues (0 silenced).
python manage.py makemigrations --check --dry-run # No changes detected
ls templates/account/email
```

**You should see:** the three comments above are the expected messages of the three `python` lines
(nothing to apply, no problems, no model changes). The `ls` prints the template files:

```text
base_message.html
base_message.txt
email_confirmation_message.html
email_confirmation_message.txt
email_confirmation_signup_message.html
email_confirmation_signup_message.txt
email_confirmation_signup_subject.txt
email_confirmation_subject.txt
password_reset_key_message.html
password_reset_key_message.txt
password_reset_key_subject.txt
```

- The templates live in `backend/templates/`, not inside the app: `allauth` comes before
  `apps.accounts` in `INSTALLED_APPS`, so its own templates would win.

#### Step 2: Run the automated backend checks

**Where:** Same terminal as step 1 (window 2, in `backend/`, venv active).

**What this does:** Runs the whole backend test suite, then only the new Part 2 test files, then the
linter and formatter check.

```bash
python -m pytest                                    # 577 passed
python -m pytest apps/accounts/tests/test_email_verification.py apps/accounts/tests/test_resend_verification.py apps/accounts/tests/test_password_reset.py apps/accounts/tests/test_emails.py apps/accounts/tests/test_startup.py -q   # 101 passed
ruff check . ; ruff format --check .                # All checks passed! / 73 files already formatted
```

**You should see:** the full run takes a while and ends with `577 passed`; the second command ends
with `101 passed`; the last prints `All checks passed!` and `73 files already formatted`. (Counts may
grow later; what matters is that nothing fails.)

- The new files cover the verification link (including the `%3A` key and the exact 24-hour expiry),
  the resend cooldown and daily cap, the reset flow (identical answers and bytes for existing,
  unknown and inactive addresses, the limits, expiry, other browsers' refresh tokens), the emails
  themselves (subject, `From`, every link and the logo on the frontend origin, the Brevo payload) and
  the startup preload of allauth's deferred libraries.
- `test_middleware.py` and the settings tests changed too: the verify and password endpoints are now
  on the allow-list, and the new limits are pinned.

#### Step 3: Sign up a test account, and try the resend limits

**Where:** First window 1 (start the server), then window 2 (the commands). **Keep using window 2
for steps 4 to 7.**

**What this does:** Window 1 runs the Django server. In window 2 you create a brand-new account
through the API (which makes the server print the sign-up email in window 1), then check the account
is not verified yet.

Window 1: `python manage.py runserver` (in `backend/`, venv active). Leave it running; it prints
nothing more until a request or an email arrives.

Window 2 (no venv needed; needs `jq`):

```bash
cd backend                            # from the repo root
id=$(date +%H%M%S)                    # a unique suffix so the address is new each run
h=(-H 'Origin: http://localhost:3000' -H 'X-Requested-With: rumor-zero')   # headers every API call needs
json=$(jq -nc --arg id "$id" '{email: "part2-\($id)@example.test", username: "part2_\($id)", password: "correct-horse-battery-42", turnstile_token: "XXXX.DUMMY.TOKEN.XXXX"}')
access=$(curl -s "${h[@]}" -H "Content-Type: application/json" --data-binary "$json" http://localhost:8000/api/auth/app/v1/auth/signup | jq -r .meta.access_token)   # access = your login token
curl -s -H "Authorization: Bearer $access" http://localhost:8000/api/v1/me/ | jq -c '{username, is_email_verified}'
```

Sanity check (this step sets `id`, `h` and `access`; `access` must not be empty):

```bash
echo ${access:0:10}                   # prints the first 10 characters of the token, not an empty line
```

**You should see** in window 2 (the number in the name is your `id`, so it differs):

```text
{"username":"part2_010027","is_email_verified":false}
```

That means the account exists and its email is not verified yet.

**If it differs:** if `access` is empty or says `null`, the sign-up failed (`runserver` not running, or `jq` missing). Fix that and run this step again from
`id=$(date +%H%M%S)`.

Window 1 now shows the sign-up email:

```text
Subject: [Rumor Zero] Welcome to Rumor Zero: verify your email
From: Rumor Zero <no-reply@example.com>
To: part2-010027@example.test
...
Content-Type: text/plain; charset="utf-8"

Welcome to Rumor Zero

You can already read everything. Confirm your email address to post, comment and report.

Verify your email:
http://localhost:3000/verify-email/NzU%3A1xEAOb%3AbiPbvPBWC_1KxA5hYCK9XQPDSoulXssAgTKbBUd_AKE

This link expires 24 hours after it was sent. If you didn't create this account, you can ignore this email.

Rumor Zero
...
Content-Type: text/html; charset="utf-8"

<!DOCTYPE html>
...
<img src="http://localhost:3000/brand/email-logo.png" alt="Rumor Zero" width="160" ...>
```

- Two parts: the plain text (no image), then the HTML with the logo. No "Hello from localhost:8000!"
  any more. Every link, and the logo, points at `http://localhost:3000`; `From` is
  `DEFAULT_FROM_EMAIL`.

**Now the resend limits.** Run this in **window 2, the same terminal that signed up** (it uses
`$access` from the block above). Three requests to the "send me a verification email again" address:

- line 1: asks for a new link with your token, right after sign-up;
- line 2: asks again without any token;
- line 3: after waiting 61 seconds, asks again with your token.

```bash
resend=http://localhost:8000/api/v1/me/verification-email/
curl -s -w ' %{http_code}\n' -X POST -H "Authorization: Bearer $access" $resend     # 1: with token, too soon
curl -s -w ' %{http_code}\n' -X POST $resend                                        # 2: no token
sleep 61                                                                            # 3: nothing prints for 61 seconds: normal, just wait
curl -s -o /dev/null -w 'after 61 s: %{http_code}\n' -X POST -H "Authorization: Bearer $access" $resend
```

**You should see** three output lines, one per curl (the `sleep` prints nothing):

```text
{"detail":"We sent one recently. Wait a little before asking again.","code":"verification_email_throttled"} 429
{"detail":"Authentication credentials were not provided.","code":"not_authenticated"} 401
after 61 s: 204
```

1. `429`: cooldown refused. The sign-up email counts for the 60-second cooldown, so the first resend
   is refused.
2. `401`: no token, so the server doesn't know who you are.
3. `204`: sent. After a minute it works, and window 1 prints a second email, now called "Verify your
   email" (no "Welcome").

- The answer to the throttled call has no `Retry-After`: the full bucket may be the minute one or
  the daily one (10 resends a day per address; the sign-up email doesn't count).
- The command waits 61 seconds on purpose.

**If it differs:** if line 1 says `401` instead of `429`, `access` is empty: redo the sign-up part of
this step. If it says `204` instead of `429`, more than a minute passed since sign-up (that is fine,
the limit just wasn't tested).

#### Step 4: Verify the account with the link from the email

**Where:** Same terminal as step 3 (window 2). Needs `h`, `access` and `resend` from step 3.

**What this does:** Pretends to be the browser opening the link from the email: it sends the key to
the verify endpoint, then checks the account is now verified, then tries several things that must
fail (reusing the link, a forged key, no headers, resending once verified).

Copy the part of the **last** link in window 1 after `/verify-email/` into `raw` (the `%3A` stays as
it is). Replace the placeholder text:

```bash
raw='PASTE_THE_PART_AFTER_/verify-email/'
key=${raw//%3A/:}                      # turn %3A back into :
verify=http://localhost:8000/api/auth/app/v1/auth/email/verify
body=$(jq -nc --arg key "$key" '{key: $key}')
curl -s -i "${h[@]}" -H "Content-Type: application/json" --data-binary "$body" $verify | tr -d '\r' | grep -iE '^(HTTP|Cache-Control|Set-Cookie|\{)'   # 1: verify (prints 3 lines)
curl -s -H "Authorization: Bearer $access" http://localhost:8000/api/v1/me/ | jq -c '{username, is_email_verified}'                                  # 2: am I verified now?
curl -s -w ' %{http_code}\n' "${h[@]}" -H "Content-Type: application/json" --data-binary "$body" $verify                                              # 3: same link again
curl -s -w ' %{http_code}\n' "${h[@]}" -H "Content-Type: application/json" --data-binary '{"key": "forged"}' $verify                                   # 4: made-up key
curl -s -w ' %{http_code}\n' -H "Content-Type: application/json" --data-binary "$body" $verify                                                         # 5: without Origin / X-Requested-With headers
curl -s -w ' %{http_code}\n' -X POST -H "Authorization: Bearer $access" $resend                                                                        # 6: resend when already verified
curl -s -w ' %{http_code}\n' "${h[@]}" -X POST http://localhost:8000/api/auth/app/v1/auth/email/verify/resend                                          # 7: allauth's own resend address
```

**You should see** (7 commands, 9 lines; command 1 prints 3 lines):

```text
HTTP/1.1 200 OK
Cache-Control: max-age=0, no-cache, no-store, must-revalidate, private
{"status": 200}
{"username":"part2_010027","is_email_verified":true}
{"status": 400, "errors": [{"message": "Invalid or expired key.", "code": "invalid_or_expired_key", "param": "key"}]} 400
{"status": 400, "errors": [{"message": "Invalid or expired key.", "code": "invalid_or_expired_key", "param": "key"}]} 400
{"status": 403, "errors": [{"code": "csrf_failed", "message": "Reload the page and try again."}]} 403
{"detail":"Your email is already verified.","code":"already_verified"} 409
{"status": 404, "errors": [{"code": "not_found", "message": "Not found."}]} 404
```

1. Lines 1 to 3: the verification worked (`200`), with no cookie line.
2. Line 4: `is_email_verified` is now `true`.
3. Line 5: `400`, the same link used a second time is refused.
4. Line 6: `400`, a forged key is refused with the same message.
5. Line 7: `403`, refused because the `Origin` and `X-Requested-With` headers were missing.
6. Line 8: `409`, already verified, so nothing is sent.
7. Line 9: `404`, allauth's own resend address stays closed.

- The verification answered 200 with no cookies: a link never logs anyone in. allauth itself says
  401 here ("verified, but nobody is logged in"); the middleware turns that into 200.
- The same link again, and a forged one, both say `invalid_or_expired_key`: an expired link says
  the same. The call without `Origin` and `X-Requested-With` is refused like every other unsafe
  `/api/auth/` call.
- Once verified, the resend is a 409 and sends nothing. allauth's own `auth/email/verify/resend` is
  the code-flow view and stays closed (404).

**If it differs:** if command 1 prints a 400 and no `200`, the pasted key is from an older email or
still has a stray character; copy the **last** link in window 1 again. If commands 2 and later fail
with 401, `access` is empty: redo step 3.

#### Step 5: Forgot password gives the same answer for every address

**Where:** Same terminal as step 3 (window 2). Needs `h` and `id` from step 3.

**What this does:** Asks for a password reset for a real address and for an address that does not
exist, and checks the server answers byte for byte the same, so nobody can find out who has an
account.

```bash
rp=http://localhost:8000/api/auth/app/v1/auth/password/request
ask() { curl -s -i "${h[@]}" -H "Content-Type: application/json" --data-binary "$(jq -nc --arg e "$1" '{email: $e}')" $rp | tr -d '\r' | grep -v -iE '^(Date|Expires|Set-Cookie):'; }   # defines a helper, prints nothing
ask "part2-$id@example.test" > /tmp/rz-known.txt      # real account: answer saved to a file
ask "nobody-$id@example.test" > /tmp/rz-unknown.txt   # unknown address: answer saved to a file
cat /tmp/rz-known.txt
diff /tmp/rz-known.txt /tmp/rz-unknown.txt && echo "identical: status, headers and body"
```

**You should see:** the `ask` line and the two `ask ...` lines print nothing (their output goes to
files). `cat` shows the saved answer, then `diff` finds no difference:

```text
HTTP/1.1 200 OK
Server: WSGIServer/0.2 CPython/3.13.16
Content-Type: application/json
Cache-Control: max-age=0, no-cache, no-store, must-revalidate, private
X-Frame-Options: DENY
Content-Length: 15
X-Content-Type-Options: nosniff
Referrer-Policy: same-origin
Cross-Origin-Opener-Policy: same-origin

{"status": 200}
identical: status, headers and body
```

- Window 1 shows **one** new email, "Reset your password", addressed to the real account. Nothing is
  printed for the unknown address. The time-dependent headers (`Date`, `Expires`) are left out of the
  comparison on purpose.
- The link in that email is `http://localhost:3000/reset-password/<key>`: 32 hex digits, a time and
  a hash, valid for 24 hours and for one use.

**If it differs:** if `diff` prints lines instead of the "identical" message, that is a real bug in
the server; note it down. If the answer is `403`, `h` is empty: redo step 3.

**The limits** (each uses a new address, and an address that doesn't exist is limited the same way,
so the limit leaks nothing). Same window 2. The loop sends 6 requests for one address in a row, then
one request with a malformed address:

```bash
for i in 1 2 3 4 5 6; do
  r=$(curl -s -w ' %{http_code}' "${h[@]}" -H "Content-Type: application/json" --data-binary "$(jq -nc --arg e "busy-$id@example.test" '{email: $e}')" $rp)
  printf '%d  %s\n' "$i" "$r"
done
curl -s -w ' %{http_code}\n' "${h[@]}" -H "Content-Type: application/json" --data-binary '{"email": "not-an-email"}' $rp
```

**You should see:**

```text
1  {"status": 200} 200
2  {"status": 200} 200
3  {"status": 200} 200
4  {"status": 200} 200
5  {"status": 200} 200
6  {"status": 429} 429
{"status": 400, "errors": [{"message": "Enter a valid email address.", "code": "invalid", "param": "email"}]} 400
```

Requests 1 to 5 are accepted (`200`), request 6 is refused (`429`, too many), and the malformed
address is a `400`.

- Five a minute per address. There are also 10 a day per address and 50 a day per IP (the
  automated tests walk through both with a moved clock). A malformed address is a 400 and never
  counts.

#### Step 6: The reset logs you in and ends the other sessions

**Where:** Same terminal as step 3 (window 2), with window 1 open to read the email. Needs `h`, `id`
and `rp` from steps 3 and 5.

**What this does:** Logs in "in another browser" with the old password (its own cookie file), then
resets the password with the emailed key. Afterwards the other browser must be logged out, the new
session must work, and only the new password must log in.

First, log in "in another browser" with the old password. The `-c` option saves that browser's
cookies to `/tmp/rz-other.txt`:

```bash
login=http://localhost:8000/api/auth/app/v1/auth/login
refresh=http://localhost:8000/api/auth/app/v1/tokens/refresh
curl -s -c /tmp/rz-other.txt "${h[@]}" -H "Content-Type: application/json" --data-binary "$(jq -nc --arg e "part2-$id@example.test" '{email: $e, password: "correct-horse-battery-42"}')" $login | jq -c '{status}'
curl -s -o /dev/null -w 'other browser refresh before the reset: %{http_code}\n' -b /tmp/rz-other.txt -c /tmp/rz-other.txt "${h[@]}" -X POST $refresh
```

**You should see:**

```text
{"status":200}
other browser refresh before the reset: 200
```

The login worked and the other browser can refresh its session.

Next, ask for a link for the real address once more, wait for it in window 1, and copy the part
after `/reset-password/` into `rk` (replace the placeholder):

```bash
curl -s -o /dev/null -w 'request: %{http_code}\n' "${h[@]}" -H "Content-Type: application/json" --data-binary "$(jq -nc --arg e "part2-$id@example.test" '{email: $e}')" $rp
rk='PASTE_THE_PART_AFTER_/reset-password/'
reset=http://localhost:8000/api/auth/app/v1/auth/password/reset
curl -s -o /dev/null -w 'key check: %{http_code}\n' -H "X-Password-Reset-Key: $rk" $reset
curl -s -w ' %{http_code}\n' -H "X-Password-Reset-Key: nonsense" $reset
curl -s -w ' %{http_code}\n' "${h[@]}" -H "Content-Type: application/json" --data-binary "$(jq -nc --arg k "$rk" '{key: $k, password: "short"}')" $reset
out=$(curl -s -i -c /tmp/rz-new.txt "${h[@]}" -H "Content-Type: application/json" --data-binary "$(jq -nc --arg k "$rk" '{key: $k, password: "a-brand-new-passphrase-77"}')" $reset | tr -d '\r')
printf '%s\n' "$out" | grep -iE '^(HTTP|Set-Cookie|Cache-Control)' | sed -E 's/rz_refresh=[^;]+/rz_refresh=<token>/'
printf '%s' "$(printf '%s\n' "$out" | sed -n '$p')" | jq -r '"user: \(.data.user.username); meta fields: \(.meta | keys_unsorted | join(", ")); access token: \(.meta.access_token | length) characters"'
curl -s -w ' %{http_code}\n' -b /tmp/rz-other.txt "${h[@]}" -X POST $refresh
curl -s -o /dev/null -w 'the new session refreshes: %{http_code}\n' -b /tmp/rz-new.txt -c /tmp/rz-new.txt "${h[@]}" -X POST $refresh
curl -s -w ' %{http_code}\n' "${h[@]}" -H "Content-Type: application/json" --data-binary "$(jq -nc --arg k "$rk" '{key: $k, password: "yet-another-passphrase-55"}')" $reset
curl -s -o /dev/null -w 'old password: %{http_code}\n' "${h[@]}" -H "Content-Type: application/json" --data-binary "$(jq -nc --arg e "part2-$id@example.test" '{email: $e, password: "correct-horse-battery-42"}')" $login
curl -s -o /dev/null -w 'new password: %{http_code}\n' "${h[@]}" -H "Content-Type: application/json" --data-binary "$(jq -nc --arg e "part2-$id@example.test" '{email: $e, password: "a-brand-new-passphrase-77"}')" $login
```

**You should see** (the `rk=` and `reset=` lines print nothing):

```text
request: 200
key check: 200
{"status": 400, "errors": [{"message": "The password reset token was invalid.", "code": "invalid_password_reset", "param": "key"}]} 400
{"status": 400, "errors": [{"message": "This password is too short. It must contain at least 8 characters.", "code": "password_too_short", "param": "password"}]} 400
HTTP/1.1 200 OK
Cache-Control: max-age=0, no-cache, no-store, must-revalidate, private
Set-Cookie:  rz_refresh=<token>; expires=…; HttpOnly; Max-Age=1209600; Path=/api/auth/; SameSite=Lax
Set-Cookie:  rz_session=1; expires=…; Max-Age=1209600; Path=/; SameSite=Lax
user: part2_010027; meta fields: is_authenticated, access_token; access token: 373 characters
{"status": 400} 400
the new session refreshes: 200
{"status": 400, "errors": [{"message": "The password reset token was invalid.", "code": "invalid_password_reset", "param": "key"}]} 400
old password: 400
new password: 200
```

What each line means, in order:

1. `request: 200`: the reset email was requested (it appears in window 1).
2. `key check: 200`: the emailed key is valid.
3. `... 400` with "token was invalid": the made-up key `nonsense` is refused.
4. `... 400` with "too short": a weak password is refused (and does not use the key up).
5. Lines `HTTP/1.1 200 OK` to the two `Set-Cookie` lines, then `user: ...`: the real reset worked and
   logged this session in (an access token and two cookies, like a login).
6. `{"status": 400} 400`: **the other browser's refresh now fails**.
7. `the new session refreshes: 200`: the session created by the reset still works.
8. `... 400` with "token was invalid": the same link a second time is refused.
9. `old password: 400`: the old password no longer logs in.
10. `new password: 200`: the new password does.

- The key check is the page's pre-check: `GET` with the key in `X-Password-Reset-Key` (it answers
  with the account's details, which the page ignores). A refused weak password doesn't use the key up.
- The reset answers like a login: an access token in `meta` and the same two cookies, and the
  browser that did it is logged in.
- **The other browser's refresh now fails (400):** the password changed, so every other session
  ends the next time it refreshes. Its access token still works for up to 15 minutes, like after a
  logout. The same link again is refused.

**If it differs:** if `key check` is not `200`, `rk` is wrong or empty: copy the part after
`/reset-password/` from the **last** reset email in window 1 and set `rk` again.

#### Step 7: An expired verification link

**Where:** A terminal in `backend/` with the venv active (window 2 after `source .venv/bin/activate`,
or a spare window). It only reads the database, so `runserver` can keep running.

**What this does:** Builds the key a verification link would have had 25 hours ago, so you can see
the "expired" screen in step 8.

Needs an account whose address is still unverified: sign up another one the way step 3 does (a new
`id`), then forge the key a link would have had 25 hours ago:

```bash
# in backend/ with the venv active; replace ID with the id of the unverified account
python manage.py shell -c "import time; from unittest import mock; from allauth.account.models import EmailAddress, EmailConfirmationHMAC; a = EmailAddress.objects.get(email='part2-ID@example.test'); real = time.time; mock.patch('time.time', lambda: real() - 25 * 3600).start(); print(EmailConfirmationHMAC(a).key)"
```

**You should see:** a key with two `:` (after Django's "objects imported" line).

- Open `http://localhost:3000/verify-email/<that key>` in the browser (step 8) and you get the
  expired state, with a working "Send a new link" once you are logged in as that account.
- The automated tests do the same with an exact 86 399 s / 86 401 s boundary.

**If it differs:** if you get `EmailAddress matching query does not exist`, the `ID` is wrong; use
the `id` of the account you signed up (its email is `part2-<id>@example.test`).

#### Step 8: Look at the pages in the browser

**Where:** Browser (http://localhost:3000), with window 1 (`runserver`) and window 3 (`npm run dev`)
running.

**What this does:** Walks through every new screen by hand: verify email, forgot password and reset
password.

Window 1's `runserver` and a third window's `npm run dev` (in `frontend/`) are running. Use
http://localhost:3000, a new email address each time, and compare with the Stitch screens
`a4_verify_email`, `a5_forgot_password` and `a6_reset_password` in
`design/stitch/stitch_website_sitemap_grid_builder/` (the logo replaces their emblem tiles, and
their state switcher, "Simulate instant link click" and jargon footers are gone).

**You should see**, for each row, what is in the "Expect" column:

| Do this | Expect |
|---|---|
| Sign up at /signup with a new email, username and `correct-horse-battery-42` | You land on **/verify-email** (not /home): "Verify your email", "We sent a verification link to **your address**", a blue "Read-only for now" callout, a tinted "Resend email (58s)" counting down, the spam hint, "Continue browsing read-only →" and "Links expire 24 hours after they're sent." |
| Wait for the countdown to reach 0 | The button turns blue: "Resend email". Click it: the text "We sent a new verification link. Check your inbox." appears under it, the countdown starts again at 60, and window 1 prints a second email. |
| Click "Continue browsing read-only →" | /home with the amber banner "Verify your email to post, comment and report." and a **Resend link** button. The rail's **New post** button is faded. |
| Click **New post** (rail, or the bottom tab at 390 px) | Nothing opens; a dark toast says "Verify your email to post. Check your inbox, or resend the link from the banner." Tab to the button: it takes focus, and a screen reader reads "Verify your email to post." |
| Click **Resend link** twice in a row | The first click is refused if you signed up less than a minute ago (toast: "We sent one recently. Wait a little before asking again.") and the button shows "Resend link (60s)"; after a minute it works (toast: "We sent a new verification link. Check your inbox."). |
| Copy the link from the **last** email in window 1 and open it in a second tab | "Your email is verified" with **Start posting →**. The first tab's banner disappears by itself within a moment (the tabs tell each other), and New post is no longer faded. |
| Reload the link's tab | "Your email is already verified": the link was used. |
| Log out, then open the same link again | "This link has expired" with "Log in to send a new link" (it points at `/login?next=%2Fverify-email`). |
| Open `/verify-email/Mg%3A1vABcd%3Aabc-DEF_123` | The same expired state (a made-up key). |
| Open /login and click **Forgot password?** (right under the password field) | /forgot-password: "Reset your password", an email field, "Send reset link →", "Back to log in". |
| Submit an empty field, then `not-an-email` | "Enter your email address.", then "Enter a valid email address." under the field. |
| Submit the real address, then repeat with an address that doesn't exist | The same "Check your inbox" message both times: "If an account exists for **that address**, we've sent a link to reset your password. It expires in 24 hours." Window 1 printed an email only for the real one. "Use a different email" goes back to the form. |
| Open the link from the reset email | A short skeleton, then "Create new password": New password with the strength bar, Confirm new password, show/hide toggles, "Use at least 8 characters.", and the callout "This also signs you out on your other devices." |
| Type `abc` and `abd`, submit | "Use at least 8 characters." under New password; nothing is sent. |
| Type a good password and a different confirmation | "The passwords don't match." under Confirm; nothing is sent. |
| Type `password1234` in both | Django refuses it: "This password is too common." under New password. |
| Type a good password in both and submit | The toast "Password changed. You're logged in." and /home with your @username in the rail. |
| Open the same reset link again | "This link has expired" with **Request a new link** (→ /forgot-password), before any password field is shown. |
| Log out and log in with the new password | /home. The old password says "That email and password don't match." |
| Phone width (F12 → device toolbar, 390 px) on every page above | No sideways scrolling; the Resend button, the callouts and the form fit the card. |

#### Step 9: The emails on disk, and where every link points

**Where:** First window 1 (restart the server), then window 2 (from the repo root).

**What this does:** Restarts the server so emails are written to files instead of the terminal, then
inspects the newest email file to prove every link points at the frontend (`localhost:3000`) and never
at the backend.

Stop `runserver` in window 1 (`Ctrl+C`) and start it so that emails go to files (in `backend/`, venv
active):

```bash
EMAIL_PROVIDER=file python manage.py runserver
```

Sign up or request a reset in the browser (so an email is written), then in window 2 (repo root):

```bash
f=$(ls -t backend/tmp/mail/*.log | head -1)                                                    # the newest email file
grep -E '^(From|To|Subject):' "$f"                                                             # who, to whom, subject
grep -oE '(href|src)="[^"]+"' "$f" | sed -E 's|(="https?://[^/"]+).*|\1…|' | sort -u          # every link and the logo, shortened to the origin
grep -oE 'https?://[^ "<]+' "$f" | sed -E 's|^(https?://[^/]+).*|\1|' | sort -u               # every URL in the file, shortened to the origin
git check-ignore "$f"                                                                          # prints the path if git ignores it
```

**You should see** (the subject depends on which email you triggered; the address and file name differ):

```text
Subject: [Rumor Zero] Reset your password
From: Rumor Zero <no-reply@example.com>
To: part2-012510@example.test
href="http://localhost:3000…
src="http://localhost:3000…
http://localhost:3000
backend/tmp/mail/20261006-192649-135804298251632.log
```

- `From` is your `DEFAULT_FROM_EMAIL`. Every `href`, the logo `src` and every URL in the file start
  with `http://localhost:3000` (your `FRONTEND_ORIGIN`): there is no backend address in any email.
- `git check-ignore` prints the path: emails written by `EMAIL_PROVIDER=file` are never committed.
  This is the folder the E2E tests read.
- Stop this server and start a normal `python manage.py runserver` again if you want the console
  emails back.

**If it differs:** if `ls` says there is no such file, the server was not started with
`EMAIL_PROVIDER=file`, or no email was triggered yet; start it as above and sign up again.

#### Step 10: Automated frontend checks

**Where:** A terminal in `frontend/` (stop `npm run dev` in window 3 first with `Ctrl+C`, then reuse
window 3).

**What this does:** Runs the frontend linters, type check, unit tests and a production build.

```bash
npm run lint             # no output after the command line
npm run lint:tokens      # lint:tokens OK (no default palette, raw hex, stray radius, shadow or type size)
npm run typecheck        # no output after the command line
npm run format:check     # All matched files use Prettier code style!
npm test                 # Test Files  65 passed (65) / Tests  708 passed (708)
npm run build
```

**You should see:** the messages in the comments (`npm run lint` and `npm run typecheck` print
nothing after the command line; that means success). `npm run build` takes a minute and ends with a
route list that gains these lines (the two key pages are dynamic, because the key is a route
parameter):

```text
├ ○ /forgot-password
├ ƒ /reset-password/[key]
├ ○ /verify-email
└ ƒ /verify-email/[key]
```

- The new screens have tests for every state: verifying, verified, already verified, expired and
  failed; the idle and sent forms; the expired, checking, mismatch and weak-password states; the
  resend countdown; New post gating (both copies, with their own hint ids); the banner's Resend; the
  sign-up redirect with and without `?next=`; the two-tab "user-changed" message.

#### Step 11: The E2E tests, dev mode and CI mode

**Where:** The same terminal in `frontend/` (window 3). Stop `runserver` in window 1 first.

**What this does:** Playwright drives a real browser through the whole flow. It starts its own
servers, so window 1 must be stopped to free the ports.

Stop `runserver` too: Playwright then starts its own Django with an in-memory cache, and with
`EMAIL_PROVIDER=file`.

```bash
npm run test:e2e
```

**You should see** (takes about half a minute; the order of the tests and the timings differ):

```text
Running 15 tests using 6 workers

  ok   4 [chromium] › e2e/email-flows.spec.ts:101:5 › an unknown address gets the same page and no email (6.0s)
  ...
  ok   6 [chromium] › e2e/email-flows.spec.ts:53:5 › forgot password → read the email → reset → logged in → log in with the new password (18.3s)

  15 passed (29.2s)
```

- Eleven tests are Parts 0C and 1 (`auth.spec.ts` now continues from `/verify-email` to `/home`). The
  four new ones are in `email-flows.spec.ts`:
  1. sign up → New post is `aria-disabled` → read the email from `backend/tmp/mail` → open the link
     → verified → "Start posting" → the banner is gone and New post is enabled → the used link says
     "already verified";
  2. forgot password → read the email → a mismatch error → reset → logged in → log out → the old
     password fails and the new one works, and the used link is expired;
  3. an unknown address gets the same page and no email;
  4. dead reset and verification links show their expired states.
- The first request of a cold Django used to fail now and then with a 500 when several sign-ups
  arrived together; that is fixed (MEMORY, 2026-10-07).

Then the way CI runs it (a production build, tested with `next start`):

```bash
npm run build
CI=1 npm run test:e2e    # 15 passed, this time against `next start`
```

**You should see:** `15 passed` again.

#### Step 12: Repository checks

**Where:** Terminal window 2 (any terminal; the first command moves to the repo root).

**What this does:** Confirms nothing you should not commit (design files, env files, mail logs) is
pending in git. These are read-only git commands.

```bash
cd "$(git rev-parse --show-toplevel)"              # the repo root, from any folder inside it
git status --short design                          # prints nothing: design/ is untouched
git status --short | grep -E '\.env|tmp/'          # prints nothing: no env file and no mail file is a candidate for a commit
git status --short backend/templates               # ?? backend/templates/ (new, until you commit it)
```

**You should see:** nothing from the second and third lines of output (the comments explain), and
`?? backend/templates/` from the last command until you commit it.

#### Step 13: CI on GitHub (after you push)

**Where:** Browser.

**What this does:** Checks that the automatic tests also pass on GitHub once you have pushed.

| URL | Expect |
|---|---|
| Your repository's **Actions** tab on github.com | A "CI" run for your push with three green jobs |

- No workflow change was needed: Playwright sets `EMAIL_PROVIDER=file` for the Django it starts, and
  the process environment wins over the `backend/.env` the job copies from `.env.example`.
- The agent couldn't run CI: only you push.

#### Step 14: Stop and clean up

**Where:** Every terminal window, plus the repo root for the last commands.

**What this does:** Stops the servers and removes the temporary files these steps created.

- Stop the servers: `Ctrl+C` in each window (leftover `next dev`: step 12 of Part 1).
- Delete the helper files:

  ```bash
  rm -f /tmp/rz-known.txt /tmp/rz-unknown.txt /tmp/rz-other.txt /tmp/rz-new.txt
  ```

- `backend/tmp/mail/` fills up with `.log` files from `EMAIL_PROVIDER=file` and the E2E runs. It is
  git-ignored; delete the folder whenever you like.
- The test accounts stay in your local database: `part2_…` from these steps, the E2E's `verify_…`
  and `reset_…`, and the agent's `shot_…`/`p_shot_…`. Delete them in Django Admin → Users if you
  like. `docker compose down -v` (repo root) wipes the whole local database, which is destructive.
- Stop the containers and keep the data: `docker compose down` (repo root).

### Part 3: Continue with Google

Needs Part 0A's containers and virtualenv, Part 0C's frontend, and your own `backend/.env` and
`frontend/.env.local`. Part 3 adds no dependency and no env variable (both Google client-ID variables
have been in the example files since Part 0A). It does add allauth's own `socialaccount` tables:
`migrate` applies six migrations of theirs, and we add none.

**Which terminal window for what.** Open the windows once and keep using the same ones:

| Window | What runs in it | Used in steps |
|---|---|---|
| Window 1 (server) | `python manage.py runserver` in `backend/`, venv active. Leave it running; it is restarted in steps 5 and 6. | 4 to 8 |
| Window 2 (commands) | All the `curl` and `python manage.py` commands. | 1 to 8 |
| Window 3 (frontend) | `npm run dev` in `frontend/`. Leave it running; it is restarted in step 6. | 6 to 8 |
| Browser | Steps 6 to 8 | 6 to 8 |

Things to know first:

- **Steps 1 to 6 need no Google account.** Steps 7 and 8 do: they are the manual check from
  `task.md` ("works end to end on `http://localhost:3000` with your client ID"), because a real
  Google sign-in can't be automated. The agent that built this part could not run steps 7 and 8; the
  rest was run on Linux on 2026-10-08, and the outputs below are what it printed.
- Steps 4 and 5 use **no real client ID**: step 4 leaves it blank, step 5 uses a made-up one
  (`rz-manual-test.apps.googleusercontent.com`) that is set only for that `runserver`. Neither step
  edits `backend/.env`, and neither needs your real client ID.
- The new-user and linking rules (staff, inactive, Gmail or Workspace only, password wipe, verified
  address) are covered by 98 automated tests that sign real RS256 tokens against a fake Google
  certificate (step 2). Step 5 only checks what is visible from outside.
- Google's script and certificates need internet. Step 5's last request asks Google for its
  certificates, so it needs internet too.
- Your Google client's **Authorized JavaScript origins** must contain `http://localhost:3000` (and
  `http://localhost`): ENV_GUIDE §1.6. New origins can take minutes (rarely hours) to start working.

#### Step 1: Apply allauth's Google tables and check nothing else changed

**Where:** Terminal window 2 (commands), starting in the repo root.

**What this does:** Starts the database containers, activates the Python environment, applies
allauth's `socialaccount` migrations and confirms we have no model changes of our own.

```bash
# start in the repo root
docker compose up -d
cd backend
source .venv/bin/activate
python manage.py migrate                           # first time: six "Applying socialaccount.… OK" lines
python manage.py check                             # System check identified no issues (0 silenced).
python manage.py makemigrations --check --dry-run  # No changes detected
python manage.py showmigrations socialaccount
```

**You should see:** the first run of `migrate` after pulling Part 3 lists these lines (a database
that already has them says `No migrations to apply.`):

```text
  Applying socialaccount.0001_initial... OK
  Applying socialaccount.0002_token_max_lengths... OK
  Applying socialaccount.0003_extra_data_default_dict... OK
  Applying socialaccount.0004_app_provider_id_settings... OK
  Applying socialaccount.0005_socialtoken_nullable_app... OK
  Applying socialaccount.0006_alter_socialaccount_extra_data... OK
```

Then the two checks print their messages (in the comments above), and `showmigrations` ends with:

```text
socialaccount
 [X] 0001_initial
 [X] 0002_token_max_lengths
 [X] 0003_extra_data_default_dict
 [X] 0004_app_provider_id_settings
 [X] 0005_socialtoken_nullable_app
 [X] 0006_alter_socialaccount_extra_data
```

#### Step 2: Run the automated backend checks

**Where:** Same terminal as step 1 (window 2, in `backend/`, venv active).

**What this does:** Runs the whole backend test suite, then only the new Part 3 test files, then the
linter and formatter check.

```bash
python -m pytest                                    # 704 passed
python -m pytest apps/accounts/tests/test_google_login.py apps/accounts/tests/test_usernames.py -q   # 98 passed
ruff check . ; ruff format --check .                # All checks passed! / 77 files already formatted
```

**You should see:** the full run ends with `704 passed` (it takes about 25 seconds), the second
command with `98 passed` (60 in `test_google_login.py`, 38 in `test_usernames.py`), and the last prints
`All checks passed!` and `77 files already formatted`. (Counts may grow later; what matters is that
nothing fails.)

- `test_google_login.py` signs real RS256 ID tokens with a test key and serves the matching
  certificate in place of Google's, so allauth's own checks (`aud`, `iss`, `exp`, `iat`, signature and
  replay) run unpatched. It covers: a new user (verified, generated username, no display name, no
  password), linking a verified or unverified account, Gmail and Workspace only, no staff linking,
  inactive accounts, every kind of bad token and request, the 404 when disabled, the session rules
  and the rate limit.
- `test_usernames.py` covers the username rules ("Ada", "José", "Mary-Jane", "李", reserved words,
  collisions).

#### Step 3: Run the automated frontend checks

**Where:** Terminal window 2, then `cd ../frontend`. Playwright (the last command) starts Django and
Next itself, so **no servers may be running on ports 3000 and 8000** (it reuses them if they are, with
whatever settings they have).

**What this does:** Runs the linters, the type check, the component tests, the production build and
the end-to-end tests.

```bash
cd ../frontend                                      # from backend/
npm run lint ; npm run lint:tokens ; npm run typecheck ; npm run format:check
npm test                                            # 67 files, 747 tests passed
npm run build
npm run test:e2e                                    # 15 passed
```

**You should see:** the first line prints nothing from ESLint and TypeScript and ends with
`lint:tokens OK (…)` and `All matched files use Prettier code style!`. `npm test` ends with
`Test Files  67 passed (67)` and `Tests  747 passed (747)`. `npm run build` lists the routes (as in
Part 2). `npm run test:e2e` ends with `15 passed`.

- The new component tests are `GoogleButton.test.tsx` (20) and `google-identity.test.ts` (7); the login
  and sign-up form tests and `auth-api.test.ts` grew too.
- The E2E run pins an empty Google client ID for both servers, so it never contacts Google: the button
  is hidden there.
- To run the E2E in CI mode (against the production build, with no client ID baked in):
  `NEXT_PUBLIC_GOOGLE_CLIENT_ID= npm run build && CI=1 npm run test:e2e` ends with `15 passed` too.

#### Step 4: With no client ID, Google sign-in is switched off

**Where:** First window 1 (start the server), then window 2 (the commands).

**What this does:** An empty `GOOGLE_OAUTH_CLIENT_ID` disables the feature "cleanly": the endpoint
answers 404, exactly like a path that doesn't exist. The variable is emptied for this one `runserver`
only (the process environment beats `backend/.env`).

Window 1 (in `backend/`, venv active; stop any other `runserver` first with `Ctrl+C`):

```bash
GOOGLE_OAUTH_CLIENT_ID= python manage.py runserver
```

Window 2:

```bash
h=(-H 'Origin: http://localhost:3000' -H 'X-Requested-With: rumor-zero')    # headers every API call needs
url=http://localhost:8000/api/auth/app/v1/auth/provider/token
body='{"provider":"google","process":"login","token":{"client_id":"x.apps.googleusercontent.com","id_token":"a.b.c"}}'
curl -s -w ' %{http_code}\n' "${h[@]}" -H "Content-Type: application/json" --data-binary "$body" $url   # 1: the sign-in
curl -s -w ' %{http_code}\n' "${h[@]}" $url                                                              # 2: a GET
curl -s -o /dev/null -w '%{http_code}\n' "${h[@]}" -X POST -H "Content-Type: application/json" --data-binary '{}' http://localhost:8000/api/auth/app/v1/auth/provider/signup   # 3: allauth's other social paths
curl -s -o /dev/null -w '%{http_code}\n' "${h[@]}" http://localhost:8000/api/auth/app/v1/account/providers                                                                    # 4
```

**You should see** (four commands, four answers):

```text
{"status": 404, "errors": [{"code": "not_found", "message": "Not found."}]} 404
{"status": 404, "errors": [{"code": "not_found", "message": "Not found."}]} 404
404
404
```

- Commands 3 and 4 show that allauth's other social endpoints (`auth/provider/signup`,
  `account/providers`, and `auth/provider/redirect`) are never reachable, with or without a client ID.

#### Step 5: With a client ID, check what an outsider can and can't do

**Where:** Window 1 (restart the server), then window 2. Window 2 must be the same terminal for the
whole step (the variables only live there).

**What this does:** Restarts the server with a made-up client ID, so the endpoint is on. Then it sends
requests that are not a real Google sign-in. Each must be refused, and none may crash the server. (A
real, signed token can only come from Google, so the success cases are in step 2's tests and steps 7
and 8.)

Window 1 (`Ctrl+C` the server of step 4, then, in `backend/` with the venv active):

```bash
GOOGLE_OAUTH_CLIENT_ID=rz-manual-test.apps.googleusercontent.com python manage.py runserver
```

Window 2:

```bash
h=(-H 'Origin: http://localhost:3000' -H 'X-Requested-With: rumor-zero')
url=http://localhost:8000/api/auth/app/v1/auth/provider/token
cid=rz-manual-test.apps.googleusercontent.com
b64() { printf '%s' "$1" | base64 -w0 | tr '+/' '-_' | tr -d '='; }                       # base64url, as JWTs use
payload=$(b64 '{"iss":"https://accounts.google.com","aud":"'$cid'","sub":"1","email":"x@gmail.com","email_verified":true,"exp":4000000000}')
rs=$(b64 '{"alg":"RS256","kid":"forged-kid","typ":"JWT"}').$payload.$(b64 'not-a-real-signature')     # looks like Google's, is not
hs=$(b64 '{"alg":"HS256","kid":"k","typ":"JWT"}').$payload.$(b64 'sig')                                # the wrong algorithm
nokid=$(b64 '{"alg":"RS256","typ":"JWT"}').$payload.$(b64 'sig')                                      # no key id
mk() { printf '{"provider":"google","process":"login","token":{"client_id":"%s","id_token":"%s"}}' "$1" "$2"; }
post() { curl -s -w ' %{http_code}\n' "${h[@]}" -H "Content-Type: application/json" --data-binary "$1" $url; }
echo "1 no headers:";     curl -s -w ' %{http_code}\n' -H "Content-Type: application/json" --data-binary "$(mk $cid $rs)" $url
echo "2 garbage token:";  post "$(mk $cid not-a-jwt)"
echo "3 HS256:";          post "$(mk $cid $hs)"
echo "4 no kid:";         post "$(mk $cid $nokid)"
echo "5 wrong client_id:"; post "$(mk other.apps.googleusercontent.com $rs)"
echo "6 connect:";        post '{"provider":"google","process":"connect","token":{"client_id":"'$cid'","id_token":"'$rs'"}}'
echo "7 GET:";            curl -s -w ' %{http_code}\n' "${h[@]}" $url
echo "8 forged RS256 (asks Google for its certificates; needs internet):"; post "$(mk $cid $rs)"
```

**You should see** (eight labels, each followed by one answer):

```text
1 no headers:
{"status": 403, "errors": [{"code": "csrf_failed", "message": "Reload the page and try again."}]} 403
2 garbage token:
{"status": 400, "errors": [{"code": "invalid_token", "message": "Invalid token.", "param": "token"}]} 400
3 HS256:
{"status": 400, "errors": [{"code": "invalid_token", "message": "Invalid token.", "param": "token"}]} 400
4 no kid:
{"status": 400, "errors": [{"code": "invalid_token", "message": "Invalid token.", "param": "token"}]} 400
5 wrong client_id:
{"status": 400, "errors": [{"code": "invalid_token", "message": "Invalid token.", "param": "token"}]} 400
6 connect:
{"status": 400, "errors": [{"code": "invalid_token", "message": "Invalid token.", "param": "token"}]} 400
7 GET:
{"status": 404, "errors": [{"code": "not_found", "message": "Not found."}]} 404
8 forged RS256 (asks Google for its certificates; needs internet):
{"status": 400, "errors": [{"message": "Invalid token.", "code": "invalid_token", "param": "token"}]} 400
```

- 1: no `Origin` / `X-Requested-With`, so refused before anything else (the same guard as login).
- 2 to 6: refused by our own shape check (`apps/accounts/google.py`) without calling Google. Without
  it, 3 and 4 would crash allauth with a 500. A real token has an `RS256` header with a key id, a
  client ID equal to the server's, and `process` "login".
- 8: passes our check, so allauth asks Google for its certificates, finds no key called
  `forged-kid` and refuses. (The key order in this body is allauth's own, so it differs from 2 to 6.)
- Window 1 printed one line for command 5, naming the variables and never the values:
  `WARNING apps.accounts.google: A Google sign-in used a client_id that differs from GOOGLE_OAUTH_CLIENT_ID; check that NEXT_PUBLIC_GOOGLE_CLIENT_ID holds the same value`.

**Now the rate limit.** A Google sign-in shares allauth's `login` limit: 30 a minute per IP. Every
attempt counts, valid or not. The loop below uses its own source address (`127.0.0.3`), so it starts
with an empty bucket whatever you did before. Run it in the same terminal as the block above (it
uses `$h`, `$url`, `$cid` and `mk` from there):

```bash
body=$(mk $cid not-a-jwt)
for i in $(seq 1 31); do curl -s -o /dev/null -w '%{http_code}\n' --interface 127.0.0.3 "${h[@]}" -H "Content-Type: application/json" --data-binary "$body" $url; done | sort | uniq -c
curl -s -w ' %{http_code}\n' --interface 127.0.0.3 "${h[@]}" -H "Content-Type: application/json" --data-binary "$body" $url
curl -s -o /dev/null -w 'another address: %{http_code}\n' --interface 127.0.0.4 "${h[@]}" -H "Content-Type: application/json" --data-binary "$body" $url
```

**You should see:**

```text
     30 400
      1 429
{"status": 429} 429
another address: 400
```

That is 30 refusals, then the 31st and every later request refused for the minute (`429`), while
another address is not affected.

**If it differs:** `Connection refused` means window 1 isn't running `runserver`; `404` on command 2
means the server still runs with no client ID (restart it as above); `curl: Bind failed` on the
`--interface` lines means your system doesn't accept `127.0.0.3` as a source address: leave the option
out and wait a minute since your last attempts.

#### Step 6: Look at the Google button in the browser

**Where:** Window 1 (restart the server **without** the override), window 3 (frontend), then the
Browser.

**What this does:** Starts both servers the normal way, so they read **your own** `backend/.env` and
`frontend/.env.local` (the same client ID in both; this step never prints it), then shows what the two
pages look like with and without a client ID.

Window 1 (`Ctrl+C` the server of step 5, then in `backend/` with the venv active):

```bash
python manage.py runserver
```

Window 3 (in `frontend/`):

```bash
npm run dev
```

In the Browser:

| URL | You should see |
|---|---|
| http://localhost:3000/login | Under the "Welcome back" text: a white button, **Continue with Google** (Google's own button, with its colourful "G"), then a thin line with **or log in with email**, then the email and password form |
| http://localhost:3000/signup | The same button under "Create your account", then **or continue with email** and the form with the Turnstile box |

- At phone width (shrink the window to about 390 px, or use the browser's device toolbar) the button
  stays inside the card and the page doesn't scroll sideways.
- The button is Google's, not ours: its width follows the card (up to 400 px) and its text is always
  English.
- **Close the popup.** Type something in the email and password boxes, then click the Google button.
  A Google window opens ("Sign in with Google"). Close it without choosing an account. Nothing
  changes on the page: your typed text is still there, there is no error and nothing says "Signing in".
  Google gives a page no signal for a closed popup, so "nothing happens" is the correct behaviour.
- **Without a client ID the button is hidden.** Stop window 3 (`Ctrl+C`) and run
  `NEXT_PUBLIC_GOOGLE_CLIENT_ID= npm run dev`, then reload both pages: no Google button and no "or"
  line, just the form. (The value is read when the dev server starts.) Stop it and run `npm run dev`
  again before step 7.

**If it differs:** if the button area stays empty, open the browser console: "The given client ID is
not found" means the ID in `frontend/.env.local` is wrong; "Not a valid origin for the client" means
`http://localhost:3000` isn't in the client's Authorized JavaScript origins yet (ENV_GUIDE §1.6; wait a
few minutes after adding it). If a red box says "Google sign-in couldn't load. Check your connection,
or use email.", the script `https://accounts.google.com/gsi/client` is blocked (ad blocker, offline).

#### Step 7: Sign up with Google (manual, needs a Google account)

**Where:** Browser, then window 2.

**What this does:** A brand-new person signs up with one click. The agent could not run this step.

1. Open http://localhost:3000/signup and click **Continue with Google**. In the popup choose a Google
   account whose address has **no account here yet**.
2. You should land on **/home** (or the page named in `?next=`), logged in. There is **no** yellow
   "Verify your email" banner, and the New post button is enabled: a Google address is already verified.
3. The side menu shows your handle, **`@` plus your Google first name in lowercase**: `@ada`, or `@ada_`
   and four digits when that name is taken, or `@member_` and six characters when the first name has
   no Latin letters. It is never made from your email address. The display name stays empty.
4. Reload the page: you stay logged in. Log out from the account menu.

Then, in window 2 (in `backend/`, venv active), look at what was created. (Django may first print
`12 objects imported automatically …`; that is not part of the answer.)

```bash
python manage.py shell -c "from allauth.socialaccount.models import SocialAccount; a = SocialAccount.objects.filter(provider='google').select_related('user').order_by('-date_joined').first(); print(a.user.username, a.user.is_email_verified, a.user.has_usable_password(), repr(a.user.display_name), sorted(a.extra_data))"
```

**You should see** one line shaped like this (your own handle):

```text
ada True False '' ['email', 'email_verified', 'sub']
```

That reads: the generated handle, email verified, **no usable password** (a Google-only account; it can
still set one with "Forgot password?"), a blank display name, and only these Google claims kept
(`hd` appears too for a Workspace address). Your name and picture are not stored.

Finally, log in again: open http://localhost:3000/login, click **Continue with Google** and choose the
same account. You land on /home again, and no second account was made:

```bash
python manage.py shell -c "from allauth.socialaccount.models import SocialAccount; from apps.accounts.models import User; print(SocialAccount.objects.count(), User.objects.count())"
```

The two numbers are the same as before the second login.

**If it differs:** a red banner under the heading says what happened:
"Google sign-in didn't work. Try again." (the server refused the token: see below),
"Your Google account's email address isn't verified…", or "Too many attempts…" (the 30-a-minute limit).
For "didn't work", `runserver` only logs a `Bad Request: …/provider/token` line, so check, in order: that
`GOOGLE_OAUTH_CLIENT_ID` in `backend/.env` and `NEXT_PUBLIC_GOOGLE_CLIENT_ID` in `frontend/.env.local`
are the **same** value (a mismatch makes window 1 print the WARNING from step 5); that the computer's
clock is right (`timedatectl` should say `System clock synchronized: yes`: a clock that is even a
little behind Google's makes the token "issued in the future" and is refused); that `runserver` was
restarted after you edited `backend/.env`; and that the dev server was restarted after you edited
`frontend/.env.local`.

#### Step 8: Google with an address that already has an account (manual, needs a Gmail address)

**Where:** Browser, then window 2.

**What this does:** Checks that a Google sign-in lands in the **same** account as an email and
password sign-up with the same Gmail address, and that the password is locked, which is how someone who
signed up with *your* address without owning it is locked out. The agent could not run this step.

Use a Gmail (`@gmail.com`) address that has no account here yet. If you already used yours in step 7,
use a second Google account, or first delete that user in Django Admin
(http://localhost:8000/admin/accounts/user/, which also deletes its Google link).

1. Open http://localhost:3000/signup and make an **email and password** account with that Gmail
   address (any username and password; Turnstile uses the test key). You land on /verify-email. **Do
   not open the email link**: the account must stay unverified.
2. Log out, open http://localhost:3000/login and click **Continue with Google**, choosing that Gmail
   account.
3. You land on /home logged in, as the **username you chose in step 1** (not a generated one), and the
   "Verify your email" banner is gone.
4. Log out and try the **password** you chose in step 1 on /login: it says "That email and password
   don't match." Google proved you own the address, so the unverified account's password was wiped. To
   get a password back use **Forgot password?** (the link goes to your real inbox).

Check it in window 2:

```bash
python manage.py shell -c "from allauth.socialaccount.models import SocialAccount; a = SocialAccount.objects.filter(provider='google').select_related('user').order_by('-date_joined').first(); print(a.user.username, a.user.is_email_verified, a.user.has_usable_password())"
```

**You should see** the username from step 1, then `True False`.

- Two more rules (`docs/ARCHITECTURE.md` §7; both covered by step 2's tests):
  - Only addresses Google itself hosts link to an existing account: `@gmail.com`, or a Google
    Workspace domain. Any other address (say `you@example.org`) that matches an existing account gets
    "An account with this email already exists. Log in with your password.", because Google can't
    vouch for who owns such an address today. A *new* person with that address can still sign up.
  - **Staff accounts** (moderators and superusers) are never linked by email: "Staff accounts log in
    with their password." If your own superuser has a Gmail address you can see this: click
    Continue with Google with it and expect the red banner.

#### Step 9: Stop and clean up

**Where:** Every terminal window, plus the browser.

- Stop the servers: `Ctrl+C` in windows 1 and 3 (leftover `next dev`: step 12 of Part 1).
- The accounts from steps 7 and 8, and any `part…`/E2E ones, stay in your local database. Delete the
  Google ones in Django Admin → **Users** (their Google links go with them; **Social accounts** lists
  them). Nothing else was created: Part 3 stores no tokens and no Google profile data.
- `docker compose down` (repo root) stops the containers and keeps the data; `docker compose down -v`
  wipes the whole local database, which is destructive.
- Real Google data never goes into git: the client ID stays in your own `.env` files (it is public by
  design), and there is no client secret anywhere.

### Part 4: Posts (composer + Recent feed)

Needs Part 0A's containers and virtualenv, Part 0C's frontend, and your own `backend/.env` and
`frontend/.env.local`. Part 4 adds one migration (`posts.0001_initial`), one pinned dependency
(`idna==3.20`, which was already installed through `requests`, so `pip install` says "Requirement
already satisfied") and no env variable.

**Which terminal window for what.** Open the windows once and keep using the same ones:

| Window | What runs in it | Used in steps |
|---|---|---|
| Window 1 (server) | `python manage.py runserver` in `backend/`, venv active. Leave it running. Start it in step 4, **after** step 3 (Playwright starts its own servers and needs ports 3000 and 8000 free). | 4 to 14 |
| Window 2 (commands) | All the `curl` and `python manage.py` commands. **Use the same window for steps 4 to 9**: the variables and functions you set in step 4 (`id`, `h`, `ada`, `bo`, `api`, `post`) only live in that one terminal. If you close it, redo step 4. | 1 to 11, 15 |
| Window 3 (frontend) | `npm run dev` in `frontend/`. Leave it running. | 13 and 14 |
| Browser | Steps 12 to 14 | 12 to 14 |

Things to know first:

- Steps 4 to 10 talk to the API directly with `curl` (they need `jq`: `sudo apt install jq`). Steps 12
  to 14 use the browser. Step 4 makes three accounts: `ada` for the API steps (step 8 uses up her whole fact
  allowance), `bo` (unverified) and `cy`, who stays untouched for the browser steps.
- The API outputs below were recorded on Linux on 2026-10-08. The browser steps were checked the same
  day with headless Chromium (screenshots at 1280 and 390 px), not by a person at a keyboard. Numbers in
  names, times and token prefixes differ on every run.
- **The fact allowance comes from your own settings.** `FACT_POSTS_PER_DAY` in `backend/.env` (the
  example file says 10) seeds it, and Django Admin → Platform settings changes it. Step 8 reads the
  number from the server, so it works with any value of 1 or more; the sample output uses 10. It is a
  **rolling 24 hours**, not a calendar day.
- A post is limited to 30 per hour per account (`post_create`). Steps 5 to 9 use about 25 of them
  (refused attempts count). If you repeat steps 6 to 8 within an hour, make new accounts (step 4 again)
  or you will see `429 throttled` instead.
- Nothing here sends an email: step 4 marks one account verified with a shell command, which stands in
  for clicking the link (Part 2 shows the real flow).

#### Step 1: Apply the migration and check the schema

**Where:** Terminal window 2 (commands), starting in the repo root.

**What this does:** Starts the database containers, activates the Python environment, installs what
`requirements.txt` pins, creates the `posts` table and counts its database rules.

```bash
# start in the repo root
docker compose up -d
cd backend
source .venv/bin/activate
pip install -r requirements-dev.txt 2>&1 | grep idna       # Requirement already satisfied: idna==3.20 …
python manage.py migrate                                   # first time: "Applying posts.0001_initial... OK"
python manage.py check                                     # System check identified no issues (0 silenced).
python manage.py makemigrations --check --dry-run          # No changes detected
python manage.py showmigrations posts
python manage.py shell -c "from django.db import connection as c; cur = c.cursor(); k = c.introspection.get_constraints(cur, 'posts_post'); print(len([n for n, v in k.items() if v['check']]), 'checks;', sorted(n for n in k if n.endswith('_idx')))" | tail -1
```

**You should see:** the first `migrate` after pulling Part 4 prints `Applying posts.0001_initial... OK`
(a database that already has it says `No migrations to apply.`). The two checks print their messages,
`showmigrations` prints `[X] 0001_initial`, and the last line is:

```text
19 checks; ['posts_author_created_idx', 'posts_pending_queue_idx', 'posts_pinned_emerg_idx', 'posts_recent_idx', 'posts_review_queue_idx', 'posts_status_created_idx']
```

- The 19 checks are our 17 rules (content length, every status and type, "an opinion can't carry a
  fact status", "a fact can't be `published`", at most 5 sources, no sources on an opinion, no empty or
  NULL source, no emergency opinion, the emergency expiry, the confidence range) plus Django's own two
  "not negative" checks on the two counters.
- `posts_recent_idx` is the one index that is not in the original data model: Recent lists every status
  except `removed`, which `(status, created_at)` can't serve.

#### Step 2: Run the automated backend checks

**Where:** Same terminal as step 1 (window 2, in `backend/`, venv active).

**What this does:** Runs the whole backend test suite, then only the new posts tests, then the linter and
formatter check.

```bash
python -m pytest                                    # 1087 passed
python -m pytest apps/posts -q                      # 383 passed
ruff check . ; ruff format --check .                # All checks passed! / 103 files already formatted
```

**You should see:** the full run ends with `1087 passed`, the second command with `383 passed`, and the
last prints `All checks passed!` and `103 files already formatted`. (Counts may grow later; what matters
is that nothing fails.)

- The 383 are spread over: `test_models.py` (69: one test per database rule, which constraint fired,
  and the indexes), `test_validators.py` (195: the shared source vectors plus the codes and messages),
  `test_services.py` (24: status by type, the rolling quota to the microsecond, and two simultaneous
  fact posts at 9 of 10, which let exactly one through, plus a control run without the lock that lets
  both through), `test_api_create.py` (41), `test_api_feed.py` (25: ordering, exclusions, no repeats or
  skips when posts arrive between pages, a crafted cursor, query counts), `test_api_quota.py` (7),
  `test_emergency.py` (14), `test_no_network.py` (4) and `test_admin.py` (4).
- `apps/accounts/tests/test_tokens.py` changed too: its `run_together` helper moved to that folder's
  `conftest.py` so the posts tests can share it.

#### Step 3: Run the automated frontend checks

**Where:** Terminal window 2, then `cd ../frontend`. Playwright (the last two commands) starts Django and
Next itself, so **no servers may be running on ports 3000 and 8000** (it reuses them if they are, with
whatever settings they have).

**What this does:** Runs the linters, the type check, the component tests, the production build and the
end-to-end tests.

```bash
cd ../frontend                                      # from backend/
npm run lint ; npm run lint:tokens ; npm run typecheck ; npm run format:check
npm test                                            # 80 files, 1089 tests passed
NEXT_PUBLIC_GOOGLE_CLIENT_ID= npm run build
npm run test:e2e                                    # 20 passed
CI=1 npm run test:e2e                               # 20 passed (against the production build)
cd ../backend                                       # back to backend/ for steps 4 to 11
```

**You should see:** the first line prints nothing from ESLint and TypeScript and ends with
`lint:tokens OK (…)` and `All matched files use Prettier code style!`. `npm test` ends with
`Test Files  80 passed (80)` and `Tests  1089 passed (1089)`. `npm run build` lists the routes as in Part 3
(`/home` is still `○`: the page is static, and the feed loads in the browser). Each E2E run ends with
`20 passed`: the 15 earlier tests and 5 new ones in `e2e/posts.spec.ts`.

- The E2E tests sign up their own accounts and verify them through the file mailbox, then: post a fact
  with a DOI and a URL (CHECKING FACTS… and "doi.org/… +1 more", the allowance down by one, still there
  after a reload and visible to a visitor), post an opinion (OPINION in italic, no source line), check
  that a bad post is blocked on the page before anything is sent, check an unverified account can read but
  not post, and check the composer at phone width.
- `NEXT_PUBLIC_GOOGLE_CLIENT_ID= ` bakes in "no Google" for the production-mode run (as in Part 3).

#### Step 4: Start the server and make two accounts

**Where:** First window 1 (start the server), then window 2 (the commands). **Keep using window 2 for
steps 5 to 9.**

**What this does:** Window 1 runs the Django server. In window 2 you sign up three accounts through the
API: `ada` and `cy`, which you mark verified with a shell command (it stands in for the email link), and
`bo`, who stays unverified.

Window 1 (in `backend/`, venv active):

```bash
python manage.py runserver                          # leave it running
```

Window 2 (in `backend/` with the venv active: steps 1 to 3 leave you there; needs `jq`). If you opened a
new terminal, first run `cd backend` from the repo root and `source .venv/bin/activate`:

```bash
id=$(date +%H%M%S)                                  # a unique suffix so the addresses are new each run
h=(-H 'Origin: http://localhost:3000' -H 'X-Requested-With: rumor-zero')   # headers every auth call needs
signup() { jq -nc --arg e "$1" --arg u "$2" '{email: $e, username: $u, password: "correct-horse-battery-42", turnstile_token: "XXXX.DUMMY.TOKEN.XXXX"}' | curl -s "${h[@]}" -H "Content-Type: application/json" --data-binary @- http://localhost:8000/api/auth/app/v1/auth/signup | jq -r .meta.access_token; }
ada=$(signup "part4-ada-$id@example.test" "part4_ada_$id")      # $ada = ada's login token
bo=$(signup "part4-bo-$id@example.test" "part4_bo_$id")         # $bo = bo's login token
cy=$(signup "part4-cy-$id@example.test" "part4_cy_$id")         # $cy = cy's login token (kept for the browser)
python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(email__in=['part4-ada-$id@example.test', 'part4-cy-$id@example.test']).update(is_email_verified=True), 'accounts marked verified')" | tail -1
for t in "$ada" "$bo" "$cy"; do curl -s -H "Authorization: Bearer $t" http://localhost:8000/api/v1/me/ | jq -c '{username, is_email_verified}'; done
api=http://localhost:8000/api/v1
post() { local out; out=$(curl -s -w '\n%{http_code}' -H "Authorization: Bearer $1" -H "Content-Type: application/json" --data-binary "$2" $api/posts/); printf '%s  ' "${out##*$'\n'}"; printf '%s' "${out%$'\n'*}" | jq -c "${3:-.}"; }   # post <token> <json> [jq filter]: prints the status code, then the answer
```

Sanity check (this step sets `id`, `ada`, `bo`, `cy`, `api` and `post`; the tokens must not be empty):

```bash
echo ${ada:0:10} ${bo:0:10} ${cy:0:10}               # three prefixes, not an empty line
```

**You should see** (the number in the names is your `id`, so it differs):

```text
2 accounts marked verified
{"username":"part4_ada_235103","is_email_verified":true}
{"username":"part4_bo_235103","is_email_verified":false}
{"username":"part4_cy_235103","is_email_verified":true}
```

and, from the sanity check, `eyJhbGciOi eyJhbGciOi eyJhbGciOi` (every token of this kind starts that way).

- `post` is a helper for the next steps: it sends a JSON body with a login token, prints the HTTP status,
  then the answer (optionally cut down with a `jq` filter).
- The shell prints a line about auto-imported objects first; `tail -1` keeps only ours.
- Sign-up is limited to 20 a minute per address (Part 1), and still calls Cloudflare's test widget, so it
  needs internet.

**If it differs:** empty tokens (`null`) mean the sign-up failed: `runserver` isn't running, `jq` is
missing, or you signed up more than 20 times in a minute. Fix that and run this step again from
`id=$(date +%H%M%S)`.

#### Step 5: Who may post

**Where:** Terminal window 2 (the same terminal as step 4).

**What this does:** Tries to post as nobody, as the unverified account, and reads the feed with no login.
Posting needs a **verified email**; reading doesn't.

```bash
curl -s -w '  %{http_code}\n' -H "Content-Type: application/json" --data '{"content":"hi","post_type":"opinion"}' $api/posts/   # 1: nobody
post "$bo" '{"content":"hi","post_type":"opinion"}'                                                                   # 2: unverified
curl -s -o /dev/null -w '%{http_code}\n' $api/posts/                                                                  # 3: the feed, no login
curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $bo" $api/me/fact-quota/                           # 4: the allowance, unverified
```

**You should see** (four commands, four answers):

```text
{"detail":"Authentication credentials were not provided.","code":"not_authenticated"}  401
403  {"detail":"Verify your email address first. Check your inbox for the link.","code":"email_unverified"}
200
200
```

- 401 means "log in first", 403 `email_unverified` means "logged in but not verified". Reading the feed
  needs nothing. Asking for your allowance needs a login only, so the composer can show it.

#### Step 6: Post an opinion and a fact

**Where:** Terminal window 2.

**What this does:** Posts as `ada` (verified) and shows what the server stored. An opinion is
`published` at once; a fact is `pending` ("Checking facts…") because the fact-check pipeline arrives in
Part 9. Sources are normalised, never fetched.

```bash
post "$ada" '{"content":"I think the new tram line will change how the city moves.","post_type":"opinion"}' '{status, post_type, sources, is_mine, confidence_score, emergency_active}'
post "$ada" '{"content":"Solar capacity grew by roughly 30% worldwide last year.","post_type":"fact","sources":["doi:10.1038/s41558-024-02102","HTTPS://www.IEA.org/reports/renewables-2023"]}' '{status, post_type, sources, author: .author.username}'
post "$ada" '{"content":"  Water boils at 100C at sea level.  ","post_type":"fact"}' '{status, content, sources}'
post "$ada" '{"content":"Opinion with a bad idea","post_type":"opinion","status":"verified_true","confidence_score":"99.00"}' '{status, confidence_score}'
post "$ada" '{"content":"Hosts are folded to punycode","post_type":"fact","sources":["https://bücher.example/über?q=1","https://faß.de:443/x"]}' '.sources'
```

**You should see** (five commands; `201` is "created"):

```text
201  {"status":"published","post_type":"opinion","sources":[],"is_mine":true,"confidence_score":null,"emergency_active":false}
201  {"status":"pending","post_type":"fact","sources":[{"value":"10.1038/s41558-024-02102","kind":"doi"},{"value":"https://www.iea.org/reports/renewables-2023","kind":"url"}],"author":"part4_ada_235103"}
201  {"status":"pending","content":"Water boils at 100C at sea level.","sources":[]}
201  {"status":"published","confidence_score":null}
201  [{"value":"https://xn--bcher-kva.example/%C3%BCber?q=1","kind":"url"},{"value":"https://xn--fa-hia.de/x","kind":"url"}]
```

- **Line 2:** `doi:10.1038/…` is stored as the bare DOI `10.1038/s41558-024-02102` with kind `doi`; the second
  source's scheme and host are lower-cased (`HTTPS://www.IEA.org/…` → `https://www.iea.org/…`). The
  order you gave is the order kept.
- **Line 3:** the text is trimmed. A fact with no sources is fine (sources are optional).
- **Line 4:** `status` and `confidence_score` in the request are ignored: only the server sets them.
- **Line 5:** `bücher.example` and `faß.de` become punycode, the way a browser opens them (`faß.de` is
  `xn--fa-hia.de`, not the `fass.de` of the old IDNA 2003 rules), the `ü` in the path is percent-encoded,
  and the default port `:443` is dropped.
- No source is ever visited by the server. Step 11 runs the test that blocks the network to prove it.

#### Step 7: See what the server refuses

**Where:** Terminal window 2.

**What this does:** Sends eight bad posts. Each answer says which field is wrong; nothing is saved.

```bash
post "$ada" '{"content":"No type"}'
post "$ada" '{"content":"   ","post_type":"opinion"}'
post "$ada" "$(jq -nc '{content: ("x" * 501), post_type: "opinion"}')"
post "$ada" '{"content":"Only facts have sources","post_type":"opinion","sources":["10.1000/xyz"]}'
post "$ada" '{"content":"Bad sources","post_type":"fact","sources":["10.1000/ok","javascript:alert(1)","http://127.0.0.1/admin","https://user:pw@example.org/"]}'
post "$ada" '{"content":"Repeats","post_type":"fact","sources":["doi:10.1000/xyz","https://doi.org/10.1000/XYZ"]}'
post "$ada" '{"content":"Too many","post_type":"fact","sources":["10.1000/a","10.1000/b","10.1000/c","10.1000/d","10.1000/e","javascript:x"]}'
post "$ada" '{"content":"Emergency","post_type":"fact","is_emergency":true}'
```

**You should see** (eight commands, eight answers, all `400`):

```text
400  {"post_type":["Choose Opinion or Fact."]}
400  {"content":["Write something first."]}
400  {"content":["Keep it to 500 characters."]}
400  {"sources":["Only fact posts can have sources."]}
400  {"sources":{"1":["Enter a link that starts with https:// or http://, or a DOI such as 10.1000/xyz."],"2":["Links to IP addresses and localhost aren't allowed."],"3":["Links with a username or password aren't allowed."]}}
400  {"sources":{"1":["Same as source 1."]}}
400  {"sources":["You can add up to 5 sources."]}
400  {"detail":"Emergency posts aren't available yet.","code":"emergency_unavailable"}
```

- **Line 5:** the numbers are the position in your list (0 is the first): sources 1, 2 and 3 are wrong,
  all reported at once, and the good first one doesn't save the post.
- **Line 6:** `doi:10.1000/xyz` and `https://doi.org/10.1000/XYZ` are the same DOI (DOIs ignore case), so the
  later one is the repeat.
- **Line 7:** six sources are refused with only the list message, even though one of them is also bad.
- **Line 8:** emergency posts are Part 11C; until then the flag is refused.

#### Step 8: The fact allowance

**Where:** Terminal window 2.

**What this does:** Reads how many fact posts `ada` may still make in the last 24 hours, uses them all,
and shows the refusal. Each fact post counts for 24 hours, even if it is deleted or removed later, so
deleting and reposting can't get around the limit. Opinions never count.

```bash
curl -s -H "Authorization: Bearer $ada" $api/me/fact-quota/ | jq -c .
left=$(curl -s -H "Authorization: Bearer $ada" $api/me/fact-quota/ | jq .remaining)
echo "posting $left more facts"
for i in $(seq 1 $left); do post "$ada" "{\"content\":\"Quota claim $i\",\"post_type\":\"fact\"}" '.status' | tr '\n' ' '; done; echo
curl -s -H "Authorization: Bearer $ada" $api/me/fact-quota/ | jq -c .
curl -s -i -H "Authorization: Bearer $ada" -H "Content-Type: application/json" --data '{"content":"One too many","post_type":"fact"}' $api/posts/ | tr -d '\r' | grep -i -E "^HTTP|^Retry-After|^\{"
post "$ada" '{"content":"Opinions are not limited","post_type":"opinion"}' '.status'
```

**You should see** (with a limit of 10; the times and `Retry-After` differ):

```text
{"limit":10,"used":3,"remaining":7,"window_hours":24,"next_slot_at":null}
posting 7 more facts
201  "pending" 201  "pending" 201  "pending" 201  "pending" 201  "pending" 201  "pending" 201  "pending" 
{"limit":10,"used":10,"remaining":0,"window_hours":24,"next_slot_at":"2026-10-09T17:51:04.118320Z"}
HTTP/1.1 429 Too Many Requests
Retry-After: 86382
{"detail":"You've used all 10 of your fact posts for the last 24 hours. You can post another at 17:51 UTC.","code":"fact_quota_exceeded"}
201  "published"
```

- `used` was 3 because steps 6 and 7 made three fact posts. When nothing is left, `next_slot_at` is the
  moment the oldest counted post is 24 hours old: the composer shows it as "next at 5:51 PM" in your own
  time zone.
- The refusal is **429 `fact_quota_exceeded`** with a `Retry-After` in seconds (about 24 hours here). It
  is a different 429 from `throttled`, so the page can tell "you've used your allowance" from "you're
  posting too fast". An allowance of 0 (Django Admin → Platform settings) answers **403
  `fact_posts_paused`** instead.

#### Step 9: The Recent feed and its cursor

**Where:** Terminal window 2.

**What this does:** Reads the public feed (no login), pages through it three posts at a time and tries a
fake cursor.

```bash
curl -s "$api/posts/?page_size=3" | jq -c '{pinned, pinned_total, kinds: [.results[].kind], contents: [.results[].post.content[0:28]], has_next: (.next_cursor != null)}'
c=$(curl -s "$api/posts/?page_size=3" | jq -r .next_cursor)
curl -s "$api/posts/?page_size=3&cursor=$c" | jq -c '{contents: [.results[].post.content[0:28]], has_next: (.next_cursor != null)}'
curl -s -w '  %{http_code}\n' "$api/posts/?cursor=not-a-cursor"
curl -s -w '  %{http_code}\n' "$api/posts/?cursor=cD1nYXJiYWdl"
curl -s -H "Authorization: Bearer $ada" "$api/posts/?page_size=1" | jq -c '.results[0].post | {is_mine, keys: (keys | length)}'
curl -s "$api/posts/?page_size=1" | jq -c '.results[0].post | {is_mine, keys: (keys | length)}'
```

**You should see:**

```text
{"pinned":[],"pinned_total":0,"kinds":["post","post","post"],"contents":["Opinions are not limited","Quota claim 7","Quota claim 6"],"has_next":true}
{"contents":["Quota claim 5","Quota claim 4","Quota claim 3"],"has_next":true}
{"detail":"Invalid cursor","code":"not_found"}  404
{"detail":"Invalid cursor","code":"not_found"}  404
{"is_mine":true,"keys":23}
{"is_mine":false,"keys":23}
```

- Newest first. `pinned` is empty until emergency posts (Part 11C), and Recent only has `post` items
  (reposts are Part 7B).
- The next page starts exactly where the last one ended: a post made between two page loads never
  repeats or skips a post (the automated tests make 5 new posts between pages 1 and 2).
- `cD1nYXJiYWdl` is the base64 of `p=garbage`, a hand-made cursor. It is a clean **404**, not a server
  error.
- Every post has the same 23 fields; `is_mine` depends on who is asking. The feed has no counts yet (likes,
  comments and reposts arrive in Parts 7 and 7B), so those fields are 0 or false.

#### Step 10: The database refuses bad rows

**Where:** Terminal window 2, in `backend/` with the venv active.

**What this does:** Tries to write six impossible posts straight into the database, skipping the API.
The database itself must refuse each one, and say which rule stopped it. Every attempt is rolled back.

```bash
python manage.py shell -c "
from django.db import IntegrityError, transaction
from django.utils import timezone
from apps.accounts.models import User
from apps.posts.models import Post
user = User.objects.get(email='part4-ada-$id@example.test')
cases = {
    'an opinion with a source': dict(post_type='opinion', status='published', sources=['10.1000/xyz']),
    'an opinion that is verified': dict(post_type='opinion', status='verified_true'),
    'a published fact': dict(post_type='fact', status='published'),
    'six sources': dict(post_type='fact', status='pending', sources=['10.1/a','10.1/b','10.1/c','10.1/d','10.1/e','10.1/f']),
    'an empty source': dict(post_type='fact', status='pending', sources=['']),
    'an emergency opinion': dict(post_type='opinion', status='published', is_emergency=True, emergency_expires_at=timezone.now()),
}
for name, fields in cases.items():
    try:
        with transaction.atomic():
            Post.objects.create(author=user, content='x', **fields)
    except IntegrityError as error:
        print(name + ' ->', error.__cause__.diag.constraint_name)
print(Post.objects.filter(content='x').count(), 'rows written')
" | tail -7
```

**You should see:**

```text
an opinion with a source -> posts_post_sources_fact_only
an opinion that is verified -> posts_post_opinion_status
a published fact -> posts_post_fact_not_published
six sources -> posts_post_sources_max
an empty source -> posts_post_sources_not_empty
an emergency opinion -> posts_post_emergency_fact_only
0 rows written
```

- Each line is the name of the database rule that fired. `0 rows written` confirms nothing got through.
- One more rule the database can't state: a source over 500 characters. Postgres would *truncate* it
  silently through Django's cast, so `validators.normalize_source` refuses it first (step 7's tests cover
  499, 500 and 501 characters).

#### Step 11: No source is ever fetched

**Where:** Terminal window 2, in `backend/` with the venv active.

**What this does:** Runs the test that blocks every way Python can reach the network (sockets, DNS,
`urllib`, `requests`, `http.client`), then posts a fact with five kinds of source. It must still work,
because the server only validates and stores a link.

```bash
python -m pytest apps/posts/tests/test_no_network.py -v 2>&1 | grep -E "PASSED|passed|FAILED"
```

**You should see:**

```text
apps/posts/tests/test_no_network.py::test_creating_a_post_with_sources_makes_no_network_request PASSED [ 25%]
apps/posts/tests/test_no_network.py::test_a_refused_source_makes_no_request_either PASSED [ 50%]
apps/posts/tests/test_no_network.py::test_the_blocker_really_blocks PASSED [ 75%]
apps/posts/tests/test_no_network.py::test_the_posts_code_imports_nothing_that_can_fetch PASSED [100%]
============================== 4 passed in 0.41s ===============================
```

- The last test also reads every file in `apps/posts/` and fails if one imports a library that can fetch.
  This is what keeps a user's link from ever becoming a request from our server.

#### Step 12: Django Admin shows the posts, read-only

**Where:** Browser, while `runserver` is running in window 1.

**What this does:** Opens the admin list of posts. Part 10 adds the moderator actions; until then nobody can
change a post from here, so nothing can skip the rules the API enforces.

| URL | Expect |
|---|---|
| http://localhost:8000/admin/ | Sign in with the superuser you made in Part 0A (email and password). If it 404s, `ADMIN_URL_PATH` in `backend/.env` isn't `admin/`; use that path. |
| http://localhost:8000/admin/posts/post/ | The posts, newest first, with columns Post, Post type, Status, Author, Created at and Deleted at, a filter panel (type, status) and a search box (text or username). **No "Add post" button.** |
| Search `tram` or `Quota` | Only the matching posts (the opinion about the tram line, or the seven "Quota claim" facts) |
| Open one post | Its fields are shown but not editable, and there are no Save buttons or Delete button |

- The same rules are checked by the automated tests (add, change and delete are refused with 403).

#### Step 13: The composer and the Recent feed in the browser

**Where:** First window 3 (start the frontend), then the browser. Window 1 must still be running `runserver`.

**What this does:** Starts the Next.js dev server and uses the composer as `cy` (verified, with a full
allowance) and `bo` (unverified).

Window 3:

```bash
cd frontend                                         # from the repo root
npm run dev                                         # leave it running
```

Browser. Log in at http://localhost:3000/login as **`cy`**, with `part4-cy-<your id>@example.test` and
`correct-horse-battery-42` (the id from step 4), then:

| Do this | Expect |
|---|---|
| Open http://localhost:3000/home | A white column titled by the **RECENT** tab (blue underline), then a card that looks like a text box: a pencil tile, "What do you want to say?" and a blue **New post** pill. Below it, the posts from steps 6 to 9, newest first. |
| Look at a fact card | A grey **FACT** chip and a dashed **CHECKING FACTS…** chip with a spinning glyph, the claim in upright serif, and under it one row with a link glyph: `doi.org/10.1038/s41558-024-02102 ↗` and `+1 more`. The left edge stripe is a pale grey-green. |
| Look at an opinion card | A grey **OPINION** chip only (no status chip), the text in *italic* serif, and no source row. |
| Click the card (or the rail's blue **New post**) | A dialog **New post** with the cursor in the text. Under the text: `0 / 500 characters`. Then "Post type  Choose one to continue", a pill with **Opinion** and **Fact** (neither selected), and a footer: `10/10 fact posts left` (your limit), **Cancel** and **Post**. |
| Click **Post** with nothing typed | Nothing is sent. Under the text: "Write something first." Under the choice: "Choose Opinion or Fact." The cursor goes back to the text. |
| Type a sentence and click **Fact** | A **Source (URL or DOI) (optional)** group appears with one field, "DOI preferred" (teal, top right) and **+ Add another source**. The button now says **Post fact, will be checked**. The hint beside "Post type" says "Fact posts are checked after you post". |
| Click **Opinion** | The source group disappears (your text stays) and the button says **Post opinion**. Click **Fact** again. |
| Type `http://127.0.0.1/admin` in the field and press Tab | The field turns red: "Links to IP addresses and localhost aren't allowed." |
| Replace it with `doi:10.1000/xyz`, click **Add another source** | The error goes; a second field appears with the cursor in it and a **×** to its right. Add up to five fields in total, then the add button disappears. |
| Type `https://doi.org/10.1000/XYZ` in the second field and click **Post fact…** | The second field turns red: "Same as source 1." Nothing is sent. Change it to `https://example.org/report`. |
| Click **Post fact, will be checked** | The button shows **Posting…**, then the dialog closes, a dark toast says **Posted. Checking the facts…**, and your post is at the top of the feed with **CHECKING FACTS…** and `doi.org/10.1000/xyz` `+1 more`. The page did not reload. |
| Open the composer again | The text is empty again, and the footer says one fact post fewer (`9/10 …`). |
| Type something, press **Esc**, open the composer again | Your text is still there: closing keeps the draft. |
| Reload the page | The posts come back from the server, in the same order. |

- Not in the table, but covered by the automated tests: pasting more than 500 characters (the counter turns
  red and "Keep it to 500 characters." appears on **Post**; an emoji counts as one character, as on the
  server), the allowance reaching 0 (the footer shows `0/10 fact posts left · next at 5:51 PM` and a fact is
  refused on the page without sending anything; `ada`, whose allowance step 8 used up, shows exactly
  that), and closing the dialog while a post is still being sent.
- Log in as `bo` (a private window): the card and the rail's **New post** are greyed out; clicking either
  shows the toast "Verify your email to post. Check your inbox, or resend the link from the banner." and
  opens nothing. The feed still loads.
- Log out and open http://localhost:3000/home: the card says "Log in to share an opinion or a fact." with a
  blue **Log in to post** link, and the feed is the same.

#### Step 14: A phone-sized window

**Where:** Browser, logged in as `cy`.

**What this does:** Checks the same screens at phone width. In Firefox or Chrome press `F12`, then the
"responsive design" / device toolbar button, and set the width to 390.

| Do this | Expect |
|---|---|
| Open http://localhost:3000/home | A top bar with the logo and your avatar, the Recent tab, the card (placeholder "What do you want to say?" in full, no blue pill), the posts and a bottom bar (Home, Search, New post, Notifications, Profile). No sideways scrolling. |
| Look at a post's header | The author's name sits on one line (long names get "…"); the FACT and status chips wrap onto a line of their own under it. |
| Tap **New post** in the bottom bar | The same dialog, almost full width. Pick **Fact**, add sources up to five: each row keeps its **×**, long links scroll inside their field, and the page still doesn't scroll sideways. |
| Look at the footer | `9/10 fact posts left` (or `10/10` if you haven't posted yet) on its own line, with **Cancel** and the submit button below it (the long label may wrap onto two lines). |

#### Step 15: Stop and clean up

**Where:** Every terminal window, plus the browser.

- Stop the servers: `Ctrl+C` in windows 1 and 3 (a leftover `next dev`: step 12 of Part 1).
- Delete the test accounts and their posts (the posts go with them). In window 2, in `backend/` with the
  venv active:

  ```bash
  python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(email__startswith='part4-').delete())" | tail -1
  ```

  After one clean run of this guide it prints `(19, {'posts.Post': 13, 'account.EmailAddress': 3,
  'accounts.User': 3})`: how many rows went in all, and per table (13 posts: 5 from step 6 and 8 from step 8;
  you get more if you made posts as `cy` or ran the guide twice). Nothing else is touched. (The E2E tests' accounts stay in your local database, as in
  earlier parts: Django Admin → Users deletes them.)
- `docker compose down` (repo root) stops the containers and keeps the data; `docker compose down -v`
  wipes the whole local database, which is destructive.
- No secret was used or printed in this part: the only values in the commands are Cloudflare's public test
  token and the throwaway password of the test accounts.

### Part 5: Post detail, sharing, deletion, status polling

Needs Part 0A's containers and virtualenv, Part 0C's frontend, and your own `backend/.env` and
`frontend/.env.local`. Part 5 adds **no migration, no dependency and no env variable**. It adds one throttle
scope (`status_poll`, in code) and three endpoints: `GET` and `DELETE /api/v1/posts/{id}/` and
`GET /api/v1/posts/status/`.

**Which terminal window for what.** Open the windows once and keep using the same ones:

| Window | What runs in it | Used in steps |
|---|---|---|
| Window 1 (server) | `python manage.py runserver` in `backend/`, venv active. Leave it running. Start it in step 3, **after** step 2 (Playwright starts its own servers and needs ports 3000 and 8000 free). | 3 to 13 |
| Window 2 (commands) | All the `curl` and `python manage.py` commands. **Use the same window for steps 3 to 9**: the variables and functions you set in step 3 (`id`, `h`, `ada`, `bo`, `cy`, `api`, `mk`, `get`, `fact`, `op`) only live in that one terminal. If you close it, redo step 3. | 1 to 10, 14 |
| Window 3 (frontend) | `npm run dev` in `frontend/`. Leave it running. | 9 to 13 |
| Browser | Steps 10 to 13 | 10 to 13 |

Things to know first:

- Steps 3 to 9 talk to the API directly with `curl` (they need `jq`: `sudo apt install jq`). Steps 10 to 13 use
  the browser. Step 3 makes three accounts, all verified: `ada` writes the posts, `bo` is "another user", and
  `cy` stays untouched for the browser steps.
- The API and page outputs below were recorded on Linux on 2026-10-09. The browser steps were checked the same
  day with headless Chromium (screenshots at 1280 and 390 px), not by a person at a keyboard. Ids, numbers in
  names, times and token prefixes differ on every run.
- Nothing here sends an email: step 3 marks the accounts verified with a shell command, which stands in for
  clicking the link (Part 2 shows the real flow). Step 7 sets a post to `removed` the same way, because the
  moderator tools that do it for real arrive in Part 10.
- **Part 5 doesn't change any post's text or sources**; a post can only be deleted by its author, and "deleted"
  only hides it (the row stays, so a moderator can still find it).

#### Step 1: Run the automated backend checks

**Where:** Terminal window 2 (commands), starting in the repo root.

**What this does:** Starts the database containers, activates the Python environment, confirms there is no
new migration, then runs the whole backend test suite, the new posts tests, the linter and the formatter check.

```bash
# start in the repo root
docker compose up -d
cd backend
source .venv/bin/activate
python manage.py makemigrations --check --dry-run   # No changes detected
python manage.py check                              # System check identified no issues (0 silenced).
python -m pytest                                    # 1160 passed
python -m pytest apps/posts -q                      # 456 passed
ruff check . ; ruff format --check .                # All checks passed! / 106 files already formatted
```

**You should see:** `No changes detected` and `System check identified no issues (0 silenced).`, then the full
run ends with `1160 passed`, the posts run with `456 passed`, and the last line pair is `All checks passed!` and
`106 files already formatted`. (Counts may grow later; what matters is that nothing fails.)

- The 73 new posts tests: `test_api_detail.py` (33: who sees what in every status, the removed tombstone, 404s,
  query counts), `test_api_delete.py` (22: permissions, soft delete, two simultaneous deletes give one success
  and one 404, the row lock), `test_api_status.py` (17: the four-key shape, the 50-id cap, one query for 50
  posts, the 120-a-minute throttle) and one more in `test_models.py` (`not_deleted()`).
- `apps/core/tests/test_settings.py` now expects eleven throttle scopes (`status_poll` is the new one).

#### Step 2: Run the automated frontend checks

**Where:** Terminal window 2, then `cd ../frontend`. Playwright (the last two commands) starts Django and
Next itself, so **no servers may be running on ports 3000 and 8000** (it reuses them if they are, with
whatever settings they have).

**What this does:** Runs the linters, the type check, the component tests, the production build and the
end-to-end tests.

```bash
cd ../frontend                                      # from backend/
npm run lint ; npm run lint:tokens ; npm run typecheck ; npm run format:check
npm test                                            # 91 files, 1210 tests passed
NEXT_PUBLIC_GOOGLE_CLIENT_ID= npm run build
npm run test:e2e                                    # 24 passed
CI=1 npm run test:e2e                               # 24 passed (against the production build)
cd ../backend                                       # back to backend/ for steps 3 to 9
```

**You should see:** the first line prints nothing from ESLint and TypeScript and ends with
`lint:tokens OK (…)` and `All matched files use Prettier code style!`. `npm test` ends with
`Test Files  91 passed (91)` and `Tests  1210 passed (1210)`. `npm run build` lists the routes as in Part 4, plus
`ƒ /p/[id]` (dynamic: it is rendered on the server for each post). Each E2E run ends with `24 passed`: the 20
earlier tests and 4 new ones in `e2e/post-detail.spec.ts`.

- The new E2E tests sign up their own accounts, then: open a fact from its card (sources numbered `01`, `02`,
  Copy link, and an anonymous request for `/p/<id>` returning the claim, the `<title>` and the Open Graph tags);
  delete an opinion (gone from Recent, a 404 page and a 404 from the API); watch a pending fact turn into
  `VERIFIED 94%` on the feed and on its own page after a status change made in the database (about 10 to 15
  seconds); and check a removed post (a tombstone for a visitor, the full text for its author).
- One of them is an E2E-only trick worth knowing: `e2e/helpers.ts` changes the status by running `manage.py
  shell` against the same database, exactly as step 12 below does by hand.

#### Step 3: Start the servers and make three accounts and two posts

**Where:** First window 1 (the Django server) and window 3 (the frontend), then window 2 (the commands).
**Keep using window 2 for steps 4 to 9.**

**What this does:** Windows 1 and 3 run the two servers. In window 2 you sign up three accounts through the API
and mark them verified, then `ada` posts a fact with two sources and an opinion. The helpers `mk` (make a post,
print its id) and `get` (print the status code, then the answer) are used by the next steps.

Window 1 (in `backend/`, venv active):

```bash
python manage.py runserver                          # leave it running
```

Window 3:

```bash
cd frontend                                         # from the repo root
npm run dev                                         # leave it running
```

Window 2 (in `backend/` with the venv active: steps 1 and 2 leave you there; needs `jq`). If you opened a new
terminal, first run `cd backend` from the repo root and `source .venv/bin/activate`:

```bash
id=$(date +%H%M%S)                                  # a unique suffix so the addresses are new each run
h=(-H 'Origin: http://localhost:3000' -H 'X-Requested-With: rumor-zero')   # headers every auth call needs
signup() { jq -nc --arg e "$1" --arg u "$2" '{email: $e, username: $u, password: "correct-horse-battery-42", turnstile_token: "XXXX.DUMMY.TOKEN.XXXX"}' | curl -s "${h[@]}" -H "Content-Type: application/json" --data-binary @- http://localhost:8000/api/auth/app/v1/auth/signup | jq -r .meta.access_token; }
ada=$(signup "part5-ada-$id@example.test" "part5_ada_$id")      # $ada = ada's login token (the author)
bo=$(signup "part5-bo-$id@example.test" "part5_bo_$id")         # $bo = bo's login token (another reader)
cy=$(signup "part5-cy-$id@example.test" "part5_cy_$id")         # $cy = cy's login token (kept for the browser)
python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(email__startswith='part5-', email__endswith='$id@example.test').update(is_email_verified=True), 'accounts marked verified')" | tail -1
for t in "$ada" "$bo" "$cy"; do curl -s -H "Authorization: Bearer $t" http://localhost:8000/api/v1/me/ | jq -c '{username, is_email_verified}'; done
api=http://localhost:8000/api/v1
mk() { curl -s -H "Authorization: Bearer $1" -H "Content-Type: application/json" --data-binary "$2" $api/posts/ | jq -r .id; }   # mk <token> <json>: makes a post, prints its id
get() { local out; out=$(curl -s -w '\n%{http_code}' ${2:+-H "Authorization: Bearer $2"} "$api$1"); printf '%s  ' "${out##*$'\n'}"; printf '%s' "${out%$'\n'*}" | jq -c "${3:-.}"; }   # get <path> [token] [jq filter]: prints the status code, then the answer
fact=$(mk "$ada" '{"content":"Solar capacity grew by roughly 30% worldwide last year.","post_type":"fact","sources":["doi:10.1038/s41558-024-02102","https://www.iea.org/reports/renewables-2023"]}')
op=$(mk "$ada" '{"content":"I think the new tram line will change how the city moves.","post_type":"opinion"}')
echo ${ada:0:10} ${bo:0:10} ${cy:0:10}               # three prefixes, not an empty line
echo "fact=$fact"; echo "op=$op"                     # two ids, not empty
```

**You should see** (the number in the names is your `id`, and the ids differ):

```text
3 accounts marked verified
{"username":"part5_ada_190845","is_email_verified":true}
{"username":"part5_bo_190845","is_email_verified":true}
{"username":"part5_cy_190845","is_email_verified":true}
eyJhbGciOi eyJhbGciOi eyJhbGciOi
fact=fb1fc4a4-232f-4d10-830c-d83b343e5b5a
op=d51f9804-6080-4107-bda3-90e1bdd1f27d
```

- The shell prints a line about auto-imported objects first; `tail -1` keeps only ours.
- Sign-up is limited to 20 a minute per address (Part 1), and still calls Cloudflare's test widget, so it
  needs internet.

**If it differs:** an empty token or an `id` of `null` means the sign-up or the post failed: `runserver` isn't
running, `jq` is missing, or you signed up more than 20 times in a minute. Fix that and run this step again
from `id=$(date +%H%M%S)`.

#### Step 4: Read a post

**Where:** Terminal window 2 (the same terminal as step 3).

**What this does:** Reads the post's page data, `GET /api/v1/posts/{id}/`, as nobody, as another user and as
the author. Anyone can read a post; only `is_mine` differs. Then two bad ids.

```bash
get /posts/$fact/ "" '{status, post_type, content, sources: [.sources[].kind], is_mine, verdict_note, confidence_score, keys: (keys | length)}'   # 1: anyone, no login
get /posts/$fact/ "$bo" '{is_mine}'                                                                                                               # 2: another user
get /posts/$fact/ "$ada" '{is_mine}'                                                                                                              # 3: the author
get /posts/$op/ "" '{status, post_type, content, sources, is_mine}'                                                                               # 4: an opinion
get /posts/not-a-post-id/ "" .                                                                                                                    # 5: not an id at all
get /posts/00000000-0000-4000-8000-000000000000/ "" .                                                                                             # 6: no such post
```

**You should see** (six commands, six answers):

```text
200  {"status":"pending","post_type":"fact","content":"Solar capacity grew by roughly 30% worldwide last year.","sources":["doi","url"],"is_mine":false,"verdict_note":"","confidence_score":null,"keys":23}
200  {"is_mine":false}
200  {"is_mine":true}
200  {"status":"published","post_type":"opinion","content":"I think the new tram line will change how the city moves.","sources":[],"is_mine":false}
404  {"detail":"Not found.","code":"not_found"}
404  {"detail":"Not found.","code":"not_found"}
```

- The answer has the same 23 keys as a post in the feed. The sources come with their kind (`doi`, `url`) in the
  order you gave them.
- An id that isn't an id gets the same JSON 404 as an unknown one, never a server error.

#### Step 5: Ask for the live status of several posts

**Where:** Terminal window 2.

**What this does:** Calls `GET /api/v1/posts/status/?ids=…`, the endpoint the badges poll. It is public, takes up
to 50 ids and returns only what a badge needs.

```bash
get "/posts/status/?ids=$fact,$op,00000000-0000-4000-8000-000000000000"            # 1: two real posts and one that doesn't exist
get "/posts/status/?ids=$fact" "not-a-token" '.results | length'                    # 2: a garbage token is simply ignored
get "/posts/status/"                                                                # 3: no ids
get "/posts/status/?ids=nope"                                                       # 4: a malformed id
many=$(python -c "import uuid; print(','.join(str(uuid.uuid4()) for _ in range(51)))")
get "/posts/status/?ids=$many"                                                      # 5: 51 ids
```

**You should see:**

```text
200  {"results":[{"id":"fb1fc4a4-232f-4d10-830c-d83b343e5b5a","status":"pending","confidence_score":null,"verdict_source":null},{"id":"d51f9804-6080-4107-bda3-90e1bdd1f27d","status":"published","confidence_score":null,"verdict_source":null}]}
200  1
400  {"ids":["Send the ids of the posts to check."]}
400  {"ids":["'nope' isn't a post id."]}
400  {"ids":["Check at most 50 posts at a time."]}
```

- Line 1 leaves out the id that doesn't exist; the order is the order you asked in. `confidence_score` is only
  set for a verdict the pipeline made, and `verdict_source` tells who decided.
- Line 2: this endpoint never checks the login, so an expired token can't turn a public read into a 401.
  (`GET /api/v1/posts/{id}/` does check a token it is given, and the page then refreshes and retries.)

#### Step 6: The author deletes a post

**Where:** Terminal window 2.

**What this does:** Tries to delete the opinion as nobody, as another user and as its author, then looks at the
result everywhere. Deleting only hides the post: the row stays in the database.

```bash
curl -s -w '  %{http_code}\n' -X DELETE $api/posts/$op/                                                  # 1: nobody
curl -s -w '  %{http_code}\n' -X DELETE -H "Authorization: Bearer $bo" $api/posts/$op/                    # 2: another user
curl -s -w '  %{http_code}\n' -X DELETE -H "Authorization: Bearer $ada" $api/posts/$op/                   # 3: the author
curl -s -w '  %{http_code}\n' -X DELETE -H "Authorization: Bearer $ada" $api/posts/$op/                   # 4: the author again
get /posts/$op/ "$ada" .                                                                                  # 5: its page, even for the author
curl -s $api/posts/ | jq "[.results[].post.id] | index(\"$op\")"                                          # 6: the feed
python manage.py shell -c "from apps.posts.models import Post; p = Post.objects.get(pk='$op'); print(p.status, p.deleted_at is not None, p.content[:20])" | tail -1   # 7: the database
```

**You should see:**

```text
{"detail":"Authentication credentials were not provided.","code":"not_authenticated"}  401
{"detail":"Only the author can do that.","code":"not_author"}  403
  204
{"detail":"Not found.","code":"not_found"}  404
404  {"detail":"Not found.","code":"not_found"}
null
published True I think the new tram
```

- 204 means done, with no body. Deleting twice is a 404 (the post is already hidden). `null` on line 6 means the
  post isn't in the feed any more.
- Line 7 is the audit trail: the post is still there, still `published`, with `deleted_at` set (`True`).
  Django Admin shows it too (step 10). A deleted fact post still counts toward the author's 24-hour fact
  allowance, so deleting and reposting can't get around it.
- Deleting doesn't use up the `post_create` throttle (30 posts an hour).

#### Step 7: A removed post is a tombstone

**Where:** Terminal window 2, in `backend/` with the venv active.

**What this does:** Makes a third post, then sets it to `removed` straight in the database (what a moderator's
Remove will do in Part 10, with a note kept only for staff). A visitor and another user get the same keys with
the text, sources and note blanked; its author still sees everything.

```bash
fact2=$(mk "$ada" '{"content":"Rain is wet, says the weather office.","post_type":"fact","sources":["10.1000/xyz"]}')
python manage.py shell -c "from apps.posts.models import Post; print(Post.objects.filter(pk='$fact2').update(status='removed', verdict_note='internal'), 'post set to removed')" | tail -1
get /posts/$fact2/ "" '{status, content, sources, verdict_note, author: .author.username, is_mine, keys: (keys | length)}'     # 1: the public
get /posts/$fact2/ "$bo" '{status, content}'                                                                                  # 2: another user
get /posts/$fact2/ "$ada" '{status, content, sources: (.sources | length), verdict_note, is_mine}'                            # 3: the author
get "/posts/status/?ids=$fact2" "" '.results'                                                                                 # 4: the poll
curl -s $api/posts/ | jq "[.results[].post.id] | index(\"$fact2\")"                                                          # 5: the feed
```

**You should see** (the name is your `id`):

```text
1 post set to removed
200  {"status":"removed","content":"","sources":[],"verdict_note":"","author":"part5_ada_190845","is_mine":false,"keys":23}
200  {"status":"removed","content":""}
200  {"status":"removed","content":"Rain is wet, says the weather office.","sources":1,"verdict_note":"internal","is_mine":true}
200  [{"id":"cd39bb38-a178-4122-bc48-80a150bd7210","status":"removed","confidence_score":null,"verdict_source":null}]
null
```

- Line 1 is the **tombstone**: still 23 keys, the author's name and the post time stay, but `content`, `sources`,
  `verdict_note` (and the confidence and verdict source) are blank, so nothing of the post leaks.
- Line 3: the author sees their own removed post in full. The removal reason and the appeal button come with
  Parts 10 and 11.
- Line 4: the poll answers `removed` (so an open tab learns it) with nothing else. Line 5: it is not in the feed.

#### Step 8: The status endpoint is rate limited

**Where:** Terminal window 2.

**What this does:** Waits a minute so the allowance starts fresh, then asks for the status 125 times. The
limit is `status_poll`: 120 a minute per client address. It counts only this endpoint, so reading the feed
still works.

```bash
sleep 61                                            # let the one-minute allowance start fresh
for i in $(seq 125); do curl -s -o /dev/null -w '%{http_code}\n' "$api/posts/status/?ids=$fact"; done | sort | uniq -c
curl -s "$api/posts/status/?ids=$fact" | jq -c .
curl -s -D - -o /dev/null "$api/posts/status/?ids=$fact" | grep -i -E "^(HTTP|retry-after)"
curl -s -o /dev/null -w 'the feed still answers: %{http_code}\n' $api/posts/
```

**You should see** (the seconds differ):

```text
    120 200
      5 429
{"detail":"Request was throttled. Expected available in 59 seconds.","code":"throttled"}
HTTP/1.1 429 Too Many Requests
Retry-After: 59
the feed still answers: 200
```

- One tab polling at its fastest makes 6 requests a minute, so 120 is room for about 20 tabs behind one address.
- Wait a minute before step 9 if you want to poll again from this terminal.

#### Step 9: What a link preview or a search crawler sees

**Where:** Terminal window 2, with `runserver` (window 1) and `npm run dev` (window 3) running.

**What this does:** Asks the Next.js server for a post's page with no cookies and no JavaScript, the way a crawler
does, and picks out the head tags. The server reads the post from Django itself, so the claim and its status are
in the HTML.

```bash
curl -s http://localhost:3000/p/$fact | grep -o -E '<title>[^<]*</title>|(property|name)="(og:title|og:description|og:type|og:image|twitter:image|twitter:card)" content="[^"]*"|rel="canonical" href="[^"]*"' | sort -u
echo ---
curl -s http://localhost:3000/p/$fact | grep -o "Solar capacity grew by roughly 30% worldwide last year\." | wc -l
curl -s -o /dev/null -w 'deleted post: %{http_code}\n' http://localhost:3000/p/$op
curl -s -o /dev/null -w 'not an id: %{http_code}\n' http://localhost:3000/p/not-a-post-id
curl -s -w '\nremoved post: %{http_code}\n' http://localhost:3000/p/$fact2 | grep -o -E '<title>[^<]*</title>|name="robots" content="[^"]*"|removed post: [0-9]+|Solar|Rain is wet' | sort -u
```

**You should see** (the first compile of the page in `next dev` takes a few seconds; the post id and the
count of claim occurrences can differ):

```text
name="twitter:card" content="summary_large_image"
name="twitter:image" content="http://localhost:3000/twitter-image.png"
property="og:description" content="Fact · CHECKING FACTS…"
property="og:image" content="http://localhost:3000/opengraph-image.png"
property="og:title" content="Solar capacity grew by roughly 30% worldwide last year. · Rumor Zero"
property="og:type" content="article"
rel="canonical" href="http://localhost:3000/p/fb1fc4a4-232f-4d10-830c-d83b343e5b5a"
<title>Solar capacity grew by roughly 30% worldwide last year. · Rumor Zero</title>
---
8
deleted post: 404
not an id: 404
name="robots" content="noindex, nofollow"
removed post: 200
<title>Removed post · Rumor Zero</title>
```

- The title is the start of the claim plus ` · Rumor Zero`; the description is the type and the status label.
  The share image is the site's static one (generating one per post would cost too much CPU on the free
  Workers plan).
- The claim appears several times (title, tags and the page itself). A post that was deleted, or an id that
  isn't one, is a real HTTP 404.
- A **removed** post is a 200 with the title "Removed post", `noindex`, and none of its text (the last command
  finds neither "Solar" nor "Rain is wet").

#### Step 10: Django Admin still shows a deleted post

**Where:** Browser, while `runserver` is running in window 1.

**What this does:** Opens the admin list of posts and finds the opinion `ada` deleted in step 6. The admin is
read-only until Part 10.

| URL | Expect |
|---|---|
| http://localhost:8000/admin/ | Sign in with the superuser you made in Part 0A. If it 404s, `ADMIN_URL_PATH` in `backend/.env` isn't `admin/`; use that path. |
| http://localhost:8000/admin/posts/post/ | The posts, newest first, including "I think the new tram line…" with a date in the **Deleted at** column. The filter panel now has **By deleted at** with *All*, *Empty* and *Not empty*. |
| Click **Not empty** under *By deleted at* | Only the deleted posts (the tram opinion). **Empty** shows everything that is still live. |

- The same rules are checked by the automated tests (`test_api_delete.py` finds the row through the admin
  changelist and both filter values).

#### Step 11: The post page in the browser

**Where:** Browser, with `runserver` (window 1) and `npm run dev` (window 3) running. Log in at
http://localhost:3000/login as **`cy`**, with `part5-cy-<your id>@example.test` and `correct-horse-battery-42`
(the id from step 3).

**What this does:** Posts a fact as `cy`, opens its page from the card, and tries Copy link and Delete.

| Do this | Expect |
|---|---|
| Open http://localhost:3000/home, click **New post**, type `Global solar output doubled in six years, the agency says.`, choose **Fact**, put `doi:10.1038/s41558-024-02102` in Source 1, click **Add another source** and put `https://www.iea.org/reports/renewables-2023` in Source 2, click **Post fact, will be checked** | The post is at the top of Recent with **CHECKING FACTS…**. |
| Look at its card's text and sources row | The claim is a link, and so is the whole card (the border darkens on hover). The row under it shows `doi.org/10.1038/s41558-024-02102 ↗` (opens doi.org in a new tab) and a blue `+1 more`. |
| Click the claim (or `+1 more`) | The address becomes `http://localhost:3000/p/<id>` (with `#sources` for `+1 more`, which scrolls to the sources). The page: **← BACK TO HOME**, a white card with a pale grey left edge holding **FACT** and **CHECKING FACTS…**, the claim in large upright serif, `@part5_cy_<id>` with `Oct 9, 2026, 1:10 PM UTC` (a UTC time), then **Copy link** and **Delete** |
| Look under the card | A **Verdict** card saying **Checking facts…** and "We're checking this claim. This page updates on its own when there is a result.", then **Sources (2)**: `01  DOI  10.1038/s41558-024-02102` and `02  LINK  https://www.iea.org/reports/renewables-2023`, each with an open-in-new icon |
| Click an open-in-new icon | The source opens in a new tab (the DOI goes to `https://doi.org/10.1038/…`). |
| Click **Copy link** | A dark toast says **Link copied.** Paste into the address bar: it is `http://localhost:3000/p/<id>`. |
| Click **Delete** | A dialog **Delete this post?**: "It disappears from feeds and from its page right away. This can't be undone." and, because it is a fact, "A deleted fact post still counts toward your fact posts for the last 24 hours." with **Cancel** and a red **Delete post**. Click **Cancel**: nothing changes. |
| Click **Delete**, then **Delete post** | You are back on `/home` with the toast **Post deleted.** and the post is gone from Recent (also after a reload). |
| Open the old `/p/<id>` address | The page "Page not found" (a real 404, for you as well). |
| Open a post you didn't write (any post by `ada`) | Same page, with **Copy link** but **no Delete**. |

- Log out and open any `/p/<id>`: the same page without Delete, no login needed.
- A post removed by a moderator (step 7's `fact2`): as a visitor, `/p/<id>` shows a white card with the author's
  name, the date and "This post was removed by a moderator." and nothing else. Logged in as its author, the page
  shows the text under a pale orange note "This post was removed by a moderator. Only you can see this text.",
  a grey **REMOVED** badge next to **FACT**, and no Verdict card. In the feed, a card that is open when its post
  is removed turns into a grey "Removed by a moderator" card within about 10 seconds.

#### Step 12: Badges update by themselves

**Where:** Browser (logged in as `cy`, with a fresh fact on screen) and Terminal window 2.

**What this does:** Changes a pending post's status in the database while its page and the feed are open, the way
the pipeline (Part 9) and the moderators (Part 10) will, and watches the badge change without a reload. The
status endpoint is polled every 10 seconds at first, then every 15, 22 … up to every 60, only while the tab is
on screen, and it stops after 10 minutes of visible time.

First post another fact as `cy` (step 11's first row) and open its page; keep the feed (`/home`) open in a
second tab. Copy the post's id from the address (`/p/<id>`). In window 2:

```bash
python manage.py shell -c "from apps.posts.models import Post; print(Post.objects.filter(pk='<id>').update(status='verified_true', verdict_source='pipeline', pipeline_verdict='true', confidence_score=94), 'post updated')" | tail -1
```

Replace `<id>` with the id you copied.

**You should see** `1 post updated`, and in the browser, within about 10 seconds and with no reload:

| Where | Expect |
|---|---|
| The post's page | The chip changes from **CHECKING FACTS…** to a teal **VERIFIED 94%**, the left edge turns teal, and the Verdict card says **Checked automatically · 94% confidence** and "This claim was found to be true." |
| The feed tab (when you switch to it) | The card for that post shows **VERIFIED 94%** too. |

- Watching the polling: open DevTools → Network, filter on `status`. Requests to `/api/v1/posts/status/?ids=…`
  go out about every 10 s, then 15 s, 22 s … while a pending post is on screen, and **stop for good once nothing
  is pending**. Switch to another browser tab: no requests while it is hidden, and one the moment you come back.
  (These timings are covered by the automated tests with fake timers; the "badge changes within about 10 seconds"
  part was also watched in headless Chromium.)
- Try `status='removed'` instead: the feed card turns into a grey "Removed by a moderator" card, and the page
  becomes the tombstone for everyone but the author.

#### Step 13: A phone-sized window

**Where:** Browser, logged in as `cy`.

**What this does:** Checks the post page at phone width. In Firefox or Chrome press `F12`, then the "responsive
design" / device toolbar button, and set the width to 390. Open any `/p/<id>` of a fact.

| Do this | Expect |
|---|---|
| Open the post's page | A top bar with the logo and your avatar, then **← BACK TO HOME**, the card with the claim wrapped over several lines, the author line and a UTC date, and **Copy link** and **Delete** side by side. A bottom bar (Home, Search, New post, Notifications, Profile). **No sideways scrolling.** |
| Scroll down | **Verdict** and **Sources (2)**: a long link wraps inside its row (`https://www.iea.org/reports/r` / `enewables-2023`), and the open-in-new icon stays at the right. |
| Tap **Delete** | The dialog fits the screen, with **Cancel** and **Delete post**. |

#### Step 14: Stop and clean up

**Where:** Every terminal window, plus the browser.

- Stop the servers: `Ctrl+C` in windows 1 and 3 (a leftover `next dev`: step 12 of Part 1).
- Delete the test accounts and their posts (the posts go with them). In window 2, in `backend/` with the
  venv active:

  ```bash
  python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(email__startswith='part5-').delete())" | tail -1
  ```

  After one clean run of this guide it prints `(12, {'posts.Post': 6, 'account.EmailAddress': 3, 'accounts.User': 3})`: how many rows went in all, and per
  table (6 posts: the three `ada` made in steps 3 and 7, plus the ones you made as `cy` in steps 11 and 12, so your
  count differs; a deleted post is still a row). Nothing else is touched. (The E2E tests' accounts stay in your local database, as in earlier parts: Django
  Admin → Users deletes them.)
- `docker compose down` (repo root) stops the containers and keeps the data; `docker compose down -v`
  wipes the whole local database, which is destructive.
- No secret was used or printed in this part: the only values in the commands are Cloudflare's public test
  token and the throwaway password of the test accounts.

### Part 6: Profiles, follows, Following feed

Needs Part 0A's containers and virtualenv, Part 0C's frontend, and your own `backend/.env` and
`frontend/.env.local`. Part 6 adds **one migration** (`social.0001_initial`, the follows table), **no dependency**
and **no new variable** (`FEED_CACHE_SECONDS` was already in `.env.example`; the code reads it now). It adds
the endpoints `GET /api/v1/users/{username}/` (and `…/posts/`, `…/followers/`, `…/following/`),
`POST` and `DELETE /api/v1/users/{username}/follow/`, and `GET /api/v1/feed/`.

**Which terminal window for what.** Open the windows once and keep using the same ones:

| Window | What runs in it | Used in steps |
|---|---|---|
| Window 1 (server) | `python manage.py runserver` in `backend`, venv active. Leave it running. Start it in step 3, **after** step 2 (Playwright starts its own servers and needs ports 3000 and 8000 free). | 3 to 14 |
| Window 2 (commands) | All the `curl` and `python manage.py` commands. **Use the same window for steps 3 to 10**: the variables and functions you set in step 3 (`id`, `h`, `ada`, `bo`, `cy`, `api`, `boname`, `signup`, `mk`, `get`) only live in that one terminal. If you close it, redo step 3. | 1 to 10, 15 |
| Window 3 (frontend) | `npm run dev` in `frontend/`. Leave it running. | 10 to 14 |
| Browser | Steps 11 to 14 | 11 to 14 |

Things to know first:

- Steps 3 to 10 talk to the API directly with `curl` (they need `jq`: `sudo apt install jq`). Steps 11 to 14 use the
  browser. Step 3 makes three accounts, all verified: `bo` is the person whose profile we look at, `ada` follows
  `bo`, and `cy` stays for the browser steps. Later steps add `dee` (never verified) and `fay` (for the throttle).
- The API and page outputs below were recorded on Linux on 2026-10-09. The browser steps were checked the same
  day with headless Chromium (screenshots at 1280 and 390 px), not by a person at a keyboard. Ids, numbers in
  names, times and token prefixes differ on every run.
- Nothing here sends an email: step 3 marks the accounts verified with a shell command, which stands in for
  clicking the link (Part 2 shows the real flow). Step 7 sets post statuses the same way, because the pipeline
  and the moderator tools that do it for real arrive in Parts 9 and 10.
- **What Part 6 does and doesn't show:** profiles are public; following needs a verified email; a profile's
  **Verified** and **FALSE** counters also count posts the author deleted, but never removed ones (step 7);
  the Following feed keeps only the *ids* of its first page for 30 seconds (step 8). Likes, comments,
  reposts and the credibility score come in later parts.

#### Step 1: Run the automated backend checks

**Where:** Terminal window 2 (commands), starting in the repo root.

**What this does:** Starts the database containers, activates the Python environment, applies the new migration,
confirms there is no further one, then runs the whole backend test suite, the new social tests, the linter and
the formatter check.

```bash
# start in the repo root
docker compose up -d
cd backend
source .venv/bin/activate
python manage.py migrate                            # Applying social.0001_initial... OK
python manage.py makemigrations --check --dry-run   # No changes detected
python manage.py check                              # System check identified no issues (0 silenced).
python -m pytest                                    # 1336 passed
python -m pytest apps/social -q                     # 160 passed
ruff check . ; ruff format --check .                # All checks passed! / 132 files already formatted
```

**You should see:** `Applying social.0001_initial... OK` (nothing to apply the second time), `No changes detected`
and `System check identified no issues (0 silenced).`, then the full run ends with `1336 passed`, the social run
with `160 passed`, and the last line pair is `All checks passed!` and `132 files already formatted`. (Counts may
grow later; what matters is that nothing fails.)

- The 160 new social tests: `test_models.py` (6: the unique pair, nobody follows themselves, both list indexes),
  `test_services.py` (18: follow is idempotent, two simultaneous follows make one row, the cache is cleared),
  `test_api_profile.py` (26), `test_api_follow.py` (23, including the real 100-requests-an-hour throttle),
  `test_api_lists.py` (23: order, cursor walk, crafted cursors, constant query counts), `test_api_user_posts.py`
  (19), `test_api_feed.py` (14), `test_feed_cache.py` (25: what is cached, when it is cleared, what a hit still
  reads fresh), `test_admin.py` (4) and `test_no_network.py` (2).
- Outside `apps/social`: the cursor check moved into a shared `TimestampCursorMixin` (`apps/core/tests/test_pagination.py`
  tests it, with a control showing what the unguarded class does), `FEED_CACHE_SECONDS` has settings tests, and
  `create_post` clears the author's cached feed.

#### Step 2: Run the automated frontend checks

**Where:** Terminal window 2, then `cd ../frontend`. Playwright (the last two commands) starts Django and
Next itself, so **no servers may be running on ports 3000 and 8000** (it reuses them if they are, with
whatever settings they have).

**What this does:** Runs the linters, the type check, the component tests, the production build and the
end-to-end tests.

```bash
cd ../frontend                                      # from backend/
npm run lint ; npm run lint:tokens ; npm run typecheck ; npm run format:check
npm test                                            # 99 files, 1320 tests passed
NEXT_PUBLIC_GOOGLE_CLIENT_ID= npm run build
npm run test:e2e                                    # 29 passed
CI=1 npm run test:e2e                               # 29 passed (against the production build)
cd ../backend                                       # back to backend/ for steps 3 to 10
```

**You should see:** the first line prints nothing from ESLint and TypeScript and ends with
`lint:tokens OK (…)` and `All matched files use Prettier code style!`. `npm test` ends with
`Test Files  99 passed (99)` and `Tests  1320 passed (1320)`. `npm run build` lists the routes as in Part 5, plus
`ƒ /u/[username]`, `ƒ /u/[username]/followers` and `ƒ /u/[username]/following` (dynamic: the profile is read on the
server for each request). Each E2E run ends with `29 passed`: the 24 earlier tests and 5 new ones in
`e2e/social.spec.ts`.

- The new E2E file signs up **two** people once and shares them (allauth limits sign-ups to 20 a minute per
  address and the rest of the suite already uses most of that). Its tests: a crawler gets a profile's `<title>`,
  Open Graph and canonical tags, an upper-case address redirects and an unknown name is a 404; a visitor is sent
  to log in to follow and sees no Following tab; the profile, the followers list and `/home` fit a phone with no
  sideways scroll; A follows B, B posts, A sees it under Following, then unfollows and the tab is empty again;
  your own post is in your Following tab at once and your own profile shows Edit profile and no Follow.
- Two E2E helpers changed: the sign-up helper now waits up to 30 seconds for `/verify-email` (hashing the password
  takes a while when six workers sign up at once; this flake predates Part 6), and `posts.spec.ts` now expects two
  links on a card (the author and the claim).

#### Step 3: Start the servers and make three accounts and two posts

**Where:** First window 1 (the Django server) and window 3 (the frontend), then window 2 (the commands).
**Keep using window 2 for steps 4 to 10.**

**What this does:** Windows 1 and 3 run the two servers. In window 2 you sign up three accounts through the API
and mark them verified, then `bo` posts an opinion and a fact with a DOI. The helpers `mk` (make a post, print its id) and `get` (print the status code, then the answer) are used by the next steps.

Window 1 (in `backend`, venv active):

```bash
python manage.py runserver                          # leave it running
```

Window 3:

```bash
cd frontend                                         # from the repo root
npm run dev                                         # leave it running
```

Window 2 (in `backend` with the venv active: steps 1 and 2 leave you there; needs `jq`). If you opened a new
terminal, first run `cd backend` from the repo root and `source .venv/bin/activate`:

```bash
id=$(date +%H%M%S)                                  # a unique suffix so the addresses are new each run
h=(-H 'Origin: http://localhost:3000' -H 'X-Requested-With: rumor-zero')   # headers every auth call needs
signup() { jq -nc --arg e "$1" --arg u "$2" '{email: $e, username: $u, password: "correct-horse-battery-42", turnstile_token: "XXXX.DUMMY.TOKEN.XXXX"}' | curl -s "${h[@]}" -H "Content-Type: application/json" --data-binary @- http://localhost:8000/api/auth/app/v1/auth/signup | jq -r .meta.access_token; }
ada=$(signup "part6-ada-$id@example.test" "part6_ada_$id")      # $ada = ada's login token (follows bo)
bo=$(signup "part6-bo-$id@example.test" "part6_bo_$id")         # $bo = bo's login token (the author we look at)
cy=$(signup "part6-cy-$id@example.test" "part6_cy_$id")         # $cy = cy's login token (kept for the browser)
python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(email__startswith='part6-', email__endswith='$id@example.test').update(is_email_verified=True), 'accounts marked verified')" | tail -1
api=http://localhost:8000/api/v1
adaname=part6_ada_$id; boname=part6_bo_$id; cyname=part6_cy_$id
mk() { curl -s -H "Authorization: Bearer $1" -H "Content-Type: application/json" --data-binary "$2" $api/posts/ | jq -r .id; }   # mk <token> <json>: makes a post, prints its id
get() { local out; out=$(curl -s -w '\n%{http_code}' ${2:+-H "Authorization: Bearer $2"} "$api$1"); printf '%s  ' "${out##*$'\n'}"; printf '%s' "${out%$'\n'*}" | jq -c "${3:-.}"; }   # get <path> [token] [jq filter]: prints the status code, then the answer
op1=$(mk "$bo" '{"content":"I think the new tram line will change how the city moves.","post_type":"opinion"}')
fact1=$(mk "$bo" '{"content":"Solar capacity grew by roughly 30% worldwide last year.","post_type":"fact","sources":["doi:10.1038/s41558-024-02102"]}')
echo ${ada:0:10} ${bo:0:10} ${cy:0:10}               # three prefixes, not an empty line
echo "op1=$op1"; echo "fact1=$fact1"                 # two ids, not empty
```

**You should see** (the number in the names is your `id`, and the ids differ):

```text
3 accounts marked verified
eyJhbGciOi eyJhbGciOi eyJhbGciOi
op1=94dd0202-8d1c-4aca-8c33-8aeee8c7833b
fact1=bb1b71af-8729-4d83-9e4f-26bc1a537d0d
```

- The shell prints a line about auto-imported objects first; `tail -1` keeps only ours.
- Sign-up is limited to 20 a minute per address (Part 1), and still calls Cloudflare's test widget, so it
  needs internet.

**If it differs:** an empty token or an `id` of `null` means the sign-up or the post failed: `runserver` isn't
running, `jq` is missing, or you signed up more than 20 times in a minute. Fix that and run this step again
from `id=$(date +%H%M%S)`.

#### Step 4: Read a profile

**Where:** Terminal window 2 (the same terminal as step 3).

**What this does:** Reads `GET /api/v1/users/{username}/` as nobody and as other people. A profile is public; only
`is_following` and `is_me` depend on who asks. Then four names that don't give a profile.

```bash
get /users/$boname/ "" '{username, display_name, bio, avatar_url, counts, reputation, is_following, is_me, keys: (keys | length)}'   # 1: anyone, no login
get /users/${boname^^}/ "" '{username}'                                                                                              # 2: upper case works
get /users/$boname/ "$ada" '{is_following, is_me}'                                                                                  # 3: ada, who doesn't follow bo yet
get /users/$boname/ "$bo" '{is_following, is_me}'                                                                                   # 4: bo looking at himself
get /users/nobody_$id/ "" .                                                                                                         # 5: no such user
get /users/ab/ "" .                                                                                                                 # 6: too short to be a username
get "/users/$boname%00x/" "" .                                                                                                      # 7: a NUL byte in the name
```

**You should see** (seven commands, seven answers):

```text
200  {"username":"part6_bo_212733","display_name":"","bio":"","avatar_url":null,"counts":{"followers":0,"following":0,"posts":2,"verified":0,"false":0},"reputation":{"score":null,"sample":0},"is_following":false,"is_me":false,"keys":10}
200  {"username":"part6_bo_212733"}
200  {"is_following":false,"is_me":false}
200  {"is_following":false,"is_me":true}
404  {"detail":"Not found.","code":"not_found"}
404  {"detail":"Not found.","code":"not_found"}
404  {"detail":"Not found.","code":"not_found"}
```

- The profile has exactly 10 keys and never an email or role. `posts` is 2: the opinion and the fact. A new
  account has a blank display name, so the page shows `@username` once instead.
- `reputation` is there already (`score` stays `null` until a person has 3 counted events, which Part 11B
  starts counting); the page doesn't show it yet.
- Lookup is case-insensitive (line 2). An unknown name, a name too short to be one and a name with a NUL byte
  all give the same JSON 404, never a server error (the NUL case was a 500 until a test caught it).

#### Step 5: Follow and unfollow

**Where:** Terminal window 2.

**What this does:** Follows and unfollows through `POST` and `DELETE /api/v1/users/{username}/follow/`, with
every refusal. Both are idempotent. Following needs a verified email, unfollowing only a login.

```bash
follow() { curl -s -w '  %{http_code}\n' -X POST ${2:+-H "Authorization: Bearer $2"} $api/users/$1/follow/; }       # follow <username> [token]
unfollow() { curl -s -w '  %{http_code}\n' -X DELETE ${2:+-H "Authorization: Bearer $2"} $api/users/$1/follow/; }   # unfollow <username> [token]
follow $boname "$ada"                                # 1: the first follow is 201
follow $boname "$ada"                                # 2: again: 200, nothing changes
follow $boname                                       # 3: nobody logged in
follow $adaname "$ada"                               # 4: following yourself
follow nobody_$id "$ada"                             # 5: no such user
dee=$(signup "part6-dee-$id@example.test" "part6_dee_$id")    # dee never verifies the email
follow $boname "$dee"                                # 6: an unverified account can't follow
get /users/$boname/ "$ada" '{counts: {followers: .counts.followers}, is_following}'    # 7: the count moved
unfollow $boname "$ada"                              # 8: unfollow: 204
unfollow $boname "$ada"                              # 9: again: still 204
unfollow $boname "$dee"                              # 10: an unverified account may unfollow (nothing to remove here)
get /users/$boname/ "$ada" '{counts: {followers: .counts.followers}, is_following}'    # 11: back to 0
follow $boname "$ada"                                # 12: ada follows again for the next steps
```

**You should see** (twelve commands, twelve answers):

```text
{"is_following":true}  201
{"is_following":true}  200
{"detail":"Authentication credentials were not provided.","code":"not_authenticated"}  401
{"detail":"You can't follow yourself.","code":"cannot_follow_self"}  400
{"detail":"Not found.","code":"not_found"}  404
{"detail":"Verify your email address first. Check your inbox for the link.","code":"email_unverified"}  403
200  {"counts":{"followers":1},"is_following":true}
  204
  204
  204
200  {"counts":{"followers":0},"is_following":false}
{"is_following":true}  201
```

- 201 the first time, 200 when you already followed: the same answer, so a retry is safe. Unfollowing is 204 with
  no body, whether or not you were following. Two simultaneous follows make one row (a test proves it).
- Order of checks: login (401), verified email (403), then the throttle, then the name (404), then the rule
  (400). A 401 or 403 never counts against the 100-an-hour allowance (step 9).

#### Step 6: Followers, following and a person's posts

**Where:** Terminal window 2.

**What this does:** `cy` follows `bo` and `bo` follows `cy`; then reads both lists, one page at a time, and
`bo`'s posts with the Facts / Opinions filter. `is_following` and `is_me` are from the point of view of whoever
asks.

```bash
follow $boname "$cy"                                 # cy follows bo too
follow $cyname "$bo"                                 # and bo follows cy
get /users/$boname/followers/ "$cy" '{names: [.results[].username | sub("part6_"; "") | sub("_'$id'"; "")], is_following: [.results[].is_following], is_me: [.results[].is_me], keys: (.results[0] | keys | length), next_cursor}'   # 1: bo's followers, as cy
get /users/$boname/followers/ "" '{names: [.results[].username | sub("part6_"; "") | sub("_'$id'"; "")], is_following: [.results[].is_following]}'   # 2: the same list as a visitor
get /users/$boname/following/ "" '{names: [.results[].username | sub("part6_"; "") | sub("_'$id'"; "")]}'                                          # 3: who bo follows
get "/users/$boname/followers/?page_size=1" "" '{names: [.results[].username | sub("part6_"; "") | sub("_'$id'"; "")], more: (.next_cursor != null)}'  # 4: one per page
get "/users/$boname/followers/?cursor=cD1ub3QtYS1kYXRl" "" .                                                                                          # 5: a made-up cursor (it decodes to p=not-a-date)
get /users/$boname/posts/ "" '{pinned, kinds: [.results[].kind], posts: [.results[].post | {type: .post_type, status, is_mine}]}'                     # 6: bo's posts
get "/users/$boname/posts/?post_type=fact" "" '{types: [.results[].post.post_type]}'                                                                         # 7: facts only
get "/users/$boname/posts/?post_type=opinion" "" '{types: [.results[].post.post_type]}'                                                                      # 8: opinions only
get "/users/$boname/posts/?post_type=both" "" .                                                                                                     # 9: not a type
```

**You should see:**

```text
{"is_following":true}  201
{"is_following":true}  201
200  {"names":["cy","ada"],"is_following":[false,false],"is_me":[true,false],"keys":8,"next_cursor":null}
200  {"names":["cy","ada"],"is_following":[false,false]}
200  {"names":["cy"]}
200  {"names":["cy"],"more":true}
404  {"detail":"Invalid cursor","code":"not_found"}
200  {"pinned":[],"kinds":["post","post"],"posts":[{"type":"fact","status":"pending","is_mine":false},{"type":"opinion","status":"published","is_mine":false}]}
200  {"types":["fact"]}
200  {"types":["opinion"]}
400  {"post_type":["Choose fact or opinion, or leave it out."]}
```

- Followers come newest follow first (`cy`, then `ada`). A row has 8 keys: the public bits plus `bio`,
  `reputation`, `is_following` and `is_me`; never an email. Line 1 is as `cy`, so `cy`'s own row has `is_me`
  true; `is_following` is false everywhere because `cy` follows only `bo`.
- Pages are 20 long (`?page_size=` up to 50); `next_cursor` is an opaque token. A made-up one is a 404, never a
  server error. The number of database queries doesn't grow with the list (tests pin it).
- `bo`'s posts: the same feed shape as Recent (`pinned` is always `[]` here), newest first, only what the public
  can see; a bad `post_type` is a 400 on that field.

#### Step 7: The Verified and FALSE counters

**Where:** Terminal window 2, in `backend` with the venv active.

**What this does:** Gives `bo` four more fact posts and sets their status the way the pipeline (Part 9) and the
moderators (Part 10) will: one verified, one FALSE, one verified and then **deleted by `bo`**, one **removed**. Then
reads the counters. A deleted post's verdict still counts (so deleting can't erase a FALSE label); a removed post
is in neither counter.

```bash
factA=$(mk "$bo" '{"content":"The river authority says the bridge reopened on Monday.","post_type":"fact"}')
factB=$(mk "$bo" '{"content":"The harvest was the largest ever recorded.","post_type":"fact"}')
factC=$(mk "$bo" '{"content":"The ferry now runs every ten minutes.","post_type":"fact"}')
factD=$(mk "$bo" '{"content":"The museum is free on Sundays.","post_type":"fact"}')
python manage.py shell -c "
from apps.posts.models import Post
for pk, fields in [('$factA', dict(status='verified_true', verdict_source='pipeline', pipeline_verdict='true', confidence_score=94)),
                   ('$factB', dict(status='verified_false', verdict_source='pipeline', pipeline_verdict='false', confidence_score=90)),
                   ('$factC', dict(status='verified_true', verdict_source='pipeline', pipeline_verdict='true', confidence_score=91)),
                   ('$factD', dict(status='removed'))]:
    Post.objects.filter(pk=pk).update(**fields)
print('4 posts set')" | tail -1
get /users/$boname/ "" '{counts}'                                          # 1: two verified so far, one FALSE
curl -s -o /dev/null -w 'delete the verified post: %{http_code}\n' -X DELETE -H "Authorization: Bearer $bo" $api/posts/$factC/   # 2: bo deletes factC
get /users/$boname/ "" '{counts}'                                          # 3: it is hidden, but its verdict still counts
get /users/$boname/posts/ "" '{statuses: [.results[].post.status]}'                   # 4: the list: no removed, no deleted post
```

**You should see:**

```text
4 posts set
200  {"counts":{"followers":2,"following":1,"posts":5,"verified":2,"false":1}}
delete the verified post: 204
200  {"counts":{"followers":2,"following":1,"posts":4,"verified":2,"false":1}}
200  {"statuses":["verified_false","verified_true","pending","published"]}
```

- Line 1: `posts` is 5 (the opinion, the pending fact and three of the four new ones: the removed one is
  hidden), `verified` 2, `false` 1. After the delete (line 3) `posts` falls to 4 but **`verified` stays 2**: the
  deleted post is hidden from the list and the count of posts, yet its verdict stays on the record.
- The list (line 4) has no removed and no deleted post, even for their author.

#### Step 8: The Following feed and its cache

**Where:** Terminal window 2. Needs `REDIS_URL` set in `backend/.env` (as in `.env.example`): line 3 reads the
cache from a second process, which only works when the cache is the shared Redis, not each process's memory.

**What this does:** Reads `GET /api/v1/feed/` as `ada`, who follows `bo`. Shows what is kept in the cache
(only ids), that your own new post appears at once, that a post by someone you follow can take up to 30 seconds
(`FEED_CACHE_SECONDS`), and that a post deleted by its author vanishes immediately because the posts themselves
are read fresh every time. (This step waits 31 seconds.)

```bash
adaid=$(curl -s -H "Authorization: Bearer $ada" $api/me/ | jq -r .id)
get /feed/ "" .                                                           # 1: nobody logged in
get /feed/ "$ada" '{contents: [.results[].post.content]}'                             # 2: ada follows bo: bo's posts, newest first
python manage.py shell -c "from django.core.cache import cache; print(cache.get('social:following-feed:v1:$adaid'))" | tail -1   # 3: what is cached for ada
mine=$(mk "$ada" '{"content":"I think ada can see her own post at once.","post_type":"opinion"}')
get /feed/ "$ada" '.results[0].post | {content, is_mine}'               # 4: ada's own post is first, despite the cache
mk "$bo" '{"content":"Bo posts something new right now.","post_type":"opinion"}' > /dev/null
get /feed/ "$ada" '{seen: ([.results[].post.content] | any(. == "Bo posts something new right now."))}'   # 5: ada does not see it yet (the cache lives for 30 s)
sleep 31
get /feed/ "$ada" '{seen: ([.results[].post.content] | any(. == "Bo posts something new right now."))}'   # 6: after 30 seconds she does
curl -s -o /dev/null -w 'bo deletes his tram opinion: %{http_code}\n' -X DELETE -H "Authorization: Bearer $bo" $api/posts/$op1/
get /feed/ "$ada" '{tram: ([.results[].post.content | select(startswith("I think the new tram"))] | length)}'   # 7: gone at once, no waiting
```

**You should see:**

```text
401  {"detail":"Authentication credentials were not provided.","code":"not_authenticated"}
200  {"contents":["The harvest was the largest ever recorded.","The river authority says the bridge reopened on Monday.","Solar capacity grew by roughly 30% worldwide last year.","I think the new tram line will change how the city moves."]}
{'ids': ['f44bbb89-28fc-4482-a788-f84c53c1eb09', '83f46a4f-fbb6-4160-a6ec-ddca8d9ebfd5', 'bb1b71af-8729-4d83-9e4f-26bc1a537d0d', '94dd0202-8d1c-4aca-8c33-8aeee8c7833b'], 'next': None}
200  {"content":"I think ada can see her own post at once.","is_mine":true}
200  {"seen":false}
200  {"seen":true}
bo deletes his tram opinion: 204
200  {"tram":0}
```

- Line 3: what the cache holds for `ada` is only a list of post **ids** and the next-page cursor, never any
  text. The posts are read again on every request, so a deleted or removed post disappears at once (line 7), and
  likes and counts (Part 7) will never be stale.
- The cache is cleared for you when you post (line 4), follow or unfollow. A post by someone you follow
  reaches you after at most `FEED_CACHE_SECONDS` (30 by default; 0 turns the cache off). Only a first page asked
  with the default size is cached.
- The Following feed needs a login (line 1) but not a verified email: reading is allowed.

#### Step 9: Following is rate limited

**Where:** Terminal window 2.

**What this does:** Makes a fresh verified account, `fay`, and sends 101 follow requests as her. The limit is
`follow`: 100 an hour per user, shared by follow and unfollow. Reading profiles is not counted.

```bash
fay=$(signup "part6-fay-$id@example.test" "part6_fay_$id")
python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(email='part6-fay-$id@example.test').update(is_email_verified=True), 'account marked verified')" | tail -1
for i in $(seq 101); do curl -s -o /dev/null -w '%{http_code}\n' -X POST -H "Authorization: Bearer $fay" $api/users/$boname/follow/; done | sort | uniq -c
curl -s -X POST -H "Authorization: Bearer $fay" $api/users/$boname/follow/ | jq -c .
curl -s -D - -o /dev/null -X POST -H "Authorization: Bearer $fay" $api/users/$boname/follow/ | grep -i -E "^(HTTP|retry-after)"
curl -s -o /dev/null -w 'reading profiles still works: %{http_code}\n' $api/users/$boname/
```

**You should see** (the seconds differ):

```text
1 account marked verified
     99 200
      1 201
      1 429
{"detail":"Request was throttled. Expected available in 3599 seconds.","code":"throttled"}
HTTP/1.1 429 Too Many Requests
Retry-After: 3599
reading profiles still works: 200
```

- 100 requests went through (the first made the follow, the other 99 were repeats), the 101st was refused with
  `429` and a `Retry-After` in seconds. The same limit applies to unfollowing, so someone can't flip a follow back
  and forth all day.
- A 401 (not logged in) or 403 (email not verified) doesn't use up the allowance.

#### Step 10: What a link preview or a search crawler sees

**Where:** Terminal window 2, with `runserver` (window 1) and `npm run dev` (window 3) running.

**What this does:** Asks the Next.js server for a profile page with no cookies and no JavaScript, the way a
crawler does, and picks out the head tags. The server reads the profile from Django itself.

```bash
curl -s http://localhost:3000/u/$boname | grep -o -E '<title>[^<]*</title>|(property|name)="(og:title|og:description|og:type|og:image|twitter:image|twitter:card)" content="[^"]*"|rel="canonical" href="[^"]*"' | sort -u
echo ---
curl -s http://localhost:3000/u/$boname | grep -o "@$boname" | sort | uniq -c
curl -s -o /dev/null -w 'upper case: %{http_code} -> %{redirect_url}\n' http://localhost:3000/u/${boname^^}
curl -s -o /dev/null -w 'no such user: %{http_code}\n' http://localhost:3000/u/nobody_$id
curl -s -o /dev/null -w 'not a username: %{http_code}\n' http://localhost:3000/u/ab
curl -s http://localhost:3000/u/nobody_$id | grep -o -E 'name="robots" content="[^"]*"' | sort -u
```

**You should see** (the first compile of the page in `next dev` takes a few seconds; the name and the count of
`@name` occurrences differ):

```text
name="twitter:card" content="summary_large_image"
name="twitter:image" content="http://localhost:3000/twitter-image.png"
property="og:description" content="Posts by @part6_bo_212733 on Rumor Zero."
property="og:image" content="http://localhost:3000/opengraph-image.png"
property="og:title" content="@part6_bo_212733 · Rumor Zero"
property="og:type" content="profile"
rel="canonical" href="http://localhost:3000/u/part6_bo_212733"
<title>@part6_bo_212733 · Rumor Zero</title>
---
     13 @part6_bo_212733
upper case: 307 -> http://localhost:3000/u/part6_bo_212733
no such user: 404
not a username: 404
name="robots" content="noindex"
```

- The title is `Display Name (@name)`, or `@name` when there is no display name (a new account has none). The
  description is the bio's first 160 characters, or "Posts by @name on Rumor Zero.". The share image is the
  site's static one, set again on this page because a page's own Open Graph tags replace the site-wide ones.
- `/u/NAME` in capitals answers `307` to the lower-case address, so there is one canonical URL. An unknown name,
  or one that can't be a username, is a real HTTP 404 with `noindex`. (The count of `@name` only has to be
  above zero: Next repeats it in the page and in its payload.)

#### Step 11: Django Admin lists the follows

**Where:** Browser, while `runserver` is running in window 1.

**What this does:** Opens the admin list of follows, which is read-only: changes only go through the follow
service, so the feed cache can't be left out of date.

| URL | Expect |
|---|---|
| http://localhost:8000/admin/ | Sign in with the superuser you made in Part 0A. If it 404s, `ADMIN_URL_PATH` in `backend/.env` isn't `admin/`; use that path. |
| http://localhost:8000/admin/social/follow/ | **Follows**: follower, following and created time, newest first, with a search box on the usernames. There is no **Add follow** button. |
| Click a follow | A page that only shows the values: no Save and no Delete (they answer 403 if you type the address). |

- Covered by `test_admin.py` (the list, the search, and 403 for add, change and delete); not opened by a person.

#### Step 12: A profile in the browser

**Where:** Browser, with `runserver` (window 1) and `npm run dev` (window 3) running. First give `bo` a name and a
bio (the Settings page arrives in Part 14), in window 2:

```bash
python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(username='$boname').update(display_name='Bo Stone', bio='Climate reporter. I write about energy, rivers and trams.\nPosts here are mine alone.'), 'profile updated')" | tail -1
```

Then log in at http://localhost:3000/login as **`cy`**, with `part6-cy-<your id>@example.test` and
`correct-horse-battery-42` (the id from step 3).

**What this does:** Opens profiles, follows and unfollows, and uses the filter chips.

| Do this | Expect |
|---|---|
| Open `http://localhost:3000/u/part6_bo_<id>` (your id) | One white card: a round avatar with the initials **BS**, **Bo Stone** in large serif, `@part6_bo_<id>` under it in blue, the bio (two lines), `Joined <this month and year> · 4 posts`, and a pale panel with four counters: **3 FOLLOWERS**, **1 FOLLOWING**, **● 2 VERIFIED** (teal dot), **● 1 FALSE** (red dot). Top right of the card a white **Following** button (`cy` follows `bo` since step 6). No "Debunked" anywhere. |
| Below the card | Three chips **All** (dark), **Facts**, **Opinions**, then `bo`'s posts as cards, newest first: the new opinion from step 8, a FALSE 90% card (red edge), a VERIFIED 94% card (teal edge) and a CHECKING FACTS… card with its DOI row. No removed or deleted post, and not the tram opinion `bo` deleted. |
| Click **Facts** | The list reloads with only the three facts (the opinion is gone); **Facts** is dark. Click it again: back to **All**. |
| Hover the **Following** button | The word becomes **Unfollow** (the button keeps its width). Click it: it turns blue **Follow** at once and **3 FOLLOWERS** becomes **2**; click it again: **Following** and **3**. |
| Click **3 FOLLOWERS** | `/u/part6_bo_<id>/followers`: **← Back to Bo Stone (@part6_bo_<id>)**, tabs **FOLLOWERS 3** (underlined) and **FOLLOWING 1**, and three rows (`fay`, `cy`, `ada`): avatar, `@name`, a **Follow** button on `fay` and `ada`, **none on your own row** (`cy`). |
| Click **FOLLOWING 1** | `/u/part6_bo_<id>/following`: one row, `cy`, with no button (it is your own row). |
| Open `/u/part6_ada_<id>` and click **Follow** | **Following** at once, and the **FOLLOWERS** counter goes up by one. Click again: it goes back. |
| Open `/u/part6_cy_<id>` (yourself) | **Edit profile** (a button that goes to `/settings`, a placeholder until Part 14) instead of Follow. |
| Open `/u/PART6_BO_<id>` in capitals | The address changes to the lower-case one. |
| Open `/u/nobody_here` | The "Page not found" page. |
| Log out and open `/u/part6_bo_<id>` | The same profile with a blue **Follow** link; clicking it goes to the log-in page and back to the profile afterwards. |

- Verified and FALSE count `bo`'s deleted post too, so they can be higher than the verified posts listed (step 7).

#### Step 13: The Following tab on /home

**Where:** Browser, logged in as `cy`.

**What this does:** Uses the second tab of the home feed. Recent stays the first tab and the default.

| Do this | Expect |
|---|---|
| Open http://localhost:3000/home | Two tabs, **RECENT** (underlined) and **FOLLOWING**. Logged out there is only **RECENT**. Opening `/home` makes no request for Following yet (DevTools → Network). |
| Click **FOLLOWING** | `bo`'s posts and your own, newest first, with the same cards as Recent; **You're caught up.** at the end. One request, `/api/v1/feed/`. Click **RECENT** and **FOLLOWING** again: no new request. |
| Click **New post** and post an opinion | It appears at the top of the open tab, and in the other tab too, without a reload. |
| Open `/u/part6_bo_<id>`, click **Following** to unfollow `bo`, then open `/home` and **FOLLOWING** | Only your own posts: `bo`'s are gone at once (the cache is cleared when you unfollow). |
| Log in with a brand-new account (no posts, no follows) and open **FOLLOWING** | **Follow people to see their posts here** with a **See Recent** button; the button switches to **RECENT**. |
| On a post card, click the author's name or avatar | Their profile opens. Clicking the claim text or empty space on the card still opens the post. |

#### Step 14: A phone-sized window

**Where:** Browser, logged in as `cy`.

**What this does:** Checks the new pages at phone width. In Firefox or Chrome press `F12`, then the "responsive
design" / device toolbar button, and set the width to 390.

| Do this | Expect |
|---|---|
| Open a profile | A top bar with the logo and your avatar; the profile card with the avatar and name side by side, the **Follow** button **below** them (not squeezed beside), the counters in a 2 by 2 grid; the chips; the posts. A bottom bar (Home, Search, New post, Notifications, Profile). **No sideways scrolling.** |
| Open `/followers` | Rows with the name truncated if long and the **Follow** button at the right. |
| Open `/home` and **FOLLOWING** | The two tabs under the top bar, the cards with the author's name and handle on one line. |

#### Step 15: Stop and clean up

**Where:** Every terminal window, plus the browser.

- Stop the servers: `Ctrl+C` in windows 1 and 3 (a leftover `next dev`: step 12 of Part 1).
- Delete the test accounts, their posts and their follows (all go with the accounts). In window 2, in `backend` with the
  venv active:

  ```bash
  python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(email__startswith='part6-').delete())" | tail -1
  ```

  After one clean run of this guide it prints `(22, {'posts.Post': 8, 'social.Follow': 4, 'account.EmailAddress': 5, 'accounts.User': 5})`:
  how many rows went in all, and per table (8 posts: seven by `bo`, six in steps 3 and 7 and one in step 8, and one by `ada` in step 8; a deleted
  post is still a row). Your count differs if you did the browser steps (more posts and follows). Nothing else is touched.
  (The E2E tests' accounts stay in your local database, as in earlier parts: Django Admin → Users deletes them.)
- `docker compose down` (repo root) stops the containers and keeps the data; `docker compose down -v`
  wipes the whole local database, which is destructive.
- No secret was used or printed in this part: the only values in the commands are Cloudflare's public test
  token and the throwaway password of the test accounts.

### Part 7: Likes & comments

Needs Part 0A's containers and virtualenv, Part 0C's frontend, and your own `backend/.env` and
`frontend/.env.local`. Part 7 adds **one migration** (`social.0002_like_comment`: the likes and comments tables), **no
dependency** and **no new variable** (the `like` and `comment` rates were already in the settings). It adds the
endpoints `POST` and `DELETE /api/v1/posts/{id}/like/`, `GET` and `POST /api/v1/posts/{id}/comments/` and
`DELETE /api/v1/comments/{id}/`, and fills `like_count`, `comment_count` and `liked_by_me` in every post.

**Which terminal window for what.** Open the windows once and keep using the same ones:

| Window | What runs in it | Used in steps |
|---|---|---|
| Window 1 (server) | `python manage.py runserver` in `backend`, venv active. Leave it running. Start it in step 3, **after** step 2 (Playwright starts its own servers and needs ports 3000 and 8000 free). | 3 to 16 |
| Window 2 (commands) | All the `curl` and `python manage.py` commands. **Use the same window for steps 3 to 12**: the variables and functions you set in step 3 (`id`, `ada`, `bo`, `cy`, `dee`, `api`, `op1`, `fact1`, `mk`, `get`, `send`, and the helpers steps 4 and 7 add) only live in that one terminal. If you close it, redo step 3. | 1 to 12, 17 |
| Window 3 (frontend) | `npm run dev` in `frontend`. Leave it running. | 13 to 16 |
| Browser | Steps 13 to 16 | 13 to 16 |

Things to know first:

- Steps 3 to 12 talk to the API directly with `curl` (they need `jq`: `sudo apt install jq`). Steps 13 to 16 use the
  browser. Step 3 makes four accounts: `ada`, `bo` and `cy` are verified and `dee` never is. `bo` writes the
  posts, `ada` and `cy` like and comment, and `dee` shows what an unverified email may not do. Step 11 adds `eve` and
  `gus` for the two rate limits.
- The API and page outputs below were recorded on Linux on 2026-10-10. The browser steps were checked the same
  day with headless Chromium (screenshots at 1280 and 390 px) and Django Admin with a scripted browser, not by a
  person at a keyboard. Ids, numbers in names, times and token prefixes differ on every run.
- Nothing here sends an email: step 3 marks the accounts verified with a shell command, which stands in for
  clicking the link (Part 2 shows the real flow). Steps 5, 9 and 10 set a post's status or hide a comment the same
  way, because the pipeline and the moderator tools that do it for real arrive in Parts 9 and 10 (step 16 uses
  the admin's own Hide action).
- **What Part 7 does and doesn't show:** likes and comments are allowed on every post the public can see
  (a fact that is still being checked included), never on a removed or deleted one; liking and commenting need a
  verified email, taking a like back or deleting your own comment only a login; a **hidden** comment (a
  moderator, in Django Admin) is in no list and no count, and deleting your own comment is a **soft delete**, so
  the row stays. Reposts and bookmarks (7B), reports (8) and notifications (13) come later.

#### Step 1: Run the automated backend checks

**Where:** Terminal window 2 (commands), starting in the repo root.

**What this does:** Starts the database containers, activates the Python environment, applies the new migration,
confirms there is no further one, then runs the whole backend test suite, the social tests, the linter and the
formatter check.

```bash
# start in the repo root
docker compose up -d
cd backend
source .venv/bin/activate
python manage.py migrate                            # Applying social.0002_like_comment... OK
python manage.py makemigrations --check --dry-run   # No changes detected
python manage.py check                              # System check identified no issues (0 silenced).
python -m pytest                                    # 1485 passed
python -m pytest apps/social -q                     # 305 passed
ruff check . ; ruff format --check .                # All checks passed! / 142 files already formatted
```

**You should see:** `Applying social.0002_like_comment... OK` (nothing to apply the second time), `No changes detected`
and `System check identified no issues (0 silenced).`, then the full run ends with `1485 passed`, the social run
with `305 passed`, and the last line pair is `All checks passed!` and `142 files already formatted`. (Counts may
grow later; what matters is that nothing fails.)

- The 145 new social tests: `test_models_engagement.py` (13: the unique like pair, a comment is 1 to 500 characters
  and an emoji is one, both indexes), `test_services_engagement.py` (26: idempotent like, who can like or comment
  on what, two simultaneous likes make one row, N simultaneous likes are all counted, two simultaneous deletes give
  one success), `test_api_like.py` (21, including the real 300-requests-an-hour limit), `test_api_comments.py` (22:
  oldest first, cursor walk, a comment arriving between pages, crafted cursors, constant query counts),
  `test_api_comment_create.py` (25, including the real 60-an-hour limit and that reading never uses it up),
  `test_api_comment_delete.py` (13), `test_engagement_counts.py` (11: real counts in Recent, the post page, a
  profile and the Following feed, also on a cache hit; constant queries), `test_admin_engagement.py` (13: Hide and
  Unhide, the permission, the admin log) and one more in `test_no_network.py`.
- Outside `apps/social`: the cursor check is tested for an oldest-first list too (`apps/core/tests/test_pagination.py`,
  4 new). `PostQuerySet.for_list(viewer)` now counts likes and comments, and `PostSerializer` refuses a post
  that was not counted (the 201 answer of a new post gets explicit zeros), so no list can show silent zeros.

#### Step 2: Run the automated frontend checks

**Where:** Terminal window 2, then `cd ../frontend`. Playwright (the last two commands) starts Django and
Next itself, so **no servers may be running on ports 3000 and 8000** (it reuses them if they are, with
whatever settings they have).

**What this does:** Runs the linters, the type check, the component tests, the production build and the
end-to-end tests.

```bash
cd ../frontend                                      # from backend/
npm run lint ; npm run lint:tokens ; npm run typecheck ; npm run format:check
npm test                                            # 106 files, 1410 tests passed
NEXT_PUBLIC_GOOGLE_CLIENT_ID= npm run build
npm run test:e2e                                    # 32 passed
CI=1 npm run test:e2e                               # 32 passed (against the production build)
cd ../backend                                       # back to backend/ for steps 3 to 12
```

**You should see:** the first line prints nothing from ESLint and TypeScript and ends with
`lint:tokens OK (…)` and `All matched files use Prettier code style!`. `npm test` ends with
`Test Files  106 passed (106)` and `Tests  1410 passed (1410)`. `npm run build` lists the same routes as in Part 6
(Part 7 adds no page: the discussion is part of `/p/[id]`). Each E2E run ends with `32 passed`: the 29 earlier tests
and 3 new ones in `e2e/social.spec.ts`.

- The new E2E tests reuse the two people that file already signs up (allauth limits sign-ups to 20 a minute per
  address and the rest of the suite already uses most of that), so Part 7 adds **no** sign-up. They are: B likes
  A's post from the feed (the heart fills and the count moves at once, the like survives a reload, A sees one like
  that isn't theirs), B opens the post, comments with Ctrl+Enter, A sees the comment with no Delete button, B
  deletes it after a confirmation and takes the like back; a visitor sees the counts and is sent to log in; and the
  post page with its discussion fits a phone with no sideways scroll.
- `posts.spec.ts` now expects three links on a card (the author, the claim and the comment count).

#### Step 3: Start the servers and make four accounts and two posts

**Where:** First window 1 (the Django server) and window 3 (the frontend), then window 2 (the commands).
**Keep using window 2 for steps 4 to 12.**

**What this does:** Windows 1 and 3 run the two servers. In window 2 you sign up four accounts through the API and
mark three of them verified (`dee` stays unverified), then `bo` posts an opinion and a fact with a DOI. The helpers
`mk` (make a post, print its id), `send` (any request, printing the status code and then the answer) and `get` (the same for a GET) are used by every later step.

Window 1 (in `backend`, venv active):

```bash
python manage.py runserver                          # leave it running
```

Window 3:

```bash
cd frontend                                         # from the repo root
npm run dev                                         # leave it running
```

Window 2 (in `backend` with the venv active: steps 1 and 2 leave you there; needs `jq`). If you opened a new
terminal, first run `cd backend` from the repo root and `source .venv/bin/activate`:

```bash
id=$(date +%H%M%S)                                  # a unique suffix so the addresses are new each run
h=(-H 'Origin: http://localhost:3000' -H 'X-Requested-With: rumor-zero')   # headers every auth call needs
signup() { jq -nc --arg e "$1" --arg u "$2" '{email: $e, username: $u, password: "correct-horse-battery-42", turnstile_token: "XXXX.DUMMY.TOKEN.XXXX"}' | curl -s "${h[@]}" -H "Content-Type: application/json" --data-binary @- http://localhost:8000/api/auth/app/v1/auth/signup | jq -r .meta.access_token; }
ada=$(signup "part7-ada-$id@example.test" "part7_ada_$id")      # $ada = ada's login token (likes and comments)
bo=$(signup "part7-bo-$id@example.test" "part7_bo_$id")         # $bo = bo's login token (the author of the posts)
cy=$(signup "part7-cy-$id@example.test" "part7_cy_$id")         # $cy = cy's login token (kept for the browser)
dee=$(signup "part7-dee-$id@example.test" "part7_dee_$id")      # $dee = dee's login token (never verified)
python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(email__startswith='part7-', email__endswith='$id@example.test').exclude(username='part7_dee_$id').update(is_email_verified=True), 'accounts marked verified')" | tail -1
api=http://localhost:8000/api/v1
adaname=part7_ada_$id; boname=part7_bo_$id; cyname=part7_cy_$id; deename=part7_dee_$id
mk() { curl -s -H "Authorization: Bearer $1" -H "Content-Type: application/json" --data-binary "$2" $api/posts/ | jq -r .id; }   # mk <token> <json>: makes a post, prints its id
get() { local out; out=$(curl -s -w '\n%{http_code}' ${2:+-H "Authorization: Bearer $2"} "$api$1"); printf '%s  ' "${out##*$'\n'}"; printf '%s' "${out%$'\n'*}" | jq -c "${3:-.}"; }   # get <path> [token] [jq filter]: prints the status code, then the answer
send() { local out; out=$(curl -s -w '\n%{http_code}' -X "$1" ${3:+-H "Authorization: Bearer $3"} ${4:+-H "Content-Type: application/json" --data-binary "$4"} "$api$2"); printf '%s  %s\n' "${out##*$'\n'}" "$(printf '%s' "${out%$'\n'*}" | jq -c "${5:-.}" 2>/dev/null)"; }   # send <METHOD> <path> [token] [json body] [jq filter]: prints the status code, then the answer
op1=$(mk "$bo" '{"content":"I think the new tram line will change how the city moves.","post_type":"opinion"}')
fact1=$(mk "$bo" '{"content":"Solar capacity grew by roughly 30% worldwide last year.","post_type":"fact","sources":["doi:10.1038/s41558-024-02102"]}')
echo ${ada:0:10} ${bo:0:10} ${cy:0:10} ${dee:0:10}    # four prefixes, not an empty line
echo "op1=$op1"; echo "fact1=$fact1"                 # two ids, not empty
```

**You should see** (the number in the names is your `id`, and the ids differ):

```text
3 accounts marked verified
eyJhbGciOi eyJhbGciOi eyJhbGciOi eyJhbGciOi
op1=c4cd330c-ef91-4ef8-a888-f016ae6e4905
fact1=ba591060-ab33-405d-b077-0ef99a789ebe
```

- The shell prints a line about auto-imported objects first; `tail -1` keeps only ours.
- Sign-up is limited to 20 a minute per address (Part 1), and still calls Cloudflare's test widget, so it
  needs internet.

**If it differs:** an empty token or an `id` of `null` means the sign-up or the post failed: `runserver` isn't
running, `jq` is missing, or you signed up more than 20 times in a minute. Fix that and run this step again
from `id=$(date +%H%M%S)`.

#### Step 4: Like and unlike

**Where:** Terminal window 2 (the same terminal as step 3).

**What this does:** Likes and unlikes through `POST` and `DELETE /api/v1/posts/{id}/like/`, with every refusal.
Both are idempotent. Liking needs a verified email, taking a like back only a login.

```bash
like() { send POST /posts/$1/like/ "$2"; }          # like <post id> [token]
unlike() { send DELETE /posts/$1/like/ "$2"; }      # unlike <post id> [token]
like $op1 "$ada"                                    # 1: the first like is 201
like $op1 "$ada"                                    # 2: again: 200, nothing changes
like $op1                                           # 3: nobody logged in
like $op1 "$dee"                                    # 4: an unverified email
like $op1 "$bo"                                     # 5: your own post is fine
like $fact1 "$ada"                                  # 6: a fact that is still "checking" can be liked
like 00000000-0000-4000-8000-000000000000 "$ada"    # 7: no such post
like not-a-uuid "$ada"                              # 8: not even an id
unlike $op1 "$bo"                                   # 9: taking your like back is 204
unlike $op1 "$bo"                                   # 10: and again: still 204, no error
unlike $op1 "$dee"                                  # 11: an unverified user may also take one back (there is none): 204
```

**You should see** (eleven commands, eleven answers):

```text
201  {"liked":true}
200  {"liked":true}
401  {"detail":"Authentication credentials were not provided.","code":"not_authenticated"}
403  {"detail":"Verify your email address first. Check your inbox for the link.","code":"email_unverified"}
201  {"liked":true}
201  {"liked":true}
404  {"detail":"Not found.","code":"not_found"}
404  {"detail":"Not found.","code":"not_found"}
204
204
204
```

- The first like is `201`, the same request again is `200` and changes nothing; `DELETE` is `204` every
  time, also when there was nothing to take back (10, 11). A user can like their own post (5).
- A fact post still labelled "checking facts" can be liked (6), like an opinion or a post under review: only a
  removed or deleted post can't (step 5). An unknown or malformed id is the same JSON 404 (7, 8), never an HTML page.
- A 401 or 403 doesn't use up the allowance of 300 likes an hour (step 11).

#### Step 5: Removed and deleted posts

**Where:** Terminal window 2.

**What this does:** Makes two more posts, one a moderator removes (set with a shell command: the moderator tools
come in Part 10) and one its author deletes, and shows that neither can be liked.

```bash
op2=$(mk "$bo" '{"content":"This opinion will be removed by a moderator.","post_type":"opinion"}')
python manage.py shell -c "from apps.posts.models import Post; print(Post.objects.filter(pk='$op2').update(status='removed'), 'post removed')" | tail -1
op3=$(mk "$bo" '{"content":"This opinion will be deleted by its author.","post_type":"opinion"}')
send DELETE /posts/$op3/ "$bo"                      # bo deletes op3: 204
like $op2 "$ada"                                    # 1: a removed post can't be liked
like $op3 "$ada"                                    # 2: a deleted post can't either
python manage.py shell -c "from apps.social.models import Like; from apps.accounts.models import User; Like.objects.create(user=User.objects.get(username='$adaname'), post_id='$op2'); print(Like.objects.filter(post_id='$op2').count(), 'like row planted on the removed post')" | tail -1
unlike $op2 "$ada"                                  # 3: ...but a like can still be taken back from it: 204
python manage.py shell -c "from apps.social.models import Like; print(Like.objects.filter(post_id='$op2').count(), 'like rows left on it')" | tail -1
unlike $op3 "$ada"                                  # 4: a deleted post is 404 even for that
```

**You should see:**

```text
1 post removed
204
404  {"detail":"Not found.","code":"not_found"}
404  {"detail":"Not found.","code":"not_found"}
1 like row planted on the removed post
204
0 like rows left on it
404  {"detail":"Not found.","code":"not_found"}
```

- `post removed` is the shell command; `204` is `bo` deleting `op3`; then the two refusals (1, 2) are plain
  `404`s, the same answer as for a post that never existed, so nothing says whether a post once existed.
- A like that was already on a post can always be taken back, even if the post was removed meanwhile (3 to
  the `0 like rows left` line), but a deleted post is `404` for that too (4).

#### Step 6: The counts on every post

**Where:** Terminal window 2.

**What this does:** Reads `like_count`, `comment_count` and `liked_by_me` as nobody and as other people, on the post
page and in three lists. The counts are counted in the same query as the posts, so a list of 20 posts costs the same
number of queries as a list of 2. The last three commands show the Following feed, whose first page is cached for
30 seconds as a list of ids only: a new like still shows at once.

```bash
get /posts/$op1/ "" '{like_count, comment_count, liked_by_me}'      # 1: a visitor: ada's like counts, "mine" is false
get /posts/$op1/ "$ada" '{like_count, comment_count, liked_by_me}'  # 2: ada: she liked it
get /posts/$op1/ "$cy" '{like_count, comment_count, liked_by_me}'   # 3: cy: someone else liked it, he didn't
get "/posts/?page_size=2" "$ada" '[.results[].post | {content: .content[0:24], like_count, liked_by_me}]'   # 4: the Recent feed: the same numbers
get "/users/$boname/posts/?page_size=2" "$ada" '[.results[].post | {content: .content[0:24], like_count, liked_by_me}]'   # 5: bo's profile posts
send POST /users/$boname/follow/ "$ada" '' '.'      # 6: ada follows bo, so the Following feed has bo's posts
get /feed/ "$ada" '[.results[].post | {content: .content[0:24], like_count}] | .[0:2]'     # 7: the Following feed: page 1 is now cached (ids only)
like $op1 "$cy"                                     # 8: one more like arrives
get /feed/ "$ada" '[.results[].post | {content: .content[0:24], like_count}] | .[0:2]'     # 9: still cached, but the count is fresh
```

**You should see:**

```text
200  {"like_count":1,"comment_count":0,"liked_by_me":false}
200  {"like_count":1,"comment_count":0,"liked_by_me":true}
200  {"like_count":1,"comment_count":0,"liked_by_me":false}
200  [{"content":"Solar capacity grew by r","like_count":1,"liked_by_me":true},{"content":"I think the new tram lin","like_count":1,"liked_by_me":true}]
200  [{"content":"Solar capacity grew by r","like_count":1,"liked_by_me":true},{"content":"I think the new tram lin","like_count":1,"liked_by_me":true}]
201  {"is_following":true}
200  [{"content":"Solar capacity grew by r","like_count":1},{"content":"I think the new tram lin","like_count":1}]
201  {"liked":true}
200  [{"content":"Solar capacity grew by r","like_count":1},{"content":"I think the new tram lin","like_count":2}]
```

- `liked_by_me` is `false` for a visitor and for everyone who didn't like the post (1, 3), `true` for `ada` (2).
  `like_count` is the same for everyone.
- Lines 4 and 5 list the two newest posts, the fact and the opinion `bo` made in step 3 (the removed and the deleted
  one are left out): both show `ada`'s like. Hidden and deleted comments are never counted in `comment_count`
  (step 10).
- Line 7 is the Following feed, now cached for `ada`; line 9 is the same page a moment later: the cache keeps the
  post ids, not the posts, so the count rose from 1 to 2.

#### Step 7: Write comments

**Where:** Terminal window 2.

**What this does:** Writes comments through `POST /api/v1/posts/{id}/comments/` and tries everything that is
refused. A comment is 1 to 500 characters (an emoji counts as one), trimmed, and needs a verified email.

```bash
comment() { send POST /posts/$1/comments/ "$2" "$(jq -nc --arg c "$3" '{content: $c}')" "${4:-.}"; }   # comment <post id> <token> <text> [jq filter]
comment $op1 "$ada" "  A fair point.  " '{content, is_mine, author: .author.username, keys: keys}'   # 1: 201, the text is trimmed
comment $op1 "$bo" "Thanks, ada." '{content, is_mine}'    # 2: the post's own author may comment
comment $op1 "$cy" "Third." '.content'                    # 3: a third comment
comment $op1 "" "Hi" '.'                                  # 4: nobody logged in
comment $op1 "$dee" "Hi" '.'                              # 5: an unverified email
comment $op1 "$ada" "" '.'                                # 6: nothing written
comment $op1 "$ada" "   " '.'                             # 7: only spaces
comment $op1 "$ada" "$(head -c 501 /dev/zero | tr '\0' x)" '.'                  # 8: 501 characters
comment $fact1 "$ada" "$(printf '😀%.0s' $(seq 500))" '.content | length'      # 9: 500 emoji = 500 characters: fine, on a fact still being checked
comment $op2 "$ada" "Hi" '.'                              # 10: a removed post has no discussion
comment 00000000-0000-4000-8000-000000000000 "$ada" "Hi" '.'                    # 11: no such post
```

**You should see** (eleven commands, eleven answers):

```text
201  {"content":"A fair point.","is_mine":true,"author":"part7_ada_190101","keys":["author","content","created_at","id","is_mine"]}
201  {"content":"Thanks, ada.","is_mine":true}
201  "Third."
401  {"detail":"Authentication credentials were not provided.","code":"not_authenticated"}
403  {"detail":"Verify your email address first. Check your inbox for the link.","code":"email_unverified"}
400  {"content":["Write something first."]}
400  {"content":["Write something first."]}
400  {"content":["Keep it to 500 characters."]}
201  500
404  {"detail":"Not found.","code":"not_found"}
404  {"detail":"Not found.","code":"not_found"}
```

- A comment has exactly five keys: `id`, `author`, `content`, `is_mine` and `created_at`. Nothing about moderation
  ever shows. The spaces around the text are gone (1).
- `400` answers come per field in the same words as a post's: "Write something first." for nothing or only
  spaces (6, 7) and "Keep it to 500 characters." for 501 (8). 500 emoji is 500 characters, not 1000 (9).
- The refusals for nobody logged in, an unverified email, a removed post and no such post are the same as for likes.

#### Step 8: Read the comments

**Where:** Terminal window 2.

**What this does:** Reads `GET /api/v1/posts/{id}/comments/`: public, **oldest first**, 20 to a page (`?page_size=`
up to 50), with a cursor to carry on.

```bash
get /posts/$op1/comments/ "" '{order: [.results[].content], keys: (.results[0] | keys), next_cursor}'   # 1: anyone can read; oldest first
get /posts/$op1/comments/ "$ada" '[.results[] | {content, is_mine}]'                                     # 2: ada's own comment says so
cur=$(curl -s "$api/posts/$op1/comments/?page_size=2" | jq -r .next_cursor)
get "/posts/$op1/comments/?page_size=2" "" '[.results[].content, (.next_cursor != null)]'                 # 3: a page of two, and a way on
get "/posts/$op1/comments/?page_size=2&cursor=$cur" "" '[.results[].content, .next_cursor]'               # 4: the last one, then no cursor
get "/posts/$op1/comments/?cursor=cD1ub3QtYS1kYXRl" "" .                                                  # 5: a made-up cursor
get /posts/$op2/comments/ "" .                                                                           # 6: removed post
get /posts/$op3/comments/ "" .                                                                           # 7: deleted post
get /posts/$op1/ "" '{comment_count, like_count}'                                                        # 8: the counts on the post
```

**You should see** (eight commands, eight answers):

```text
200  {"order":["A fair point.","Thanks, ada.","Third."],"keys":["author","content","created_at","id","is_mine"],"next_cursor":null}
200  [{"content":"A fair point.","is_mine":true},{"content":"Thanks, ada.","is_mine":false},{"content":"Third.","is_mine":false}]
200  ["A fair point.","Thanks, ada.",true]
200  ["Third.",null]
404  {"detail":"Invalid cursor","code":"not_found"}
404  {"detail":"Not found.","code":"not_found"}
404  {"detail":"Not found.","code":"not_found"}
200  {"comment_count":3,"like_count":2}
```

- Anyone can read (1). The order is the order they were written. Only `ada`'s own comment says `is_mine: true`
  when she asks (2).
- Line 3 is a page of two and `true`: there is more; line 4 follows the cursor and gets the last comment, then
  `null`. A comment that arrives between two pages is neither skipped nor repeated (a test covers it).
- A made-up cursor is a clean `404 "Invalid cursor"`, never a server error. A removed or deleted post has no
  comment list at all (6, 7), not even for its author.

#### Step 9: Delete your own comment

**Where:** Terminal window 2.

**What this does:** Deletes a comment through `DELETE /api/v1/comments/{id}/`. It is a **soft delete**: the comment
leaves every list and count, but the row stays in the database (the last command shows it).

```bash
cid=$(curl -s $api/posts/$op1/comments/ | jq -r '.results[1].id')    # bo's comment (the second one)
send DELETE /comments/$cid/ ""                      # 1: nobody logged in
send DELETE /comments/$cid/ "$ada"                  # 2: someone else's comment
send DELETE /comments/$cid/ "$bo"                   # 3: its author: 204
send DELETE /comments/$cid/ "$bo"                   # 4: again: it is gone, 404
get /posts/$op1/ "" '{comment_count}'               # 5: the count dropped
get /posts/$op1/comments/ "" '[.results[].content]' # 6: and so did the list
python manage.py shell -c "from apps.social.models import Comment; c = Comment.objects.get(pk='$cid'); print(repr(c.content), '| deleted_at set:', c.deleted_at is not None, '| hidden:', c.is_hidden)" | tail -1   # 7: the row is still there
```

**You should see:**

```text
401  {"detail":"Authentication credentials were not provided.","code":"not_authenticated"}
403  {"detail":"Only the author can do that.","code":"not_author"}
204
404  {"detail":"Not found.","code":"not_found"}
200  {"comment_count":2}
200  ["A fair point.","Third."]
'Thanks, ada.' | deleted_at set: True | hidden: False
```

- Only the author can delete: someone else gets `403 not_author` (2), and so does the author of the *post*.
  Deleting needs no verified email. The second delete is `404` (4), as for posts.
- The count and the list lose the comment at once (5, 6), and the row is still there with `deleted_at` set (7),
  like a deleted post.

#### Step 10: What a moderator's Hide does

**Where:** Terminal window 2.

**What this does:** Hides one comment with a shell command, which is what the admin's **Hide** action does (step 16
uses the real one), and shows that a hidden comment is gone for everyone, its author included, and not counted.

```bash
aid=$(curl -s $api/posts/$op1/comments/ | jq -r '.results[0].id')    # ada's comment (now the first)
python manage.py shell -c "from apps.social.models import Comment; print(Comment.objects.filter(pk='$aid').update(is_hidden=True), 'comment hidden')" | tail -1   # what the admin's Hide action does
get /posts/$op1/comments/ "$ada" '[.results[].content]'     # 1: gone from the list, even for its own author
get /posts/$op1/ "" '{comment_count}'                       # 2: and not counted
send DELETE /comments/$aid/ "$ada"                          # 3: its author can't delete it any more
python manage.py shell -c "from apps.social.models import Comment; print(Comment.objects.filter(pk='$aid').update(is_hidden=False), 'comment unhidden')" | tail -1   # Unhide
get /posts/$op1/comments/ "" '[.results[].content]'         # 4: back in its place
get /posts/$op1/ "" '{comment_count}'                       # 5: and counted again
```

**You should see:**

```text
1 comment hidden
200  ["Third."]
200  {"comment_count":1}
404  {"detail":"Not found.","code":"not_found"}
1 comment unhidden
200  ["A fair point.","Third."]
200  {"comment_count":2}
```

- Hidden means in no list and no count, for everyone (1, 2); staff see it only in Django Admin. Its author
  can't delete it any more (3): to them it no longer exists.
- Unhiding puts it back in its place, and the count goes back up (4, 5).

#### Step 11: Liking and commenting are rate limited

**Where:** Terminal window 2.

**What this does:** Makes two more verified accounts and a post, then uses up their allowances: 300 likes an hour
(`POST` and `DELETE` share it) and 60 comments an hour (only `POST` counts; reading never does).

```bash
eve=$(signup "part7-eve-$id@example.test" "part7_eve_$id")      # $eve = a fresh account for the like limit
gus=$(signup "part7-gus-$id@example.test" "part7_gus_$id")      # $gus = a fresh account for the comment limit
python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(email__in=['part7-eve-$id@example.test', 'part7-gus-$id@example.test']).update(is_email_verified=True), 'accounts marked verified')" | tail -1
op4=$(mk "$bo" '{"content":"A post for the limits to chew on.","post_type":"opinion"}')
for i in $(seq 1 300); do curl -s -o /dev/null -w '%{http_code}\n' -X POST -H "Authorization: Bearer $eve" $api/posts/$op4/like/; done | sort | uniq -c   # 300 likes of one post
curl -s -i -X POST -H "Authorization: Bearer $eve" $api/posts/$op4/like/ | grep -ioE 'HTTP/[0-9.]+ [0-9]+|retry-after: [0-9]+|"code":"[a-z_]+"'              # the 301st
for i in $(seq 1 60); do curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $gus" -H "Content-Type: application/json" --data-binary "{\"content\":\"Limit test $i\"}" $api/posts/$op4/comments/; done | sort | uniq -c   # 60 comments
curl -s -i -H "Authorization: Bearer $gus" -H "Content-Type: application/json" --data-binary '{"content":"One too many"}' $api/posts/$op4/comments/ | grep -ioE 'HTTP/[0-9.]+ [0-9]+|retry-after: [0-9]+|"code":"[a-z_]+"'   # the 61st
get /posts/$op4/comments/ "$gus" '{n: (.results | length)}'                  # reading is never throttled
```

**You should see** (the seconds differ):

```text
2 accounts marked verified
    299 200
      1 201
HTTP/1.1 429
Retry-After: 3597
"code":"throttled"
     60 201
HTTP/1.1 429
Retry-After: 3600
"code":"throttled"
200  {"n":20}
```

- 300 requests went through (the first made the like, the other 299 were repeats), the 301st was refused with `429`,
  `"code":"throttled"` and a `Retry-After` in seconds. Likewise 60 comments, then the 61st.
- A 401 or 403 doesn't use up an allowance, but a `400` for a bad comment does (tests cover both).
- Reading the comments still works while the comment allowance is spent: the last answer shows the page of 20.

#### Step 12: The indexes are used

**Where:** Terminal window 2.

**What this does:** In a transaction that is thrown away at the end, makes 300 users, 2,000 posts, 40,000 comments and
30,000 likes, asks the database how it would run the three queries behind every card and prints the plan lines. Nothing is
saved.

```bash
python manage.py shell <<'EOF' 2>&1 | grep -E "^---|Scan|rolled back"
from datetime import timedelta
from django.db import connection, transaction
from django.utils import timezone
from apps.accounts.models import User
from apps.posts.models import Post
from apps.social.models import Comment, Like

class Rollback(Exception):
    pass

try:
    with transaction.atomic():   # everything below is thrown away at the end
        users = User.objects.bulk_create([User(username=f"xp_{i:03d}", email=f"xp{i}@example.test") for i in range(300)])
        now = timezone.now()
        posts = Post.objects.bulk_create([Post(author=users[i % 300], content=f"p{i}", post_type="opinion", status="published", created_at=now - timedelta(seconds=i)) for i in range(2000)])
        Comment.objects.bulk_create([Comment(post=posts[n % 200], author=users[n % 300], content="c", created_at=now - timedelta(seconds=n), is_hidden=(n % 50 == 0), deleted_at=(now if n % 70 == 0 else None)) for n in range(40000)])
        Like.objects.bulk_create([Like(user=users[n % 300], post=posts[(n // 300) % 2000]) for n in range(30000)], ignore_conflicts=True)
        with connection.cursor() as c:
            for table in ("social_comment", "social_like", "posts_post"):
                c.execute(f"ANALYZE {table}")
            target = str(posts[7].pk)
            for label, sql in {
                "--- comment list, first page": "SELECT id FROM social_comment WHERE post_id = %s AND NOT is_hidden AND deleted_at IS NULL ORDER BY created_at, id LIMIT 21",
                "--- comment count": "SELECT COUNT(*) FROM social_comment WHERE post_id = %s AND NOT is_hidden AND deleted_at IS NULL",
                "--- like count": "SELECT COUNT(*) FROM social_like WHERE post_id = %s",
            }.items():
                c.execute("EXPLAIN " + sql, [target])
                print(label)
                for row in c.fetchall():
                    print(row[0])
        raise Rollback
except Rollback:
    print("rolled back: nothing was saved")
EOF
```

**You should see** (the cost numbers differ a little):

```text
--- comment list, first page
  ->  Index Only Scan using comments_post_visible_idx on social_comment  (cost=0.41..595.39 rows=170 width=24)
--- comment count
  ->  Bitmap Heap Scan on social_comment  (cost=17.73..353.09 rows=170 width=0)
        ->  Bitmap Index Scan on comments_post_visible_idx  (cost=0.00..17.69 rows=170 width=0)
--- like count
  ->  Bitmap Heap Scan on social_like  (cost=22.61..319.28 rows=300 width=0)
        ->  Bitmap Index Scan on likes_post_created_idx  (cost=0.00..22.54 rows=300 width=0)
rolled back: nothing was saved
```

- The comment list reads `comments_post_visible_idx` straight in order (an index-only scan): that index only holds
  comments that are shown (not hidden, not deleted), and the count uses it too. The like count uses
  `likes_post_created_idx`.
- Each post card counts its own likes and comments with these two queries; a count costs about as many index entries
  as the post has comments, which is fine for now. (A post with many thousands of likes would want a stored counter:
  recorded for Part 16.)

#### Step 13: Likes on the cards

**Where:** Browser, with `runserver` (window 1) and `npm run dev` (window 3) running. Log in at
http://localhost:3000/login as `part7-cy-<id>@example.test` (use the `id` from step 3: `echo $id`) with the password `correct-horse-battery-42` (`cy` was verified in step 3).

**What this does:** Looks at the like and comment buttons on the Recent feed, as three kinds of visitor.

| Do this | Expect |
|---|---|
| Open http://localhost:3000/home and look at the posts `bo` made | Every card ends with a hairline and two small buttons: a **heart** with the like count and a **speech bubble** with the comment count. The solar fact card shows `1` and `1`; "A post for the limits to chew on." shows `1` and `60` (step 11); the tram opinion shows a **filled blue heart** and `2` (`cy` liked it in step 6) and `2` comments. Counts of 1,000 and more print as `1.4K`. |
| Click the filled heart on the tram card | It turns into an outline heart and the count goes `2` to `1` **at once**, before the server answers. Click again: filled, `2`. |
| Press `Tab` until a heart has the focus, then `Enter` or `Space` | The same toggle. A focused button has a thin blue ring. |
| Reload the page | The heart and the numbers are what the server says: the state survived. |
| Click the speech bubble | The post's own page opens, scrolled to the **Comments** section (`/p/<id>#comments`). Clicking the claim text opens the same page from the top. |
| Open a private window and go to /home (a visitor) | The same cards with the same counts. The hearts are **links**: they point to `/login?next=%2Fp%2F<id>`, and after you log in you land on that post's page. |
| In another window log in as `dee` (`part7-dee-<id>@example.test`, same password: never verified) and click a heart | The heart looks dimmed and nothing is sent; a toast says "Verify your email to like posts. Check your inbox for the link." |

- Covered by `LikeButton.test.tsx` (flip before the answer, rollback and toast on every kind of failure, one
  request for two clicks in one tick, all four visitor states) and the new E2E tests.
- The heart on a card is always above the card's big invisible link, so it never opens the post by accident.

#### Step 14: The discussion on a post's page

**Where:** Browser, logged in as `cy`, with both servers running.

**What this does:** Opens the tram post and uses the Comments section.

| Do this | Expect |
|---|---|
| Open the tram post (click its text on /home) and scroll below the verdict | The heading **Comments (2)** with OLDEST FIRST at the right, a box "Add a comment…" with `0 / 500 characters`, the hint "Ctrl + Enter to post" and a blue **Comment** button; below it `ada`'s "A fair point." and then `cy`'s "Third.". Only `cy`'s own comment has a small **DELETE**. (`bo`'s was deleted in step 9.) |
| Look at the row next to **Copy link** | The heart and the speech bubble with the words "Like" and "Comments" beside their counts (the words show from 640 px up). Clicking "Comments" jumps down to the section. |
| Type a line (the counter moves), then press `Ctrl+Enter` (`Cmd+Enter` on a Mac) | Your comment appears at the **end** of the list with "now", the heading says **Comments (3)**, the box is empty and keeps the focus, and a toast says "Comment posted." |
| Click **Comment** with the box empty, or only spaces | "Write something first." under the box; nothing is sent. |
| Paste a text of 501 characters, then click **Comment** | The counter turns red (`501 / 500 characters`) and the message is "Keep it to 500 characters."; nothing is sent. |
| Click **DELETE** under your own comment | A dialog "Delete this comment?" says "It disappears from the discussion right away. This can't be undone." **Cancel** closes it and nothing happens. **Delete comment** removes the row, the heading goes back to **Comments (2)** and a toast says "Comment deleted." |
| Open the same page in a private window (a visitor) | The comments are readable, there is no box, and a link says "Log in to comment" (to join the discussion). |
| Log in as `dee` (unverified) and open the page | The box is greyed out and locked, with the note "Verify your email to comment." |
| Open a removed post's page (not available from the UI: try `/p/<op2>`) | The tombstone with no discussion at all, for anyone, its author too. |

- Covered by `CommentComposer.test.tsx`, `CommentSection.test.tsx` (including the StrictMode case that once hid
  the author's Delete button on posts), `CommentList.test.tsx`, `DeleteCommentModal.test.tsx` and the E2E tests.
- The comments are fetched by the page after it loads (not server-rendered): `curl` of `/p/<id>` still gets the
  claim, the tags and the counts, but not the comment texts.

#### Step 15: A phone-sized window

**Where:** Browser, logged in as `cy`.

**What this does:** Checks the new parts at phone width. In Firefox or Chrome press `F12`, then the "responsive
design" / device toolbar button, and set the width to 390.

| Do this | Expect |
|---|---|
| Open /home | Each card's bar (heart, count, bubble, count) fits on one line under the claim. **No sideways scrolling.** |
| Open a post's page | The claim card's action row holds the heart and the speech bubble with their counts only (the words are hidden below 640 px) and **Copy link** beside them; the comment box is full width with the counter under it and the **Comment** button at the right; each comment is a card with the name, the time, the text and **DELETE**. |
| Type 300 characters into the box | Still **no sideways scrolling.** |

- Measured with headless Chromium at 390 px: 0 px of horizontal overflow on `/home`, on a post's page and with 300
  characters typed.

#### Step 16: Django Admin hides and unhides comments

**Where:** Browser, while `runserver` is running in window 1.

**What this does:** Opens the admin list of comments and uses the two new actions, the way a moderator will.

| URL / action | Expect |
|---|---|
| http://localhost:8000/admin/ | Sign in with the superuser you made in Part 0A. If it 404s, `ADMIN_URL_PATH` in `backend/.env` isn't `admin/`; use that path. |
| http://localhost:8000/admin/social/comment/ | **Comments**: the text (shortened), author, post, **Is hidden**, **Deleted at** and **Created at**, newest first, with a search box (text and username), the filters **By is hidden**, **By deleted at** and **By created at**, and the **Action** menu with "Hide selected comments" and "Unhide selected comments". There is no **Add comment** button. The comments you deleted in the browser are there with a date in **Deleted at**: the rows survived. |
| Click a comment | A page that only shows the values: no Save and no Delete (they answer 403 if you type the address). |
| Tick one comment of the tram post, choose **Hide selected comments**, click **Go** | A banner says "Hidden: 1 comment." Reload the tram post's page: the comment is gone from the list and the heading is one lower; the public list from step 8 no longer has it either. |
| Open the filter **By is hidden → Yes**, tick it, choose **Unhide selected comments**, click **Go** | "Unhidden: 1 comment." The comment is back in the discussion. Ticking one that is already in that state changes nothing ("Hidden: 0 comments."). |
| http://localhost:8000/admin/social/like/ | **Likes**: user, post and time, read-only like the follows. |

- Both actions need the `social.change_comment` permission. Today only a superuser has it; Part 10 gives it to the
  Moderators group. A staff member without it sees the list but is not offered the actions (a test covers that).
- Each change is written to Django's own admin log (the comment, who and "Hidden" or "Unhidden"): the moderation
  actions table arrives in Part 10 and has no comment kind. **Unhide** doesn't undelete a comment its author deleted.
- Covered by `test_admin_engagement.py` and, for these clicks, a scripted browser run; not clicked by a person.

#### Step 17: Stop and clean up

**Where:** Every terminal window, plus the browser.

- Stop the servers: `Ctrl+C` in windows 1 and 3 (a leftover `next dev`: step 12 of Part 1).
- Delete the test accounts, their posts, follows, likes and comments (all go with the accounts). In window 2, in `backend` with the
  venv active:

  ```bash
  python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(email__startswith='part7-').delete())" | tail -1
  ```

  After one clean run of steps 3 to 12 of this guide it prints `(86, {'social.Like': 4, 'social.Comment': 64, 'social.Follow': 1, 'account.EmailAddress': 6, 'posts.Post': 5, 'accounts.User': 6})`:
  how many rows went in all, and per table (5 posts by `bo`: the tram opinion, the fact, the removed one, the
  deleted one and the limits post, and a deleted post is still a row; 64 comments: 3 on the tram post, 1 on the fact
  and 60 on the limits post, the deleted and the hidden-then-unhidden one included; 4 likes: `ada` and `cy` on
  the tram post, `ada` on the fact and `eve` on the limits post, `bo`'s was taken back). Your count differs if you did the browser steps
  (more comments and likes). Nothing else is touched.
  (The E2E tests' accounts stay in your local database, as in earlier parts: Django Admin → Users deletes them.)
  If you made a throwaway superuser for step 16, delete that too.
- `docker compose down` (repo root) stops the containers and keeps the data; `docker compose down -v`
  wipes the whole local database, which is destructive.
- No secret was used or printed in this part: the only values in the commands are Cloudflare's public test
  token and the throwaway password of the test accounts.

### Part 7B: Bookmarks & reposts

Needs Part 0A's containers and virtualenv, Part 0C's frontend, and your own `backend/.env` and
`frontend/.env.local`. Part 7B adds **one migration** (`social.0003_repost_bookmark`: the reposts and bookmarks tables),
**no dependency** and **no new variable** (the `repost` and `bookmark` rates were already in the settings). It adds the
endpoints `POST` and `DELETE /api/v1/posts/{id}/repost/` and `…/bookmark/` and `GET /api/v1/me/bookmarks/`, fills
`repost_count`, `reposted_by_me` and `bookmarked_by_me` in every post, and turns the Following feed and the profile
lists into **mixed lists of posts and reposts**.

**Which terminal window for what.** Open the windows once and keep using the same ones:

| Window | What runs in it | Used in steps |
|---|---|---|
| Window 1 (server) | `python manage.py runserver` in `backend`, venv active. Leave it running. Start it in step 3, **after** step 2 (Playwright starts its own servers and needs ports 3000 and 8000 free). | 3 to 18 |
| Window 2 (commands) | All the `curl` and `python manage.py` commands. **Use the same window for steps 3 to 13**: the variables and functions you set in step 3 (`id`, `ada`, `bo`, `cy`, `dee`, `api`, `op1`, `fact1`, `adapost`, `mk`, `get`, `send`, and the helpers later steps add) only live in that one terminal. If you close it, redo step 3. | 1 to 13, 19 |
| Window 3 (frontend) | `npm run dev` in `frontend`. Leave it running. | 14 to 18 |
| Browser | Steps 14 to 18 | 14 to 18 |

Things to know first:

- Steps 3 to 13 talk to the API directly with `curl` (they need `jq`: `sudo apt install jq`). Steps 14 to 18 use the
  browser. Step 3 makes four accounts: `ada`, `bo` and `cy` are verified and `dee` never is. `bo` writes the
  posts, `ada` reposts and bookmarks them, `cy` follows `ada` (and later `bo`) and reads the Following feed, and
  `dee` shows what an unverified email may not do. Step 12 adds `eve` and `gus` for the two rate limits.
- The API and page outputs below were recorded on Linux on 2026-10-10. The browser steps were checked the same
  day with headless Chromium (screenshots at 1280 and 390 px) and Django Admin with a scripted browser, not by a
  person at a keyboard. Ids, numbers in names, times and token prefixes differ on every run.
- Nothing here sends an email: step 3 marks the accounts verified with a shell command, which stands in for
  clicking the link (Part 2 shows the real flow). Steps 5, 8 and 10 set a post's status (or plant a row) the same way,
  because the pipeline and the moderator tools that do it for real arrive in Parts 9 and 10.
- **What Part 7B does and doesn't show:** a repost is a plain pointer to the original, never a copy: it has no text
  and no status of its own and always shows the original's **live** label (nothing is checked again). You can't
  repost your own post, a post labelled FALSE or a removed or deleted one; you can always take a repost back,
  even when the original is gone. Reposting needs a verified email; bookmarks are **private**, need only a login
  and are never counted or shown to anyone else. Recent still lists only originals; the Following feed and a
  profile list posts **and** reposts, newest activity first. Score effects of reposts (11B), reports (8) and
  notifications (13) come later.

#### Step 1: Run the automated backend checks

**Where:** Terminal window 2 (commands), starting in the repo root.

**What this does:** Starts the database containers, activates the Python environment, applies the new migration,
confirms there is no further one, then runs the whole backend test suite, the social tests, the linter and the
formatter check.

```bash
# start in the repo root
docker compose up -d
cd backend
source .venv/bin/activate
python manage.py migrate                            # Applying social.0003_repost_bookmark... OK
python manage.py makemigrations --check --dry-run   # No changes detected
python manage.py check                              # System check identified no issues (0 silenced).
python -m pytest                                    # 1875 passed
python -m pytest apps/social -q                     # 695 passed
ruff check . ; ruff format --check .                # All checks passed! / 154 files already formatted
```

**You should see:** `Applying social.0003_repost_bookmark... OK` (nothing to apply the second time), `No changes
detected` and `System check identified no issues (0 silenced).`, then the full run ends with `1875 passed`, the
social run with `695 passed`, and the last line pair is `All checks passed!` and `154 files already formatted`.
(Counts may grow later; what matters is that nothing fails.)

- The 390 new social tests: `test_models_repost_bookmark.py` (16: the unique pairs, only the four statuses a post
  can be reposted in, cascades, the indexes), `test_services_repost_bookmark.py` (37: every refusal and their
  order, `status_at_repost`, undoing on a gone post, the cache bust, and real races: two simultaneous reposts make
  one row, six users are all counted, a repost waits for a concurrent status change and records the status at
  commit), `test_api_repost.py` (26, including the real 100-an-hour limit), `test_api_bookmark.py` (17,
  including the real 300-an-hour limit and that bookmarks don't use the like allowance),
  `test_api_bookmark_list.py` (16: only your own, newest first, deleted and removed dropped, a cursor walk, 3
  queries whatever the size), `test_api_feed_reposts.py` (32: mixed items, "no longer available" stubs, once per
  page, the cache, 4 / 3 queries), `test_api_user_posts_reposts.py` (17: reposts on a profile, the Facts and
  Opinions chips by the original's type), `test_timeline.py` (63: the page rule as a table, the cursor token and
  every way to forge one), `test_timeline_db.py` (140: ties, the cursor filters, the per-side slice, items
  arriving or changing during a walk, and 50 + 50 + 30 seeded random walks compared with a reference written
  separately), `test_admin_repost_bookmark.py` (6) and more in `test_engagement_counts.py` and
  `test_no_network.py`.
- `PostQuerySet.for_list(viewer)` now also counts reposts and tells you whether you reposted and bookmarked each
  post, in the same query; `PostSerializer` still refuses a post that wasn't counted.

#### Step 2: Run the automated frontend checks

**Where:** Terminal window 2, then `cd ../frontend`. Playwright (the last two commands) starts Django and
Next itself, so **no servers may be running on ports 3000 and 8000** (it reuses them if they are, with
whatever settings they have).

**What this does:** Runs the linters, the type check, the component tests, the production build and the
end-to-end tests.

```bash
cd ../frontend                                      # from backend/
npm run lint ; npm run lint:tokens ; npm run typecheck ; npm run format:check
npm test                                            # 113 files, 1510 tests passed
NEXT_PUBLIC_GOOGLE_CLIENT_ID= npm run build
npm run test:e2e                                    # 36 passed
CI=1 npm run test:e2e                               # 36 passed (against the production build)
cd ../backend                                       # back to backend/ for steps 3 to 13
```

**You should see:** the first line prints nothing from ESLint and TypeScript and ends with
`lint:tokens OK (…)` and `All matched files use Prettier code style!`. `npm test` ends with
`Test Files  113 passed (113)` and `Tests  1510 passed (1510)`. `npm run build` lists the same routes as in Part 7
(`/bookmarks` was a placeholder before and is now the real page; it is still static). Each E2E run ends with `36 passed`:
the 32 earlier tests and 4 new ones in `e2e/social.spec.ts`.

- The new E2E tests reuse the two people that file already signs up (allauth limits sign-ups to 20 a minute per
  address and the rest of the suite already uses most of that), so Part 7B adds **no** sign-up. A third person's
  post is made straight in the database. They are: B reposts that post, A (who follows B) sees "Reposted by B" with
  the post's live label, then "This post is no longer available" once it is removed, and B undoes the repost; a
  bookmark is private (it shows on A's `/bookmarks` and is empty for everyone else); Repost is disabled with its
  reason on your own post and on a FALSE one, and a visitor is sent to log in; and a card with four actions and the
  Bookmarks page fit a phone.

#### Step 3: Start the servers and make four accounts and three posts

**Where:** First window 1 (the Django server) and window 3 (the frontend), then window 2 (the commands).
**Keep using window 2 for steps 4 to 13.**

**What this does:** Windows 1 and 3 run the two servers. In window 2 you sign up four accounts through the API and
mark three of them verified (`dee` stays unverified), then `bo` posts an opinion and a fact with a DOI and `ada`
posts an opinion. The helpers `mk` (make a post, print its id), `send` (any request, printing the status code and
then the answer) and `get` (the same for a GET) are used by every later step.

Window 1 (in `backend`, venv active):

```bash
python manage.py runserver                          # leave it running
```

Window 3:

```bash
cd frontend                                         # from the repo root
npm run dev                                         # leave it running
```

Window 2 (in `backend` with the venv active: steps 1 and 2 leave you there; needs `jq`). If you opened a new
terminal, first run `cd backend` from the repo root and `source .venv/bin/activate`:

```bash
id=$(date +%H%M%S)                                  # a unique suffix so the addresses are new each run
h=(-H 'Origin: http://localhost:3000' -H 'X-Requested-With: rumor-zero')   # headers every auth call needs
signup() { jq -nc --arg e "$1" --arg u "$2" '{email: $e, username: $u, password: "correct-horse-battery-42", turnstile_token: "XXXX.DUMMY.TOKEN.XXXX"}' | curl -s "${h[@]}" -H "Content-Type: application/json" --data-binary @- http://localhost:8000/api/auth/app/v1/auth/signup | jq -r .meta.access_token; }
ada=$(signup "part7b-ada-$id@example.test" "part7b_ada_$id")    # $ada = ada's login token (reposts and bookmarks)
bo=$(signup "part7b-bo-$id@example.test" "part7b_bo_$id")       # $bo = bo's login token (the author of the posts)
cy=$(signup "part7b-cy-$id@example.test" "part7b_cy_$id")       # $cy = cy's login token (follows ada)
dee=$(signup "part7b-dee-$id@example.test" "part7b_dee_$id")    # $dee = dee's login token (never verified)
python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(email__startswith='part7b-', email__endswith='$id@example.test').exclude(username='part7b_dee_$id').update(is_email_verified=True), 'accounts marked verified')" | tail -1
api=http://localhost:8000/api/v1
adaname=part7b_ada_$id; boname=part7b_bo_$id; cyname=part7b_cy_$id; deename=part7b_dee_$id
mk() { curl -s -H "Authorization: Bearer $1" -H "Content-Type: application/json" --data-binary "$2" $api/posts/ | jq -r .id; }   # mk <token> <json>: makes a post, prints its id
get() { local out; out=$(curl -s -w '\n%{http_code}' ${2:+-H "Authorization: Bearer $2"} "$api$1"); printf '%s  ' "${out##*$'\n'}"; printf '%s' "${out%$'\n'*}" | jq -c "${3:-.}"; }   # get <path> [token] [jq filter]: prints the status code, then the answer
send() { local out; out=$(curl -s -w '\n%{http_code}' -X "$1" ${3:+-H "Authorization: Bearer $3"} ${4:+-H "Content-Type: application/json" --data-binary "$4"} "$api$2"); printf '%s  %s\n' "${out##*$'\n'}" "$(printf '%s' "${out%$'\n'*}" | jq -c "${5:-.}" 2>/dev/null)"; }   # send <METHOD> <path> [token] [json body] [jq filter]: prints the status code, then the answer
op1=$(mk "$bo" '{"content":"I think the new tram line will change how the city moves.","post_type":"opinion"}')
fact1=$(mk "$bo" '{"content":"Solar capacity grew by roughly 30% worldwide last year.","post_type":"fact","sources":["doi:10.1038/s41558-024-02102"]}')
adapost=$(mk "$ada" '{"content":"Ada thinks trams beat buses.","post_type":"opinion"}')
echo ${ada:0:10} ${bo:0:10} ${cy:0:10} ${dee:0:10}    # four prefixes, not an empty line
echo "op1=$op1"; echo "fact1=$fact1"; echo "adapost=$adapost"      # three ids, not empty
```

**You should see** (the number in the names is your `id`, and the ids differ):

```text
3 accounts marked verified
eyJhbGciOi eyJhbGciOi eyJhbGciOi eyJhbGciOi
op1=29da0351-d108-4b08-9965-626e7a05e8c9
fact1=3c2b6ef4-bc02-4076-8ec0-8f650613e851
adapost=ee6ff30b-0ac9-4578-a848-dd31c6019ca5
```

- The shell prints a line about auto-imported objects first; `tail -1` keeps only ours.
- Sign-up is limited to 20 a minute per address (Part 1), and still calls Cloudflare's test widget, so it
  needs internet.

**If it differs:** an empty token or an `id` of `null` means the sign-up or the post failed: `runserver` isn't
running, `jq` is missing, or you signed up more than 20 times in a minute. Fix that and run this step again
from `id=$(date +%H%M%S)`.

#### Step 4: Repost and undo

**Where:** Terminal window 2 (the same terminal as step 3).

**What this does:** Reposts and un-reposts through `POST` and `DELETE /api/v1/posts/{id}/repost/`, with the
refusals every toggle has. Both are idempotent. Reposting needs a verified email, taking a repost back only a login.

```bash
repost() { send POST /posts/$1/repost/ "$2"; }       # repost <post id> [token]
unrepost() { send DELETE /posts/$1/repost/ "$2"; }   # unrepost <post id> [token]
repost $op1 "$ada"                                  # 1: the first repost is 201
repost $op1 "$ada"                                  # 2: again: 200, nothing changes
repost $op1                                         # 3: nobody logged in
repost $op1 "$dee"                                  # 4: an unverified email
repost $fact1 "$ada"                                # 5: a fact that is still "checking" can be reposted
repost 00000000-0000-4000-8000-000000000000 "$ada"  # 6: no such post
repost not-a-uuid "$ada"                            # 7: not even an id
unrepost $fact1 "$ada"                              # 8: taking a repost back is 204
unrepost $fact1 "$ada"                              # 9: and again: still 204, no error
unrepost $fact1 "$dee"                              # 10: an unverified user may also take one back (there is none): 204
```

**You should see** (ten commands, ten answers):

```text
201  {"reposted":true}
200  {"reposted":true}
401  {"detail":"Authentication credentials were not provided.","code":"not_authenticated"}
403  {"detail":"Verify your email address first. Check your inbox for the link.","code":"email_unverified"}
201  {"reposted":true}
404  {"detail":"Not found.","code":"not_found"}
404  {"detail":"Not found.","code":"not_found"}
204
204
204
```

- The first repost is `201`, the same request again is `200` and changes nothing; `DELETE` is `204` every
  time, also when there was nothing to take back (9, 10).
- A repost has no id of its own: `POST` and `DELETE` always name the **original** post. So "reposting a repost"
  can only mean reposting the original, and a second repost of the same post by the same person can't exist.
- A 401 or 403 doesn't use up the allowance of 100 reposts an hour (step 12).

#### Step 5: What can't be reposted

**Where:** Terminal window 2.

**What this does:** Tries the three refusals of ARCHITECTURE §4d (your own post, a post labelled FALSE, a removed
or deleted post), and shows two subtle rules: a repost you already made survives the original turning FALSE, and
you can always take a repost back, even when the original is gone. The statuses are set with shell commands; the
tools that do it for real come in Parts 9 and 10.

```bash
repost $adapost "$ada"                              # 1: your own post is refused
false1=$(mk "$bo" '{"content":"The moon is made of green cheese.","post_type":"fact"}')
python manage.py shell -c "from apps.posts.models import Post; print(Post.objects.filter(pk='$false1').update(status='verified_false', verdict_source='moderator'), 'post marked FALSE')" | tail -1
repost $false1 "$ada"                               # 2: a post labelled FALSE is refused
op2=$(mk "$bo" '{"content":"This opinion will be removed by a moderator.","post_type":"opinion"}')
python manage.py shell -c "from apps.posts.models import Post; print(Post.objects.filter(pk='$op2').update(status='removed'), 'post removed')" | tail -1
op3=$(mk "$bo" '{"content":"This opinion will be deleted by its author.","post_type":"opinion"}')
send DELETE /posts/$op3/ "$bo"                      # bo deletes op3: 204
repost $op2 "$ada"                                  # 3: a removed post: 404
repost $op3 "$ada"                                  # 4: a deleted post: 404
fact2=$(mk "$bo" '{"content":"The harbour bridge is 1,149 metres long.","post_type":"fact"}')
repost $fact2 "$ada"                                # 5: a fact still being checked: 201
python manage.py shell -c "from apps.social.models import Repost; print(list(Repost.objects.filter(post_id='$fact2').values_list('status_at_repost', flat=True)), 'status recorded at the time')" | tail -1
python manage.py shell -c "from apps.posts.models import Post; print(Post.objects.filter(pk='$fact2').update(status='verified_false', verdict_source='moderator'), 'post marked FALSE')" | tail -1
repost $fact2 "$ada"                                # 6: it turned FALSE after ada reposted it: still a quiet 200
repost $fact2 "$cy"                                 # 7: but cy can't repost it now: 409
python manage.py shell -c "from apps.social.models import Repost; from apps.accounts.models import User; u = User.objects.get(username='$adaname'); [Repost.objects.create(user=u, post_id=p, status_at_repost='published') for p in ('$op2', '$op3')]; print(Repost.objects.filter(post_id__in=['$op2', '$op3']).count(), 'reposts planted on the removed and the deleted post')" | tail -1
unrepost $op2 "$ada"                                # 8: a repost of a removed post can be taken back: 204
unrepost $op3 "$ada"                                # 9: and one of a deleted post too: 204
python manage.py shell -c "from apps.social.models import Repost; print(Repost.objects.filter(post_id__in=['$op2', '$op3']).count(), 'reposts left on them')" | tail -1
unrepost 00000000-0000-4000-8000-000000000000 "$ada"   # 10: an unknown post is 404
```

**You should see:**

```text
409  {"detail":"You can't repost your own post.","code":"cannot_repost_own"}
1 post marked FALSE
409  {"detail":"Posts labelled FALSE can't be reposted.","code":"cannot_repost_false"}
1 post removed
204
404  {"detail":"Not found.","code":"not_found"}
404  {"detail":"Not found.","code":"not_found"}
201  {"reposted":true}
['pending'] status recorded at the time
1 post marked FALSE
200  {"reposted":true}
409  {"detail":"Posts labelled FALSE can't be reposted.","code":"cannot_repost_false"}
2 reposts planted on the removed and the deleted post
204
204
0 reposts left on them
404  {"detail":"Not found.","code":"not_found"}
```

- Your own post and a FALSE post are `409` with their own codes, which the button uses to explain itself (step 14).
  A removed or deleted post is the same plain `404` as for a post that never existed (3, 4).
- `status_at_repost` is the status the post had **when** it was reposted (`pending` here): Part 11B reads it to
  decide what a verdict is worth to the reposter. The post turning FALSE later doesn't touch it (6), and doesn't
  refuse a repost that already exists, but a new reposter is refused (7).
- The removed and the deleted post never take a new repost, but the two reposts planted on them (a shell command
  stands in for reposts made before the original went away) are taken back with a plain `204` (8, 9): the card
  that says "This post is no longer available" must always have its **Undo repost** (step 15).

#### Step 6: Bookmarks

**Where:** Terminal window 2.

**What this does:** Saves and un-saves posts through `POST` and `DELETE /api/v1/posts/{id}/bookmark/`. Bookmarks are
private, so there is no verified-email rule and no restriction on whose or which post: only a post the public can't
see is refused.

```bash
bookmark() { send POST /posts/$1/bookmark/ "$2"; }       # bookmark <post id> [token]
unbookmark() { send DELETE /posts/$1/bookmark/ "$2"; }   # unbookmark <post id> [token]
bookmark $op1 "$ada"                                # 1: the first bookmark is 201
bookmark $op1 "$ada"                                # 2: again: 200
bookmark $op1                                       # 3: nobody logged in
bookmark $op1 "$dee"                                # 4: an unverified email is fine: bookmarks are private
bookmark $adapost "$ada"                            # 5: your own post is fine
bookmark $false1 "$ada"                             # 6: so is a post labelled FALSE
bookmark $op2 "$ada"                                # 7: a removed post: 404
bookmark $op3 "$ada"                                # 8: a deleted post: 404
bookmark not-a-uuid "$ada"                          # 9: not even an id
unbookmark $op1 "$dee"                              # 10: taking one back is 204
unbookmark $op1 "$dee"                              # 11: and again: 204
unbookmark $op3 "$ada"                              # 12: a deleted post is 404 even for that
python manage.py shell -c "from apps.social.models import Bookmark; from apps.accounts.models import User; Bookmark.objects.create(user=User.objects.get(username='$adaname'), post_id='$op2'); print(Bookmark.objects.filter(post_id='$op2').count(), 'bookmark planted on the removed post')" | tail -1
unbookmark $op2 "$ada"                              # 13: ...but a bookmark can be taken back from a removed post: 204
python manage.py shell -c "from apps.social.models import Bookmark; print(Bookmark.objects.filter(post_id='$op2').count(), 'bookmarks left on it')" | tail -1
```

**You should see:**

```text
201  {"bookmarked":true}
200  {"bookmarked":true}
401  {"detail":"Authentication credentials were not provided.","code":"not_authenticated"}
201  {"bookmarked":true}
201  {"bookmarked":true}
201  {"bookmarked":true}
404  {"detail":"Not found.","code":"not_found"}
404  {"detail":"Not found.","code":"not_found"}
404  {"detail":"Not found.","code":"not_found"}
204
204
404  {"detail":"Not found.","code":"not_found"}
1 bookmark planted on the removed post
204
0 bookmarks left on it
```

- Like a repost, a bookmark is `201` then `200`, and `DELETE` is `204` every time (10, 11). `dee`, who may not
  like, comment or repost, can bookmark (4).
- Every visible post can be bookmarked, including your own (5) and a FALSE one (6). A removed or deleted post can't
  (7, 8), and a bookmark that was already there can be taken back from a removed post (13) but not a deleted one
  (12), exactly as with likes.

#### Step 7: The counts and flags on every post

**Where:** Terminal window 2.

**What this does:** Reads `repost_count`, `reposted_by_me` and `bookmarked_by_me` as nobody and as other people.
The count is public and the same for everyone; the two flags are yours alone. **There is no bookmark count anywhere**:
not on the post, not on a profile.

```bash
repost $op1 "$cy"                                   # cy reposts the tram post too: 201 (ada's repost is from step 4)
f='{reposts: .repost_count, reposted_by_me, bookmarked_by_me}'
get /posts/$op1/ "" "$f"                            # 1: nobody logged in
get /posts/$op1/ "$ada" "$f"                        # 2: ada reposted and bookmarked it
get /posts/$op1/ "$cy" "$f"                         # 3: cy reposted it, did not bookmark it
get /posts/$op1/ "$bo" "$f"                         # 4: bo wrote it: sees the count, nothing of his own
get /users/$boname/posts/ "$ada" '[.results[] | {text: .post.content[:26], reposts: .post.repost_count, reposted: .post.reposted_by_me, saved: .post.bookmarked_by_me}]'
get /users/$adaname/ "$bo" '.counts'                # 5: a profile has no bookmark count, and no repost count either
```

**You should see:**

```text
201  {"reposted":true}
200  {"reposts":2,"reposted_by_me":false,"bookmarked_by_me":false}
200  {"reposts":2,"reposted_by_me":true,"bookmarked_by_me":true}
200  {"reposts":2,"reposted_by_me":true,"bookmarked_by_me":false}
200  {"reposts":2,"reposted_by_me":false,"bookmarked_by_me":false}
200  [{"text":"The harbour bridge is 1,14","reposts":1,"reposted":true,"saved":false},{"text":"The moon is made of green ","reposts":0,"reposted":false,"saved":true},{"text":"Solar capacity grew by rou","reposts":0,"reposted":false,"saved":false},{"text":"I think the new tram line ","reposts":2,"reposted":true,"saved":true}]
200  {"followers":0,"following":0,"posts":1,"verified":0,"false":0}
```

- `reposts` is 2 for everyone (`ada` and `cy`); `reposted_by_me` and `bookmarked_by_me` are `false` for a visitor and
  for anyone who didn't do it (1, 4). `bo`, the author, sees nobody's bookmark, not even that someone saved his post (4).
- The list is `bo`'s four visible posts (the removed and the deleted one are left out), counted in the same query as
  the posts: a list of 20 posts costs the same number of queries as a list of 2 (tests pin it).
- The profile's counters (5) are the ones from Part 6: still no repost count and no bookmark count.

#### Step 8: The Following feed with reposts

**Where:** Terminal window 2.

**What this does:** Makes `cy` follow `ada`, lets `ada` repost two facts, and reads `cy`'s Following feed. It shows
that a repost carries the original's **live** label (a verdict changes it at once, even though the first page is
cached), that a repost whose original was removed becomes a stub, that an undone repost leaves the page at once, that
a **new** repost reaches a follower after at most 30 seconds (the cache), and that a post shows **once per page**.

```bash
feed() { get "/feed/${2:+?$2}" "$1" '[.results[] | {kind, by: (.reposted_by.username // null), text: ((.post.content // "-")[:24]), status: .post.status, gone: .post.unavailable}]'; }   # feed <token> [query]: cy's Following feed, one line per item
fact3=$(mk "$bo" '{"content":"Rail ridership doubled in ten years.","post_type":"fact"}')
send POST /users/$adaname/follow/ "$cy"             # cy follows ada: 201 (this also clears cy's cached feed)
repost $fact1 "$ada"                                # ada reposts the solar fact (still "checking")
repost $fact3 "$ada"                                # ...and a third fact
feed "$cy"                                          # 1: cy's Following feed: ada's post and reposts, and cy's own repost
python manage.py shell -c "from apps.posts.models import Post; print(Post.objects.filter(pk='$fact1').update(status='verified_true', verdict_source='pipeline', pipeline_verdict='true', confidence_score=94), 'post verified')" | tail -1
python manage.py shell -c "from apps.posts.models import Post; print(Post.objects.filter(pk='$fact3').update(status='removed'), 'post removed')" | tail -1
feed "$cy"                                          # 2: the label changed, the removed one is a stub: the cached page keeps only keys
unrepost $fact1 "$ada"                              # ada takes her solar repost back: 204
feed "$cy"                                          # 3: it is gone at once, though the page is still cached
op5=$(mk "$bo" '{"content":"A late post from bo.","post_type":"opinion"}')
repost $op5 "$ada"                                  # ada reposts a brand-new post
feed "$cy"                                          # 4: cy's cached page doesn't have it yet (at most 30 s)
sleep 31
feed "$cy"                                          # 5: 31 seconds later it is on top
send POST /users/$boname/follow/ "$cy"              # cy follows bo too (this clears the cache)
get /feed/ "$cy" "[.results[] | select(.post.id == \"$op1\") | {kind, by: (.reposted_by.username // null)}]"   # 6: the tram post, by bo and reposted twice: shown once
```

**You should see** (the number in the names is your `id`):

```text
201  {"is_following":true}
201  {"reposted":true}
201  {"reposted":true}
200  [{"kind":"repost","by":"part7b_ada_203850","text":"Rail ridership doubled i","status":"pending","gone":null},{"kind":"repost","by":"part7b_ada_203850","text":"Solar capacity grew by r","status":"pending","gone":null},{"kind":"repost","by":"part7b_cy_203850","text":"I think the new tram lin","status":"published","gone":null},{"kind":"repost","by":"part7b_ada_203850","text":"The harbour bridge is 1,","status":"verified_false","gone":null},{"kind":"post","by":null,"text":"Ada thinks trams beat bu","status":"published","gone":null}]
1 post verified
1 post removed
200  [{"kind":"repost","by":"part7b_ada_203850","text":"-","status":null,"gone":true},{"kind":"repost","by":"part7b_ada_203850","text":"Solar capacity grew by r","status":"verified_true","gone":null},{"kind":"repost","by":"part7b_cy_203850","text":"I think the new tram lin","status":"published","gone":null},{"kind":"repost","by":"part7b_ada_203850","text":"The harbour bridge is 1,","status":"verified_false","gone":null},{"kind":"post","by":null,"text":"Ada thinks trams beat bu","status":"published","gone":null}]
204
200  [{"kind":"repost","by":"part7b_ada_203850","text":"-","status":null,"gone":true},{"kind":"repost","by":"part7b_cy_203850","text":"I think the new tram lin","status":"published","gone":null},{"kind":"repost","by":"part7b_ada_203850","text":"The harbour bridge is 1,","status":"verified_false","gone":null},{"kind":"post","by":null,"text":"Ada thinks trams beat bu","status":"published","gone":null}]
201  {"reposted":true}
200  [{"kind":"repost","by":"part7b_ada_203850","text":"-","status":null,"gone":true},{"kind":"repost","by":"part7b_cy_203850","text":"I think the new tram lin","status":"published","gone":null},{"kind":"repost","by":"part7b_ada_203850","text":"The harbour bridge is 1,","status":"verified_false","gone":null},{"kind":"post","by":null,"text":"Ada thinks trams beat bu","status":"published","gone":null}]
200  [{"kind":"repost","by":"part7b_ada_203850","text":"A late post from bo.","status":"published","gone":null},{"kind":"repost","by":"part7b_ada_203850","text":"-","status":null,"gone":true},{"kind":"repost","by":"part7b_cy_203850","text":"I think the new tram lin","status":"published","gone":null},{"kind":"repost","by":"part7b_ada_203850","text":"The harbour bridge is 1,","status":"verified_false","gone":null},{"kind":"post","by":null,"text":"Ada thinks trams beat bu","status":"published","gone":null}]
201  {"is_following":true}
200  [{"kind":"repost","by":"part7b_cy_203850"}]
```

- Each item has `kind` (`post` or `repost`), `by` (who reposted it) and the original's content and status. A repost
  has no text of its own. Newest **activity** first: a repost sorts by when it was made, a post by when it was posted.
- Line 1 is cy's page: `ada`'s own post (the last item), her reposts of the two facts and of the harbour fact (from
  step 5, labelled `verified_false`: a repost shows the original's label whatever it was when reposted), and `cy`'s
  own repost of the tram post (step 7). **`ada`'s older repost of the same tram post is not there**: a post shows
  once per page, the most recent activity wins.
- Line 2: the solar repost says `verified_true` and the third fact's repost is a **stub** (`"gone": true`, no text,
  no status) although the page was read from the cache a moment ago: the cache holds only the keys of the page, and the
  posts and reposts are read fresh every time. A stub shows as "This post is no longer available" (step 15).
- Line 3: an undone repost leaves the page at once. Line 4: a **new** repost made by someone you follow isn't there
  yet, the same rule as a new post (Part 6): the first page is cached for 30 seconds. Line 5, 31 seconds later, it is.
  Your **own** reposts and follows clear your own cache, so they show at once.
- Line 6: after `cy` also follows `bo`, the tram post could show up three times (`bo`'s own post, `ada`'s repost and
  `cy`'s repost), but only the most recent of them, `cy`'s repost, is shown.

#### Step 9: Profiles with reposts, and the Facts and Opinions chips

**Where:** Terminal window 2.

**What this does:** Reads `ada`'s profile list, which now holds her own posts **and** her reposts, and the two filter
chips: a repost is filtered by the **original's** type, so a repost of a fact shows under Facts even when the fact is
gone.

```bash
prof='[.results[] | {kind, by: (.reposted_by.username // null), text: ((.post.content // "-")[:24]), gone: .post.unavailable}]'
get /users/$adaname/posts/ "" "$prof"               # 1: ada's profile: her own post and her reposts (the removed fact is a stub)
get "/users/$adaname/posts/?post_type=fact" "" "$prof"      # 2: Facts: her facts, and reposts of facts (also the one that is gone)
get "/users/$adaname/posts/?post_type=opinion" "" "$prof"   # 3: Opinions: her opinions, and reposts of opinions
get "/users/$adaname/posts/?post_type=gossip" "" "."        # 4: anything else is a 400
```

**You should see** (the number in the names is your `id`):

```text
200  [{"kind":"repost","by":"part7b_ada_203850","text":"A late post from bo.","gone":null},{"kind":"repost","by":"part7b_ada_203850","text":"-","gone":true},{"kind":"repost","by":"part7b_ada_203850","text":"The harbour bridge is 1,","gone":null},{"kind":"repost","by":"part7b_ada_203850","text":"I think the new tram lin","gone":null},{"kind":"post","by":null,"text":"Ada thinks trams beat bu","gone":null}]
200  [{"kind":"repost","by":"part7b_ada_203850","text":"-","gone":true},{"kind":"repost","by":"part7b_ada_203850","text":"The harbour bridge is 1,","gone":null}]
200  [{"kind":"repost","by":"part7b_ada_203850","text":"A late post from bo.","gone":null},{"kind":"repost","by":"part7b_ada_203850","text":"I think the new tram lin","gone":null},{"kind":"post","by":null,"text":"Ada thinks trams beat bu","gone":null}]
400  {"post_type":["Choose fact or opinion, or leave it out."]}
```

- The profile list is public and never cached. You can't repost your own post, so a profile never shows the same
  post twice and its pages are always full. The stub (`gone`) is `ada`'s repost of the removed fact, kept until she
  undoes it.
- The filter is applied to the original (2, 3): the stub is under Facts because the post it pointed at was a fact.

#### Step 10: Your bookmarks list

**Where:** Terminal window 2.

**What this does:** Reads `GET /api/v1/me/bookmarks/`: **only your own**, newest bookmark first, in the same
envelope as the feeds. Deleted and removed posts are left out (the bookmark rows stay, so a post that comes back
reappears).

```bash
python manage.py shell -c "from apps.social.models import Bookmark; from apps.accounts.models import User; u = User.objects.get(username='$adaname'); [Bookmark.objects.create(user=u, post_id=p) for p in ('$op2', '$op3')]; print(Bookmark.objects.filter(user=u).count(), 'bookmarks of ada in the table, including one on a removed and one on a deleted post')" | tail -1
saved='[.results[] | {kind, text: .post.content[:26], saved: .post.bookmarked_by_me}]'
get /me/bookmarks/ "$ada" "$saved"                  # 1: ada's list: newest bookmark first; the removed and the deleted post are dropped
get /me/bookmarks/ "$bo" "$saved"                   # 2: bo saved nothing: an empty list, not ada's
get /me/bookmarks/ "" '.code'                       # 3: nobody logged in: 401
curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $bo" "$api/users/$adaname/bookmarks/"   # 4: there is no address for someone else's list: 404
c=$(curl -s -H "Authorization: Bearer $ada" "$api/me/bookmarks/?page_size=2" | jq -r .next_cursor)
get "/me/bookmarks/?page_size=2" "$ada" '{n: (.results | length), more: (.next_cursor != null)}'   # 5: two to a page, and a cursor
get "/me/bookmarks/?page_size=2&cursor=$c" "$ada" '{n: (.results | length), more: (.next_cursor != null)}'   # 6: the rest
get "/me/bookmarks/?cursor=cD1ub3QtYS1kYXRl" "$ada" '.code'   # 7: a made-up cursor is a 404
get /me/bookmarks/ "$ada" '.results[0] | keys'      # 8: the items have the feed's four keys (activity_at is when you saved it)
```

**You should see:**

```text
5 bookmarks of ada in the table, including one on a removed and one on a deleted post
200  [{"kind":"post","text":"The moon is made of green ","saved":true},{"kind":"post","text":"Ada thinks trams beat buse","saved":true},{"kind":"post","text":"I think the new tram line ","saved":true}]
200  []
401  "not_authenticated"
404
200  {"n":2,"more":true}
200  {"n":1,"more":false}
404  "not_found"
200  ["activity_at","kind","post","reposted_by"]
```

- The order is the order she saved them in, newest first (the FALSE post, her own post, the tram post), not the order
  of the posts. Five rows are in the table, three are shown (1).
- `bo` gets an empty list, never `ada`'s (2), and there is no way to ask for another user's (4): the route doesn't
  exist. Nothing counts bookmarks anywhere (step 7).
- Every item is `kind: "post"` with `reposted_by: null`; its `activity_at` is the time of the bookmark.

#### Step 11: Paging the feed while posts arrive

**Where:** Terminal window 2.

**What this does:** Walks `cy`'s Following feed two items at a time while a new post and a new repost arrive between
the two pages. The mixed feed pages by a cursor over (activity time, kind, post, reposter), so nothing new can push an
item onto the next page or pull one off it; a cursor that isn't ours is a clean `404`.

```bash
p1=$(curl -s -H "Authorization: Bearer $cy" "$api/feed/?page_size=2")
echo "$p1" | jq -c '[.results[] | {kind, by: (.reposted_by.username // null), text: ((.post.content // "-")[:24])}]'   # 1: the first two items
c=$(echo "$p1" | jq -r .next_cursor)
mk "$bo" '{"content":"Posted while cy was reading.","post_type":"opinion"}' > /dev/null
repost $(mk "$bo" '{"content":"Reposted while cy was reading.","post_type":"opinion"}') "$ada"
get "/feed/?page_size=2&cursor=$c" "$cy" '[.results[] | {kind, by: (.reposted_by.username // null), text: ((.post.content // "-")[:24])}]'   # 2: the next two: neither new item gets in
get "/feed/?cursor=cD1ub3QtYS1kYXRl" "$cy" '.code'  # 3: a made-up cursor is a 404
get "/feed/?cursor=junk" "$cy" '.code'              # 4: so is any other cursor that isn't ours
```

**You should see** (the number in the names is your `id`):

```text
[{"kind":"repost","by":"part7b_ada_203850","text":"A late post from bo."},{"kind":"repost","by":"part7b_ada_203850","text":"-"}]
201  {"reposted":true}
200  [{"kind":"repost","by":"part7b_cy_203850","text":"I think the new tram lin"},{"kind":"repost","by":"part7b_ada_203850","text":"The harbour bridge is 1,"}]
404  "not_found"
404  "not_found"
```

- Line 1 is the two newest items. The two new ones (made after it) are newer than anything on the first page, so
  they only appear at the top of a **fresh** first page; the second page (line 3) carries on exactly where the first
  stopped: no repeat and no gap. A page can hold fewer items than its size when some rows repeat a post that is
  already on it; the cursor still moves past them.
- The cursor is a bare token (never an absolute URL, which would point past the relay). The one from Part 6's feed is not
  valid any more: the client simply starts from the top again (a test covers it).

#### Step 12: Reposting and bookmarking are rate limited

**Where:** Terminal window 2.

**What this does:** Makes two more verified accounts, then uses up their allowances: 100 reposts an hour (`POST` and
`DELETE` share it) and 300 bookmarks an hour (likewise). The two buckets are separate from each other and from
likes.

```bash
eve=$(signup "part7b-eve-$id@example.test" "part7b_eve_$id")    # $eve = a fresh account for the repost limit
gus=$(signup "part7b-gus-$id@example.test" "part7b_gus_$id")    # $gus = a fresh account for the bookmark limit
python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(email__in=['part7b-eve-$id@example.test', 'part7b-gus-$id@example.test']).update(is_email_verified=True), 'accounts marked verified')" | tail -1
for i in $(seq 1 100); do curl -s -o /dev/null -w '%{http_code}\n' -X POST -H "Authorization: Bearer $eve" $api/posts/$op1/repost/; done | sort | uniq -c   # 100 reposts of one post
curl -s -i -X POST -H "Authorization: Bearer $eve" $api/posts/$op1/repost/ | grep -ioE 'HTTP/[0-9.]+ [0-9]+|retry-after: [0-9]+|"code":"[a-z_]+"'              # the 101st
for i in $(seq 1 300); do curl -s -o /dev/null -w '%{http_code}\n' -X POST -H "Authorization: Bearer $gus" $api/posts/$op1/bookmark/; done | sort | uniq -c   # 300 bookmarks of one post
curl -s -i -X POST -H "Authorization: Bearer $gus" $api/posts/$op1/bookmark/ | grep -ioE 'HTTP/[0-9.]+ [0-9]+|retry-after: [0-9]+|"code":"[a-z_]+"'   # the 301st
send POST /posts/$op1/like/ "$gus"                  # bookmarks have their own allowance: a like still works
get /me/bookmarks/ "$gus" '{n: (.results | length)}'   # reading is never throttled
```

**You should see** (the seconds differ):

```text
2 accounts marked verified
     99 200
      1 201
HTTP/1.1 429
Retry-After: 3599
"code":"throttled"
    299 200
      1 201
HTTP/1.1 429
Retry-After: 3597
"code":"throttled"
201  {"liked":true}
200  {"n":1}
```

- 100 requests went through (the first made the repost, the other 99 were repeats), the 101st was refused with `429`,
  `"code":"throttled"` and a `Retry-After` in seconds. Likewise 300 bookmarks, then the 301st.
- A 401 or 403 doesn't use up an allowance (tests cover it, and that a refusal like `409` does count). Using up the
  bookmark allowance leaves a like working (201), so the buckets really are separate.

#### Step 13: The indexes are used

**Where:** Terminal window 2.

**What this does:** In a transaction that is thrown away at the end, makes 300 users, 20,000 posts, 3,000 reposts, 50
follows and 2,000 bookmarks, then asks the database how it would run the Following feed's query (a first page and a deep
page) and the bookmark page, and prints the plan lines. Nothing is saved.

```bash
python manage.py shell <<'PYEOF' 2>&1 | grep -E "^---|Scan|Sort|rolled back"
import random
from datetime import timedelta
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from apps.accounts.models import User
from apps.posts.models import Post, PostStatus
from apps.social import feed, timeline
from apps.social.models import Bookmark, Follow, Repost

class Rollback(Exception):
    pass

rng = random.Random(1)
try:
    with transaction.atomic():   # everything below is thrown away at the end
        users = User.objects.bulk_create([User(username=f"xq_{i:03d}", email=f"xq{i}@example.test") for i in range(301)])
        me, others = users[0], users[1:]
        now = timezone.now()
        Follow.objects.bulk_create([Follow(follower=me, following=u) for u in others[:50]])
        posts = Post.objects.bulk_create([Post(author=others[i % 300], content=f"p{i}", post_type="opinion", status="published", created_at=now - timedelta(seconds=3 * i)) for i in range(20000)])
        pairs = {}
        while len(pairs) < 3000:
            u, p = rng.choice(others), rng.choice(posts)
            if p.author_id != u.pk:
                pairs[(u.pk, p.pk)] = Repost(user=u, post=p, status_at_repost="published", created_at=now - timedelta(seconds=rng.randint(0, 60000)))
        Repost.objects.bulk_create(list(pairs.values()))
        Bookmark.objects.bulk_create([Bookmark(user=me, post=p, created_at=now - timedelta(seconds=i)) for i, p in enumerate(posts[:2000])])
        with connection.cursor() as c:
            for table in ("posts_post", "social_repost", "social_follow", "social_bookmark"):
                c.execute(f"ANALYZE {table}")
        deep = timeline.Key(now - timedelta(seconds=30000), 0, timeline.ZERO_UUID, timeline.ZERO_UUID)
        for label, cursor in (("--- Following feed, first page", None), ("--- Following feed, a deep page", deep)):
            with CaptureQueriesContext(connection) as q:
                timeline.page(feed.following_posts(me), feed.following_reposts(me), size=20, cursor=cursor, dedupe=True)
            print(label)
            with connection.cursor() as c:
                c.execute("EXPLAIN (COSTS OFF) " + q.captured_queries[-1]["sql"])
                for row in c.fetchall():
                    print(row[0])
        rows = Bookmark.objects.filter(user=me, post__deleted_at__isnull=True).exclude(post__status=PostStatus.REMOVED).order_by("-created_at", "-id").values("id", "created_at", "post_id")[:21]
        sql, params = rows.query.sql_with_params()
        print("--- bookmark page")
        with connection.cursor() as c:
            c.execute("EXPLAIN (COSTS OFF) " + sql, params)
            for row in c.fetchall():
                print(row[0])
        raise Rollback
except Rollback:
    print("rolled back: nothing was saved")
PYEOF
```

**You should see:**

```text
--- Following feed, first page
  ->  Incremental Sort
        Sort Key: posts_post.created_at DESC, (0) DESC, posts_post.id DESC, ('00000000-0000-0000-0000-000000000000'::uuid) DESC
              Sort Key: posts_post.created_at DESC, posts_post.id DESC
                    ->  Index Scan using posts_recent_idx on posts_post
                            ->  Seq Scan on social_follow u0
                    ->  Sort
                          Sort Key: social_repost.created_at DESC, social_repost.post_id DESC, social_repost.user_id DESC
                          ->  Seq Scan on social_repost
                                  ->  Seq Scan on social_follow u0_1
--- Following feed, a deep page
  ->  Incremental Sort
        Sort Key: posts_post.created_at DESC, (0) DESC, posts_post.id DESC, ('00000000-0000-0000-0000-000000000000'::uuid) DESC
              Sort Key: posts_post.created_at DESC, posts_post.id DESC
                    ->  Index Scan using posts_recent_idx on posts_post
                            ->  Seq Scan on social_follow u0
                    ->  Sort
                          Sort Key: social_repost.created_at DESC, social_repost.post_id DESC, social_repost.user_id DESC
                          ->  Seq Scan on social_repost
                                  ->  Seq Scan on social_follow u0_1
--- bookmark page
        ->  Index Scan using bookmarks_user_created_idx on social_bookmark
        ->  Index Scan using posts_post_pkey on posts_post
rolled back: nothing was saved
```

- The Following feed is one query: the posts side walks `posts_recent_idx` newest first and stops after enough rows (the
  same plan at the first page and at a deep one: that is what the plain `created_at <=` in the filter is for), the
  reposts side takes the reposts of the people you follow, sorts them and keeps the newest few, and the two are merged.
  Each side is cut to at most 41 rows (twice the page plus one).
- The reposts side is a sequential scan and a sort. At 3,000 reposts that is nothing; measured separately with
  300,000 reposts and 200 follows it took about 11 to 18 ms. Splitting it into a separate query per group of
  people (a variant that was tried) took about the same time, so it is recorded for Part 16 rather than built now.
- The bookmark page walks `bookmarks_user_created_idx` in order and looks each post up by its primary key: 21 rows, no sort.

#### Step 14: Reposts and bookmarks on the cards

**Where:** Browser, with `runserver` (window 1) and `npm run dev` (window 3) running. Log in at
http://localhost:3000/login as `part7b-cy-<id>@example.test` (use the `id` from step 3: `echo $id`) with the password `correct-horse-battery-42` (`cy` was verified in step 3).

**What this does:** Looks at the two new buttons and the "Reposted by" line, as four kinds of visitor.

| Do this | Expect |
|---|---|
| Open http://localhost:3000/home and click the **Following** tab | Cards from `bo` and `ada`. A repost has a small line **"↻ Reposted by @part7b_ada_<id>"** above the author row, in the same grey small type as a timestamp; the card itself is the original's, with the original's author. Every card ends with a hairline, then (left) a **heart**, a **speech bubble** and a **two-arrow repost glyph**, each with its count, and (right, alone) a small **bookmark** glyph. |
| Click the repost glyph on a card that isn't yours and isn't FALSE | The glyph turns **blue** and the count goes up by one **at once**, before the server answers. Click again: back to grey and the old count. |
| Click the bookmark glyph | It turns into a filled **blue** bookmark at once; click again to take it back. There is no number beside it, ever. |
| Log in as `ada` in a second window. On her own post ("Ada thinks trams beat buses.") look at its repost glyph | It is dimmed. Hover it: the tooltip says "You can't repost your own post." A click shows the same words as a toast and sends nothing. |
| As `ada`, on "The moon is made of green cheese." (FALSE) look at the repost glyph | Dimmed, with the tooltip and toast "Posts labelled FALSE can't be reposted." Its bookmark still works. |
| Reload the page | The glyphs and counts are what the server says: the state survived. |
| Open a private window and go to /home (a visitor) | The same cards and counts. The repost and bookmark glyphs are **links**: they point to `/login?next=%2Fp%2F<id>`. |
| In another window log in as `dee` (`part7b-dee-<id>@example.test`, same password: never verified) and click a repost glyph | It looks dimmed and nothing is sent; a toast says "Verify your email to repost posts. Check your inbox for the link." The bookmark glyph **works**: bookmarks are private. |

- Covered by `RepostButton.test.tsx` (flip before the answer, rollback and a toast per kind of failure, one request for
  two clicks in one tick, the disabled reasons, enabled to undo, the visitor and unverified states, a unique hint per
  button), `BookmarkButton.test.tsx`, `RepostHeader.test.tsx`, `PostActions.test.tsx`, `FeedList.test.tsx` and the new E2E tests.
- Every button sits above the card's big invisible link, so it never opens the post by accident. A repost's buttons
  act on the **original** (a repost has no id of its own), so reposting a card that already says "Reposted by" reposts
  the original post.

#### Step 15: "This post is no longer available", and Undo repost

**Where:** Browser, logged in as `ada` (`part7b-ada-<id>@example.test`) in one window and as `cy` in another.

**What this does:** Looks at what a repost becomes when its original disappears (the stub from step 8) and removes it.

| Do this | Expect |
|---|---|
| As `cy`: open /home, click **Following** | One card has the line "↻ Reposted by @part7b_ada_<id>" and, below it, a shorter card body with a **no-entry glyph** and **"This post is no longer available"**: no text, no buttons. It is the third fact's repost, whose original was removed in step 8. There is no **Undo repost** button for `cy`. |
| As `ada`: open http://localhost:3000/u/part7b_ada_`<id>` (Profile in the rail) | The same card in her list, **with a ghost "Undo repost" button** at its right. Her other reposts have "Reposted by" lines and the normal buttons, and her repost glyphs are blue. |
| Still as `ada`, click the **Facts** chip, then **Opinions** | The stub is listed under **Facts** (its original was a fact) and not under **Opinions**. |
| Click **Undo repost** | The card disappears and a toast says "Repost removed." Reload: it is still gone, and `cy`'s Following tab no longer shows it. |

- The server answers `204` to an undo whatever became of the original (step 5), so a stub can always be removed.
- Covered by `UnavailablePostCard.test.tsx`, the Undo cases in `FeedList.test.tsx` and the E2E test.

#### Step 16: The Bookmarks page and the post page

**Where:** Browser, logged in as `ada`, with both servers running.

**What this does:** Opens the page that lists your bookmarks and the post page's action row.

| Do this | Expect |
|---|---|
| Click **Bookmarks** in the left rail (http://localhost:3000/bookmarks) | A heading **Bookmarks** and your saved posts, newest bookmark first: the FALSE moon post, `ada`'s own post, the tram post. Each card has its bookmark **filled and blue**; the moon post's and her own post's repost glyphs are dimmed, the tram post's is blue. The list ends with "You're caught up." |
| Click a filled bookmark | It turns outline at once (the card stays until the next load, as an unfollowed row does). Reload: it is gone from the list. |
| Log in as `bo` (never saved anything) and open /bookmarks | An empty state with a bookmark glyph: **"No bookmarks yet"** and "Posts you bookmark appear here. Only you can see them." |
| Log out and open /bookmarks | You are sent to `/login?next=%2Fbookmarks` and come back here after logging in. |
| Open a post's own page (click its text) | The claim card's action row reads **Like, Comments, Repost** with words beside the glyphs (from 640 px up), then the **bookmark** glyph and **Copy link**. The repost and bookmark work as on a card. |

- The list is fetched by the page after it loads (not server-rendered, never indexed), and only after the session is
  known, so the first request carries your token. A pending fact in the list still changes its badge by itself.
- Covered by `BookmarkList.test.tsx` (including the StrictMode case), `BookmarkButton.test.tsx` and the E2E test.

#### Step 17: A phone-sized window

**Where:** Browser, logged in as `cy`.

**What this does:** Checks the new parts at phone width. In Firefox or Chrome press `F12`, then the "responsive
design" / device toolbar button, and set the width to 390.

| Do this | Expect |
|---|---|
| Open /home and click **Following** | Each card's bar (heart, count, bubble, count, repost, count, and the bookmark at the right) fits on one line under the claim; a repost's "Reposted by" line fits above the author row. **No sideways scrolling.** |
| Open /bookmarks | The heading and the cards fit; **no sideways scrolling.** |
| Open a post's page | The action row holds the glyphs with their counts only (the words are hidden below 640 px), the bookmark and **Copy link**, wrapping to a second line if needed. |

- Measured with headless Chromium at 390 px: 0 px of horizontal overflow on `/home`, on the Following tab and on
  `/bookmarks`.

#### Step 18: Django Admin: reposts, and bookmarks for superusers only

**Where:** Browser, while `runserver` is running in window 1. For the moderator check, first make one in window 2:

```bash
python manage.py shell -c "from django.contrib.auth.models import Permission; from apps.accounts.models import User, Role; mod = User.objects.create_user(email='part7b-mod-$id@example.test', username='part7b_mod_$id', password='correct-horse-battery-42', role=Role.MODERATOR, is_email_verified=True); mod.user_permissions.set(Permission.objects.filter(codename__in=['view_repost', 'view_bookmark', 'change_bookmark', 'delete_bookmark', 'add_bookmark'])); print('moderator made')" | tail -1
```

**What this does:** Opens the two new admin lists as a superuser, then as a moderator who holds **every bookmark
permission** (a moderator gets no permissions at all until Part 10; this one is given them by hand to prove they don't
matter).

| URL / action | Expect |
|---|---|
| http://localhost:8000/admin/ (superuser from Part 0A; if it 404s, `ADMIN_URL_PATH` in `backend/.env` isn't `admin/`: use that path) | **Bookmarks** and **Reposts** are listed under Social. |
| http://localhost:8000/admin/social/repost/ | **Reposts**: user, post, **Status at repost** and **Created at**, newest first, a search box (username) and a **By status at repost** filter. No **Add repost** button; a repost's page only shows the values (no Save, no Delete: they answer 403 if you type the address). |
| http://localhost:8000/admin/social/bookmark/ | **Bookmarks**: user, post and **Created at**, read-only like the follows. This list exists for the superuser's own housekeeping; nothing else in the product ever shows it. |
| Log out, log in as `part7b-mod-<id>@example.test` (password above) and open http://localhost:8000/admin/ | **Reposts** is listed (read-only). **Bookmarks is not listed at all.** |
| As the moderator open http://localhost:8000/admin/social/bookmark/ and `…/bookmark/add/` | **403** for both, although this account has `view`, `add`, `change` and `delete` for bookmarks: nobody but a superuser can open the list (user decision 2026-10-10). |

- Reposts are read-only because a repost changes only through the service (it must clear the reposter's cached feed
  and respect the rules). Bookmarks are private by design (ARCHITECTURE §4d): no moderator permission, now or after Part
  10, opens them.
- Covered by `test_admin_repost_bookmark.py` (including a moderator holding all five bookmark permissions) and, for these
  clicks, a scripted browser run; not clicked by a person.

#### Step 19: Stop and clean up

**Where:** Every terminal window, plus the browser.

- Stop the servers: `Ctrl+C` in windows 1 and 3 (a leftover `next dev`: step 12 of Part 1).
- Delete the test accounts, their posts, follows, likes, reposts and bookmarks (all go with the accounts). In window 2, in `backend/` with the
  venv active:

  ```bash
  python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(email__startswith='part7b-').delete())" | tail -1
  ```

  After one clean run of steps 3 to 13 of this guide it prints `(39, {'social.Like': 1, 'social.Repost': 7, 'social.Bookmark': 6, 'social.Follow': 2, 'account.EmailAddress': 6, 'posts.Post': 11, 'accounts.User': 6})`:
  how many rows went in all, and per table (11 posts: ten by `bo`, among them the removed one, the deleted one (still a
  row) and the two made while `cy` was reading, and `ada`'s own; 7 reposts: `ada` still holds the tram post, the
  harbour fact, the third fact, the late post and the one made while `cy` was reading, `cy` the tram post and `eve` the
  same one (the solar repost was undone and the two planted ones were taken back); 6 bookmarks: `ada`'s five (the tram
  post, her own, the FALSE one and the two planted on the removed and the deleted post) and `gus`'s; 1 like, `gus`'s; 2
  follows, `cy` of `ada` and of `bo`). Your count differs if you did the browser steps (more reposts, bookmarks and
  likes) or step 18 (one more account, with its permissions). Nothing else is touched.
  (The E2E tests' accounts stay in your local database, as in earlier parts: Django Admin → Users deletes them.)
  If you made a throwaway moderator for step 18, that goes too (same prefix).
- `docker compose down` (repo root) stops the containers and keeps the data; `docker compose down -v`
  wipes the whole local database, which is destructive.
- No secret was used or printed in this part: the only values in the commands are Cloudflare's public test
  token and the throwaway password of the test accounts.

### Part 8: Reporting & threshold

Needs Part 0A's containers and virtualenv, Part 0C's frontend, and your own `backend/.env` and
`frontend/.env.local`. Part 8 adds **one migration** (`reports.0001_initial`: the reports table), **two new Django
apps** (`apps/reports` and `apps/pipeline`, which holds only `routing.py` so far), **no dependency** and **no new
variable** (the `report` rate of 10 an hour and the four report settings were already there). It adds the endpoint
`POST /api/v1/posts/{id}/report/`, fills `reported_by_me` in every post, adds the **flag button** and the **report
dialog**, and closes one gap in Part 7B: a post under review that was FALSE before the review can't be reposted.

**Which terminal window for what.** Open the windows once and keep using the same ones:

| Window | What runs in it | Used in steps |
|---|---|---|
| Window 1 (server) | `python manage.py runserver` in `backend`, venv active. Leave it running. Start it in step 3, **after** step 2 (Playwright starts its own servers and needs ports 3000 and 8000 free). | 3 to 13 |
| Window 2 (commands) | All the `curl` and `python manage.py` commands. **Use the same window for steps 3 to 9**: the variables and functions you set in step 3 (`id`, `ada`, `bo`, `cy`, `dee`, `ed`, `fay`, `gus`, `hal`, `ivy`, `api`, `op1`, `fact1`, `mk`, `get`, `send`, and the helpers later steps add) only live in that one terminal. If you close it, redo step 3. | 1 to 9, 14 |
| Window 3 (frontend) | `npm run dev` in `frontend`. Leave it running. | 10 to 13 |
| Browser | Steps 10 to 13 | 10 to 13 |

Things to know first:

- Steps 3 to 9 talk to the API directly with `curl` (they need `jq`: `sudo apt install jq`). Steps 10 to 13 use the
  browser. Step 3 makes nine accounts: `bo` writes the posts, five people (`ada`, `cy`, `ed`, `fay`, `gus`) each post
  once and then report, `hal` is verified but has **never posted or commented**, `dee` is never verified, and `ivy`
  is only there for the rate limit in step 9.
- The API and page outputs below were recorded on Linux on 2026-10-10. The browser steps were checked the same
  day with headless Chromium (screenshots at 1280 and 390 px) and Django Admin with a scripted browser, not by a
  person at a keyboard. Ids, numbers in names, times and seconds differ on every run.
- Nothing here sends an email: step 3 marks the accounts verified with a shell command, which stands in for
  clicking the link (Part 2 shows the real flow). Steps 7 and 8 set a post's status or move a report's time the same
  way, because the pipeline and the moderator tools that do it for real arrive in Parts 9 and 10.
- **The numbers assume the default settings** (5 counting reports inside 24 hours, an account at least 24 hours old).
  The backend seeds them from your own `backend/.env` the first time, so check yours before step 6:

  ```bash
  python manage.py shell -c "from apps.core.services import get_platform_settings as g; c = g(); print(c.report_threshold, c.report_window_hours, c.report_min_account_age_hours)" | tail -1
  ```

  It should print `5 24 24`. If not, the counts in steps 6 and 7 shift by the difference.
- **What Part 8 does and doesn't show:** a report is private and final (one per person and post, for life). It
  **counts toward the threshold** only if the account is at least 24 hours old, or the person has already taken part
  (a post that isn't removed or a comment that isn't hidden; posts and comments they deleted themselves still count).
  When 5 counting reports arrive inside 24 hours the post goes to **UNDER REVIEW** but stays visible; nothing is
  removed automatically. What moderators then do (Mark FALSE, Dismiss, Remove) is Part 10, the fact-check that gives
  a post a label is Part 9, the credibility credit for a good report is 11B and the notification to the author is 13.

#### Step 1: Run the automated backend checks

**Where:** Terminal window 2 (commands), starting in the repo root.

**What this does:** Starts the database containers, activates the Python environment, applies the new migration,
confirms there is no further one, then runs the whole backend test suite, the new tests, the linter and the
formatter check.

```bash
# start in the repo root
docker compose up -d
cd backend
source .venv/bin/activate
python manage.py migrate                            # Applying reports.0001_initial... OK
python manage.py makemigrations --check --dry-run   # No changes detected
python manage.py check                              # System check identified no issues (0 silenced).
python -m pytest                                    # 2066 passed
python -m pytest apps/reports apps/pipeline -q      # 182 passed
ruff check . ; ruff format --check .                # All checks passed! / 181 files already formatted
```

**You should see:** `Applying reports.0001_initial... OK` (nothing to apply the second time), `No changes detected` and
`System check identified no issues (0 silenced).`, then the full run ends with `2066 passed`, the new apps' run with
`182 passed`, and the last line pair is `All checks passed!` and `181 files already formatted`. (Counts may grow
later; what matters is that nothing fails.)

- The 182 new tests: `apps/pipeline/tests/test_routing.py` (45: every `merge_flag` pair, `enter_review` from every
  status, `apply_report_threshold` below, at and above the threshold, a removed post, an appeal), and in
  `apps/reports/tests/`: `test_models.py` (12: the unique pair, the five named checks, cascades),
  `test_counting.py` (23: the age rule at its exact edge, a young account with each kind of post and comment, deleted
  ones counting and moderated ones not), `test_threshold.py` (36: the report that reaches the threshold, every
  status it starts from, the window at its exact edge, dismissed and non-counting reports, every refusal),
  `test_races.py` (6: real threads: two simultaneous reports by one person make one, six people are all counted, a report
  waits for a concurrent delete or removal and is then a 404, and two reports waiting behind a held row lock still reach
  the threshold), `test_api_report.py` (44, including the real 10-an-hour limit), `test_reported_by_me.py` (8),
  `test_admin.py` (6) and `test_no_network.py` (2).
- Some more in `apps/social/tests/` (the new repost refusal) and `test_engagement_counts.py` (`reported_by_me` is
  read strictly like the other counts).
- `PostQuerySet.for_list(viewer)` now also tells you whether you reported each post, in the same query; every list
  keeps its query count.

#### Step 2: Run the automated frontend checks

**Where:** Terminal window 2, then `cd ../frontend`. Playwright (the last two commands) starts Django and
Next itself, so **no servers may be running on ports 3000 and 8000** (it reuses them if they are, with
whatever settings they have).

**What this does:** Runs the linters, the type check, the component tests, the production build and the
end-to-end tests.

```bash
cd ../frontend                                      # from backend/
npm run lint ; npm run lint:tokens ; npm run typecheck ; npm run format:check
npm test                                            # 117 files, 1580 tests passed
NEXT_PUBLIC_GOOGLE_CLIENT_ID= npm run build
npm run test:e2e                                    # 38 passed
CI=1 npm run test:e2e                               # 38 passed (against the production build)
cd ../backend                                       # back to backend/ for steps 3 to 9
```

**You should see:** the first line prints nothing from ESLint and TypeScript and ends with
`lint:tokens OK (…)` and `All matched files use Prettier code style!`. `npm test` ends with
`Test Files  117 passed (117)` and `Tests  1580 passed (1580)`. `npm run build` lists the same routes as in Part 7B
(Part 8 adds no route). Each E2E run ends with `38 passed`: the 36 earlier tests and 2 new ones in
`e2e/social.spec.ts` (one earlier phone test now checks five actions).

- The new E2E tests reuse the two people that file already signs up (allauth limits sign-ups to 20 a minute per
  address and the rest of the suite already uses most of that), so Part 8 adds **no** sign-up. A third person's post and
  the reports that bring it one short of the threshold are made straight in the database (`seedReports()` in
  `e2e/helpers.ts`, through the backend's own report service). The tests are: the form checks itself ("Choose a
  reason.", then "Tell us what's wrong." for "Something else"), the report is sent, the flag turns into "You reported
  this" and keeps focus, a reload shows the post UNDER REVIEW with its text still there, and the post page agrees; and
  no Report on your own post, with a visitor's flag a link to log in.

#### Step 3: Start the servers and make nine accounts and posts

**Where:** First window 1 (the Django server) and window 3 (the frontend), then window 2 (the commands).
**Keep using window 2 for steps 4 to 9.**

**What this does:** Windows 1 and 3 run the two servers. In window 2 you sign up nine accounts through the API and
mark eight of them verified (`dee` stays unverified), then `bo` posts an opinion and a fact with a DOI, and five
people each post an opinion (so their later reports count: a brand-new account with no activity doesn't count, step 7).
The helpers `mk` (make a post, print its id), `send` (any request, printing the status code and then the answer) and
`get` (the same for a GET) are used by every later step.

Window 1 (in `backend`, venv active):

```bash
python manage.py runserver                          # leave it running
```

Window 3:

```bash
cd frontend                                         # from the repo root
npm run dev                                         # leave it running
```

Window 2 (in `backend` with the venv active: steps 1 and 2 leave you there; needs `jq`). If you opened a new
terminal, first run `cd backend` from the repo root and `source .venv/bin/activate`:

```bash
id=$(date +%H%M%S)                                  # a unique suffix so the addresses are new each run
h=(-H 'Origin: http://localhost:3000' -H 'X-Requested-With: rumor-zero')   # headers every auth call needs
signup() { jq -nc --arg e "$1" --arg u "$2" '{email: $e, username: $u, password: "correct-horse-battery-42", turnstile_token: "XXXX.DUMMY.TOKEN.XXXX"}' | curl -s "${h[@]}" -H "Content-Type: application/json" --data-binary @- http://localhost:8000/api/auth/app/v1/auth/signup | jq -r .meta.access_token; }
ada=$(signup "part8-ada-$id@example.test" "part8_ada_$id")      # $ada = ada's login token (reports, and the first reporter)
bo=$(signup "part8-bo-$id@example.test" "part8_bo_$id")         # $bo = bo's login token (the author of the posts)
cy=$(signup "part8-cy-$id@example.test" "part8_cy_$id")         # $cy .. $gus = four more people who report
dee=$(signup "part8-dee-$id@example.test" "part8_dee_$id")      # $dee = never verified
ed=$(signup "part8-ed-$id@example.test" "part8_ed_$id")
fay=$(signup "part8-fay-$id@example.test" "part8_fay_$id")
gus=$(signup "part8-gus-$id@example.test" "part8_gus_$id")
hal=$(signup "part8-hal-$id@example.test" "part8_hal_$id")      # $hal = verified, but has never posted or commented
ivy=$(signup "part8-ivy-$id@example.test" "part8_ivy_$id")      # $ivy = only used for the rate limit in step 9
python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(email__startswith='part8-', email__endswith='$id@example.test').exclude(username='part8_dee_$id').update(is_email_verified=True), 'accounts marked verified')" | tail -1
api=http://localhost:8000/api/v1
mk() { curl -s -H "Authorization: Bearer $1" -H "Content-Type: application/json" --data-binary "$2" $api/posts/ | jq -r .id; }   # mk <token> <json>: makes a post, prints its id
get() { local out; out=$(curl -s -w '\n%{http_code}' ${2:+-H "Authorization: Bearer $2"} "$api$1"); printf '%s  ' "${out##*$'\n'}"; printf '%s' "${out%$'\n'*}" | jq -c "${3:-.}"; }   # get <path> [token] [jq filter]: prints the status code, then the answer
send() { local out; out=$(curl -s -w '\n%{http_code}' -X "$1" ${3:+-H "Authorization: Bearer $3"} ${4:+-H "Content-Type: application/json" --data-binary "$4"} "$api$2"); printf '%s  %s\n' "${out##*$'\n'}" "$(printf '%s' "${out%$'\n'*}" | jq -c "${5:-.}" 2>/dev/null)"; }   # send <METHOD> <path> [token] [json body] [jq filter]: prints the status code, then the answer
op1=$(mk "$bo" '{"content":"I think the new tram line will change how the city moves.","post_type":"opinion"}')
fact1=$(mk "$bo" '{"content":"Solar capacity grew by roughly 30% worldwide last year.","post_type":"fact","sources":["doi:10.1038/s41558-024-02102"]}')
for t in "$ada" "$cy" "$ed" "$fay" "$gus"; do mk "$t" '{"content":"I enjoy the rain.","post_type":"opinion"}' > /dev/null; done   # five people who have taken part
echo ${ada:0:10} ${bo:0:10} ${hal:0:10}                # three prefixes, not an empty line
echo "op1=$op1"; echo "fact1=$fact1"                    # two ids, not empty
```

**You should see** (the number in the names is your `id`, and the ids differ):

```text
8 accounts marked verified
eyJhbGciOi eyJhbGciOi eyJhbGciOi
op1=1b699450-7e9d-44ea-a24c-6a991dbb282a
fact1=9ed9ca08-f00a-416b-bee5-856a3bfd45d6
```

- The shell prints a line about auto-imported objects first; `tail -1` keeps only ours.
- Sign-up is limited to 20 a minute per address (Part 1), and still calls Cloudflare's test widget, so it
  needs internet. Nine sign-ups fit.

**If it differs:** an empty token or an `id` of `null` means the sign-up or the post failed: `runserver` isn't
running, `jq` is missing, or you signed up more than 20 times in a minute. Fix that and run this step again
from `id=$(date +%H%M%S)`.

#### Step 4: Report a post, and everything that is refused

**Where:** Terminal window 2 (the same terminal as step 3).

**What this does:** Reports a post through `POST /api/v1/posts/{id}/report/` and tries every refusal: one report per
person, a login, a verified email, your own post, a post that isn't there, and the three ways the body can be wrong.

```bash
report() { send POST /posts/$1/report/ "$2" "$3"; }   # report <post id> <token> <json body>
report $op1 "$ada" '{"reason":"inaccurate"}'                  # 1: ada's first report is 201
report $op1 "$ada" '{"reason":"spam"}'                        # 2: the same person again: 409, for life
report $op1 "" '{"reason":"spam"}'                            # 3: nobody logged in
report $op1 "$dee" '{"reason":"spam"}'                        # 4: an unverified email
report $op1 "$bo" '{"reason":"spam"}'                         # 5: bo can't report his own post
report 00000000-0000-4000-8000-000000000000 "$hal" '{"reason":"spam"}'   # 6: no such post
report not-a-uuid "$hal" '{"reason":"spam"}'                  # 7: not even an id
report $op1 "$hal" '{}'                                       # 8: no reason
report $op1 "$hal" '{"reason":"nonsense"}'                    # 9: not one of the five
report $op1 "$hal" '{"reason":"other"}'                       # 10: "something else" needs words
report $op1 "$hal" '{"reason":"other","details":"   "}'       # 11: and spaces are not words
report $op1 "$hal" "$(jq -nc --arg d "$(printf 'x%.0s' $(seq 501))" '{reason:"other",details:$d}')"   # 12: 501 characters
report $op1 "$cy" '{"reason":"other","details":"  It makes a claim about me that is not true.  "}'      # 13: cy's report, with details: 201
```

**You should see** (thirteen commands, thirteen answers):

```text
201  {"reported":true}
409  {"detail":"You already reported this post.","code":"already_reported"}
401  {"detail":"Authentication credentials were not provided.","code":"not_authenticated"}
403  {"detail":"Verify your email address first. Check your inbox for the link.","code":"email_unverified"}
403  {"detail":"You can't report your own post.","code":"cannot_report_own"}
404  {"detail":"Not found.","code":"not_found"}
404  {"detail":"Not found.","code":"not_found"}
400  {"reason":["Choose a reason."]}
400  {"reason":["Choose a reason."]}
400  {"details":["Tell us what's wrong."]}
400  {"details":["Tell us what's wrong."]}
400  {"details":["Keep it to 500 characters."]}
201  {"reported":true}
```

- A report is always the same `201 {"reported":true}`: the answer never says whether it sent the post to review.
- The second report by `ada` is `409`, and would be even if a moderator had dismissed her first one: one report
  per person and post, **for life**.
- Your own post is `403` (`cannot_report_own`); a removed or deleted post is the plain `404` of a post that never
  existed, **its author included**.
- Missing, `null` or unknown reasons all say "Choose a reason."; "Something else" needs words (`null`, empty and
  spaces don't count); details are trimmed and counted in characters, so an emoji is one.
- A 401 or an unverified email doesn't use up the allowance of 10 reports an hour (step 9); every other answer does,
  a 400 or a 409 included.

#### Step 5: `reported_by_me`, and what stays private

**Where:** Terminal window 2.

**What this does:** Reads the post as the person who reported it, as its author, as another person and as a
visitor, then checks that nothing else about reports shows in the post.

```bash
get /posts/$op1/ "$ada" '{reported_by_me}'            # 1: ada reported it: true
get /posts/$op1/ "$bo" '{reported_by_me}'             # 2: the author: false
get /posts/$op1/ "" '{reported_by_me}'                # 3: a visitor: false
get /posts/ "$cy" '[.results[].post | select(.id == "'$op1'") | .reported_by_me]'   # 4: in the Recent list, for cy: true
get /posts/ "$ed" '[.results[].post | select(.id == "'$op1'") | .reported_by_me]'   # 5: in the same list, for ed (who has not reported): false
get /posts/$op1/ "$bo" 'keys | map(select(test("report|flag")))'                    # 6: nothing about reports leaks except your own flag
```

**You should see:**

```text
200  {"reported_by_me":true}
200  {"reported_by_me":false}
200  {"reported_by_me":false}
200  [true]
200  [false]
200  ["reported_by_me"]
```

- Only the person who reported sees `true` (1, 4); the author, someone else and a visitor see `false`. It is the
  same flag in Recent, the Following feed, a profile's posts, your bookmarks and the post page.
- The post has no report count, no reasons and no reporter: the only key that mentions reports is your own flag (6).

#### Step 6: Five counting reports send a post to review, and it stays visible

**Where:** Terminal window 2.

**What this does:** Adds three more reports to the tram post (it has two from step 4) and watches its status after
each stage. The `state` helper prints the post's status, why it is under review, what it was before, and the lifetime
report counter.

```bash
state() { python manage.py shell -c "from apps.posts.models import Post; p = Post.objects.get(pk='$1'); print(p.status, p.flagged_reason, p.pre_review_status, 'report_count=%d' % p.report_count)" | tail -1; }   # state <post id>
state $op1                                            # 1: two reports so far (ada and cy)
report $op1 "$ed" '{"reason":"misleading"}'           # 2: the third
report $op1 "$fay" '{"reason":"spam"}'                # 3: the fourth
state $op1                                            # 4: still published
report $op1 "$gus" '{"reason":"harassment"}'          # 5: the fifth: the same answer as any other report
state $op1                                            # 6: now under review
get /posts/$op1/ "" '{status, content}'               # 7: but it is still visible, with its text, to a visitor
get /posts/ "" '[.results[].post | select(.id == "'$op1'") | .status]'   # 8: and still in Recent
```

**You should see:**

```text
published None None report_count=2
201  {"reported":true}
201  {"reported":true}
published None None report_count=4
201  {"reported":true}
under_review reports published report_count=5
200  {"status":"under_review","content":"I think the new tram line will change how the city moves."}
200  ["under_review"]
```

- Four counting reports leave the post as it was; the fifth moves it to `under_review` with `flagged_reason` `reports`
  and remembers it was `published`, so a moderator's **Dismiss** (Part 10) can put it back.
- The post **stays visible**: a visitor still reads its text (7) and it is still in Recent (8). Reports never hide
  a post; a moderator decides.
- `report_count` is the lifetime counter of every report, counting or not.

#### Step 7: What counts

**Where:** Terminal window 2.

**What this does:** Shows the two rules that decide whether a report counts: a brand-new account with no activity
doesn't, and a report older than the window stops counting. The `flags` helper lists each reporter and whether their
report counts; `counting` counts the open, counting reports inside the window.

```bash
flags() { python manage.py shell -c "from apps.reports.models import Report; print(sorted((r.reporter.username.rsplit('_', 2)[1], r.counts_toward_threshold) for r in Report.objects.filter(post_id='$1')))" | tail -1; }   # flags <post id>
counting() { python manage.py shell -c "import datetime; from django.utils import timezone; from apps.core.services import get_platform_settings; from apps.reports.models import Report; c = get_platform_settings(); n = Report.objects.filter(post_id='$1', status='open', counts_toward_threshold=True, created_at__gte=timezone.now() - datetime.timedelta(hours=c.report_window_hours)).count(); print('counting reports in the window:', n, 'of', Report.objects.filter(post_id='$1').count())" | tail -1; }   # counting <post id>
report $fact1 "$hal" '{"reason":"inaccurate"}'        # 1: hal has never posted or commented, and the account is new
flags $fact1                                          # 2: stored as "does not count"
get /posts/$fact1/ "" '{status}'                      # 3: so it does not move the post
hal1=$(mk "$hal" '{"content":"My first post.","post_type":"opinion"}')   # 4: hal takes part
report $op1 "$hal" '{"reason":"spam"}'                # 5: now a report by hal counts
flags $op1                                            # 6: six reports, all counting
counting $op1                                         # 7: inside the 24-hour window
python manage.py shell -c "import datetime; from django.utils import timezone; from apps.reports.models import Report; r = Report.objects.filter(post_id='$op1', reporter__username='part8_ada_$id').get(); r.created_at = timezone.now() - datetime.timedelta(hours=25); r.save(); print('one report moved 25 hours back')" | tail -1
counting $op1                                         # 8: it fell out of the window
```

**You should see** (the order of the list is by name):

```text
201  {"reported":true}
[('hal', False)]
200  {"status":"pending"}
201  {"reported":true}
[('ada', True), ('cy', True), ('ed', True), ('fay', True), ('gus', True), ('hal', True)]
counting reports in the window: 6 of 6
one report moved 25 hours back
counting reports in the window: 5 of 6
```

- `hal`'s first report is stored as "does not count" (2): the account is under 24 hours old and has no post or
  comment, which is how a crowd of fresh sign-ups is kept from sending a post to review. It still adds to the
  lifetime counter, but the post doesn't move (3).
- After `hal` posts something (4) a report from `hal` counts (6). A post or comment the person **deleted** still counts;
  one a moderator removed or hid doesn't.
- A report older than 24 hours (the window, from the settings) stops counting toward the threshold (8). It stays on
  record. Once a post is under review it stays there; only a moderator moves it back.

#### Step 8: A FALSE post goes to review too, and can't be reposted meanwhile

**Where:** Terminal window 2.

**What this does:** Labels a fact FALSE (a shell command stands in for the moderator tools of Part 10), has five people
report it, and then tries to repost it. Reports can move a post that is labelled FALSE to review, which shows
UNDER REVIEW instead of FALSE; the page remembers what it was.

```bash
false1=$(mk "$bo" '{"content":"The moon is made of green cheese.","post_type":"fact"}')
python manage.py shell -c "from apps.posts.models import Post; print(Post.objects.filter(pk='$false1').update(status='verified_false', verdict_source='moderator'), 'post marked FALSE')" | tail -1
get /posts/$false1/ "" '{status}'                     # 1: labelled FALSE
for t in "$ada" "$cy" "$ed" "$fay" "$gus"; do report $false1 "$t" '{"reason":"inaccurate"}'; done   # 2: five people report it
get /posts/$false1/ "" '{status}'                     # 3: now UNDER REVIEW (it was FALSE until the reports)
state $false1                                         # 4: and it remembers it was FALSE
send POST /posts/$false1/repost/ "$hal"               # 5: it can't be reposted meanwhile, as before
send POST /posts/$op1/repost/ "$hal"                  # 6: a post that was never FALSE can be reposted while under review
```

**You should see:**

```text
1 post marked FALSE
200  {"status":"verified_false"}
201  {"reported":true}
201  {"reported":true}
201  {"reported":true}
201  {"reported":true}
201  {"reported":true}
200  {"status":"under_review"}
under_review reports verified_false report_count=5
409  {"detail":"Posts labelled FALSE can't be reposted.","code":"cannot_repost_false"}
201  {"reposted":true}
```

- After the fifth report the post shows UNDER REVIEW (3), with `pre_review_status` `verified_false` (4): a moderator's
  **Dismiss** puts the FALSE label back (Part 10).
- It can't be reposted meanwhile (5): otherwise a group could report a FALSE post to reopen it to reposts. The check
  is the same `409` `cannot_repost_false` as for a FALSE post. The page can't know this in advance (the earlier status
  is never public), so the repost button answers with the toast "Posts labelled FALSE can't be reposted."
- A post that was never FALSE can be reposted while it is under review (6), as in Part 7B.

#### Step 9: Reporting is rate limited

**Where:** Terminal window 2.

**What this does:** Uses up `ivy`'s allowance of 10 reports an hour. `bo` makes 11 posts for her to report; the
eleventh request is refused.

```bash
for i in $(seq 11); do ids[$i]=$(mk "$bo" "{\"content\":\"Post number $i for the limit.\",\"post_type\":\"opinion\"}"); done   # bo makes 11 posts
for i in $(seq 10); do report ${ids[$i]} "$ivy" '{"reason":"spam"}'; done | sort | uniq -c    # 1: ivy reports ten of them
report ${ids[11]} "$ivy" '{"reason":"spam"}'          # 2: the eleventh in an hour
curl -si -X POST -H "Authorization: Bearer $ivy" -H "Content-Type: application/json" --data-binary '{"reason":"spam"}' $api/posts/${ids[11]}/report/ | grep -i '^retry-after'   # 3: how long to wait
send POST /posts/${ids[11]}/like/ "$ivy"              # 4: likes have their own allowance
```

**You should see** (the seconds differ):

```text
     10 201  {"reported":true}
429  {"detail":"Request was throttled. Expected available in 3600 seconds.","code":"throttled"}
Retry-After: 3600
201  {"liked":true}
```

- Ten reports went through, the eleventh was refused with `429`, `"code":"throttled"` and a `Retry-After` in seconds.
- Likes have their own allowance (4), so a like still works. A 401 or an unverified email never counts; a 400 does
  (the tests cover both, with the real 10 requests).

#### Step 10: The flag and the report dialog

**Where:** Browser, with `runserver` (window 1) and `npm run dev` (window 3) running. Log in at
http://localhost:3000/login as `part8-cy-<id>@example.test` (use the `id` from step 3: `echo $id`) with the password
`correct-horse-battery-42` (`cy` was verified in step 3).

**What this does:** Looks at the flag on the cards and walks through the dialog, as a signed-in reader.

| Do this | Expect |
|---|---|
| Open http://localhost:3000/home | Every card ends with a hairline, then (left) a **heart**, a **speech bubble** and a **two-arrow repost glyph** with counts, and (right) a small **bookmark** glyph and a small **flag**. `cy`'s own post ("I enjoy the rain.") has **no flag**. The tram post (`cy` reported it in step 4) has a **filled blue flag**, and shows **UNDER REVIEW** with its text. |
| Click the flag on "Solar capacity grew by roughly 30% worldwide last year." | A dialog **"Report this post"** with a small label "REPORT" above its title and a flag glyph beside it. It quotes the post in a grey card (author, handle, the claim in serif). Below: **"Why are you reporting this post?"** with five cards: **False or inaccurate**, **Missing context or misleading**, **Harassment or defamation**, **Spam or fake accounts**, **Something else**, each with one plain line. **None is chosen.** The first radio has the focus ring. Under them a **Details** box with "0 / 500 characters" and "Optional.". At the bottom a light-blue note **"What happens next"** (scroll the dialog if you can't see it), and in the footer a fingerprint and "Reports are private. The author is never told who reported.", **Cancel** and **Submit report**. |
| Click **Submit report** with nothing chosen | A red **"Choose a reason."** under the five cards; the focus goes to the first one; nothing is sent. |
| Choose **Something else** (the Details hint becomes "Required for “Something else”."), click **Submit report** | A red **"Tell us what's wrong."** under the box, and the focus goes to the box. Typing clears it. |
| Type a sentence in Details and click **Submit report** | The button shows a spinner for a moment, then the dialog closes and a toast says **"Report sent. Thank you."** The flag is now **filled and blue**, and **keyboard focus is on it**. |
| Click the filled flag | Nothing opens; a toast says "You already reported this post." Hover it: the tooltip says "You reported this". |
| Reload the page | The flag is still filled. The post is **not** under review: it has two reports (`hal`'s and `cy`'s) and only one of them counts. |
| Open a private window and go to /home (a visitor) | The same cards. The flag is a **link**: it points to `/login?next=%2Fp%2F<id>` and its tooltip says "Log in to report". |
| In another window log in as `dee` (`part8-dee-<id>@example.test`, same password: never verified) and click a flag | It looks dimmed and no dialog opens; a toast says "Verify your email to report posts. Check your inbox for the link." |

- Choosing a reason clears its error; the dialog can't be closed (Esc, ×, Cancel) while a report is being sent, and its
  fields are locked meanwhile.
- If the server refuses after the request (a 429 after ten reports, a network error), the dialog stays open with your
  choices and says so, for example "You're reporting too fast. Try again in about 60 minutes." (the unit tests cover every
  answer; step 9 shows the 429 itself).
- Covered by `ReportModal.test.tsx` (every state above, each server answer, the locked form, the focus after a server error),
  `ReportButton.test.tsx` (visitor, loading, own post, unverified, reported, resync from the server, the same button
  keeping focus), `PostActions.test.tsx`, `FeedList.test.tsx` and the new E2E tests.
- No dialog exists until a flag is clicked: a feed of 20 cards carries 20 flags and no dialog.

#### Step 11: The post page, your own posts and the under-review badge

**Where:** Browser, logged in as `cy`, with both servers running.

**What this does:** Opens the post page, where the flag has a word, and checks the places where there must be no flag.

| Do this | Expect |
|---|---|
| Click the tram post's text on /home | The post page. The claim card shows **UNDER REVIEW** and the full text. The action row reads **Like, Comments, Repost** with words (from 640 px up), the **bookmark** glyph, then a **filled blue flag with the word "Reported"**, and **Copy link**. |
| Open the page of "Solar capacity grew …" (the post you reported in step 10) | The same row with **"Reported"**. |
| Open a post that `cy` has not reported (for example the first "Post number 1 for the limit.") | The row ends with an outline flag and **"Report"**. Click it: the same dialog opens. Press **Esc**: it closes and focus returns to the flag. |
| Open the page of `cy`'s own post (click "I enjoy the rain." on /home, the one by `cy`) | The row has **no flag and no Report**, only the other buttons and a **Delete** button. |

- A removed post can't be made here (moderator removal arrives with Part 10); its page has no Report, covered by
  `PostDetail.test.tsx` along with a Report for a reader, a log-in link for a visitor, "You reported this" from the
  signed-in view and none on your own post. The E2E tests cover the rest.

#### Step 12: A phone-sized window

**Where:** Browser, logged in as `cy`.

**What this does:** Checks the new parts at phone width. In Firefox or Chrome press `F12`, then the "responsive
design" / device toolbar button, and set the width to 390.

| Do this | Expect |
|---|---|
| Open /home | Each card's bar (heart, count, bubble, count, repost, count, and the bookmark and flag at the right) fits on one line under the claim. **No sideways scrolling.** |
| Click a flag | The dialog fits the screen: its body scrolls, the footer (the privacy line, then **Cancel** and **Submit report**) stays at the bottom, and there is **no sideways scrolling**. A long claim in the quote is cut after three lines. |
| Open a post's page | The action row holds the glyphs with their counts only (the words are hidden below 640 px), the bookmark, the flag and **Copy link**, wrapping to a second line if needed. |

- Measured with headless Chromium at 390 px: 0 px of horizontal overflow on `/home`, in the open dialog and on a post's
  page.

#### Step 13: Django Admin: reports

**Where:** Browser, while `runserver` is running in window 1.

**What this does:** Opens the new admin list as a superuser. Reports are read-only: they are written only by the
report service (it holds the row lock and works out whether the report counts); resolving them is Part 10.

| URL / action | Expect |
|---|---|
| http://localhost:8000/admin/ (superuser from Part 0A; if it 404s, `ADMIN_URL_PATH` in `backend/.env` isn't `admin/`: use that path) | **Reports** is listed in the sidebar. |
| http://localhost:8000/admin/reports/report/ | **Select report to view**: post, reporter, **Reason**, status, whether it counts toward the threshold and the time, newest first; a search box (reporter username) and filters **By status**, **By reason**, **By counts toward threshold** and **By created at**. The list **never shows the details text**. No **Add report** button. |
| Click a report whose reason is **Something else** | Its page shows the details you typed, read-only: no **Save**, no **Delete**. http://localhost:8000/admin/reports/report/add/ answers **403**. |

- A moderator gets no permissions at all until Part 10 (it also adds the review queue and **Dismiss**), so a moderator who opens
  the list is refused (403) today; with only `view_report` they could read it but not change anything. Covered by
  `test_admin.py`; the superuser clicks above were run with a scripted browser, not by a person.

#### Step 14: Stop and clean up

**Where:** Every terminal window, plus the browser.

- Stop the servers: `Ctrl+C` in windows 1 and 3 (a leftover `next dev`: step 12 of Part 1).
- Delete the test accounts, their posts, reposts, likes and reports (all go with the accounts). In window 2, in `backend/` with
  the venv active:

  ```bash
  python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(email__startswith='part8-').delete())" | tail -1
  ```

  After one clean run of steps 3 to 9 of this guide it prints `(62, {'social.Like': 1, 'social.Repost': 1, 'reports.Report': 22, 'account.EmailAddress': 9, 'posts.Post': 20, 'accounts.User': 9})`:
  how many rows went in all, and per table (22 reports: 2 and then 3 on the tram post, 2 by `hal`, 5 on the FALSE post and
  10 by `ivy`; 20 posts: 14 by `bo` (the tram post, the solar fact, the FALSE one and the 11 for the limit), `hal`'s one and
  the five opinions; 1 repost, `hal`'s of the tram post; 1 like, `ivy`'s). Your count differs if you did the browser steps
  (more reports) or made other accounts. Nothing else is touched.
  (The E2E tests' accounts stay in your local database, as in earlier parts: Django Admin → Users deletes them.)
- `docker compose down` (repo root) stops the containers and keeps the data; `docker compose down -v`
  wipes the whole local database, which is destructive.
- No secret was used or printed in this part: the only values in the commands are Cloudflare's public test
  token and the throwaway password of the test accounts.

---

### Part 9: Fact-check pipeline stub + routing

Needs Part 0A's containers and virtualenv, Part 0C's frontend, and your own `backend/.env` and
`frontend/.env.local`. Part 9 adds **no migration**, **no dependency** and **no new variable** (`PIPELINE_BACKEND`,
`PIPELINE_INLINE_KICK`, `PIPELINE_URL`, `PIPELINE_API_KEY` and `INTERNAL_CRON_SECRET` were already in
`backend/.env.example`; Django now reads them). It makes fact posts get a verdict: the built-in **stub pipeline**, the
rules that turn its answer into VERIFIED, FALSE or UNDER REVIEW, and three ways to run it: the **inline kick** (a
background thread right after a fact is saved), the hourly **tick** `POST /api/internal/tick/` (cron-job.org, Part
17) and `python manage.py process_pending` for local dev.

**Which terminal window for what.** Open the windows once and keep using the same ones:

| Window | What runs in it | Used in steps |
|---|---|---|
| Window 1 (server) | `python manage.py runserver` in `backend`, venv active. Leave it running. Start it in step 3, **after** step 2 (Playwright starts its own servers and needs ports 3000 and 8000 free). Step 7 restarts it with the kick off and step 12 restarts it normally. | 3 to 14 |
| Window 2 (commands) | All the `curl` and `python manage.py` commands. **Use the same window for steps 3 to 11**: the variables and functions you set in step 3 (`id`, `ada`, `bo`, `cy`, `dee`, `api`, `mk`, `get`, `send`) and later (`t1` … `o1`, `src`, `k1` … `k3`, `secret`, `tick`, `l1`, `r1`, `f1`) only live in that one terminal. If you close it, redo step 3. | 1 to 11, 15 |
| Window 3 (frontend) | `npm run dev` in `frontend`. Leave it running. | 12 to 14 |
| Window 4 (sweeper) | `python manage.py process_pending --loop` in `backend`, venv active, for one step | 9 |
| Browser | Steps 12 to 14 | 12 to 14 |

Things to know first:

- **The stub's rules** (ARCHITECTURE §6): a fact whose text contains `#true` gets VERIFIED 95%, `#false` gets FALSE
  92%, `#unsure` goes to UNDER REVIEW (confidence 40). The first of these tags in the text wins, in any case, and only
  as a whole tag (`#trueish` is not one). Any other text gets a confidence of 50 to 99 and "true" or "false" from a
  hash of the text, so the same text always gets the same answer; below the threshold (85) it goes to UNDER REVIEW.
  Opinions are never checked. The stub ignores sources (a real pipeline would read them).
- **Not for production as it is** (user decision 2026-10-11, a launch blocker for Part 17): with the stub any
  author can write `#true` to get VERIFIED 95%.
- Steps 3 to 11 talk to the API with `curl` (they need `jq`: `sudo apt install jq`) and to Django with
  `python manage.py shell`. Steps 12 to 14 use the browser. Step 3 makes four verified accounts: `ada` posts the facts
  of steps 4 to 6, `bo` and `cy` those of steps 7 to 10, `dee` reposts in step 10 and posts in step 11 and in the browser.
- The API and command outputs below were recorded on Linux on 2026-10-11. The browser steps were checked the same day
  with headless Chromium (screenshots at 1280 and 390 px) and Django Admin with a scripted browser, not by a person at
  a keyboard. Ids, numbers in names, times and seconds differ on every run.
- Nothing here sends an email: step 3 marks the accounts verified with a shell command, which stands in for clicking
  the link (Part 2 shows the real flow). Step 10 puts a post under review the same way, standing in for five reports
  (Part 8 shows real ones), and step 11 stands in a pipeline that never answers for the stub.
- **The numbers assume the default settings** (confidence threshold 85, 10 fact posts per person per 24 hours). The
  backend seeds them from your own `backend/.env` the first time; step 3 prints yours.
- Every check is logged in window 1 (or in window 2 when a `python manage.py` command runs it), one line per post:
  `… INFO apps.pipeline.processor: Pipeline: post <id> -> labelled` (or `entered_review`, `updated_review`, `retry`).

#### Step 1: Run the automated backend checks

**Where:** Terminal window 2 (commands), starting in the repo root.

**What this does:** Starts the database containers, activates the Python environment, confirms there is no migration
to apply or make, then runs the whole backend test suite, Part 9's tests, the linter and the formatter check.

```bash
# start in the repo root
docker compose up -d
cd backend
source .venv/bin/activate
python manage.py migrate                            # No migrations to apply.
python manage.py makemigrations --check --dry-run   # No changes detected
python manage.py check                              # System check identified no issues (0 silenced).
python -m pytest                                    # 2359 passed
python -m pytest apps/pipeline apps/core/tests/test_tick.py apps/posts/tests/test_services_pipeline.py -q   # 312 passed
ruff check . ; ruff format --check .                # All checks passed! / 200 files already formatted
```

**You should see:** `No migrations to apply.`, `No changes detected` and `System check identified no issues (0
silenced).`, then the full run ends with `2359 passed`, the pipeline run with `312 passed`, and the last line pair is
`All checks passed!` and `200 files already formatted`. (Counts may grow later; what matters is that nothing fails.)

- The pipeline run holds Part 8's 45 routing tests and 267 new ones: `test_contract.py` (61: what a request and a
  result may hold, the confidence rounded half up to two places), `test_stub_client.py` (29: each tag, the first tag
  wins, whole tags only, the hash rule pinned to fixed answers), `test_http_client.py` (35: the request it would send,
  every way a call can fail, no redirect followed, at most 64 KB, a 20 s limit, the key never in an error), 
  `test_routing_pipeline.py` (55: every pipeline row of the ARCHITECTURE §4 table, retries after 2, 4, 8 and 16
  minutes and a moderator after five), `test_queue.py` (8: which posts wait for a check, in what order),
  `test_processor.py` (32: the lease, a try that dies mid-call, what happens when a report, a delete, a moderator or a
  dismissal arrives while a check is running), `test_races.py` (5: real threads: two sweepers never check the same
  post, a locked post is skipped, the post is never locked while the pipeline thinks, the kick waits for a moment's
  lock), `test_kick.py` (10), `test_command.py` (7), `test_no_network.py` (1), plus `apps/core/tests/test_tick.py`
  (11) and `apps/posts/tests/test_services_pipeline.py` (13).
- Some more in `apps/core/tests/test_settings.py` (the four `PIPELINE_*` variables are checked at startup) and in
  `apps/posts/tests/` (who decided a label is public only with the label).

#### Step 2: Run the automated frontend checks

**Where:** Terminal window 2, then `cd ../frontend`. Playwright (the last two commands) starts Django and
Next itself, so **no servers may be running on ports 3000 and 8000** (it reuses them if they are, with
whatever settings they have; a reused Django must also run with `PIPELINE_INLINE_KICK=False`).

**What this does:** Runs the linters, the type check, the component tests, the production build and the
end-to-end tests.

```bash
cd ../frontend                                      # from backend/
npm run lint ; npm run lint:tokens ; npm run typecheck ; npm run format:check
npm test                                            # 117 files, 1587 tests passed
NEXT_PUBLIC_GOOGLE_CLIENT_ID= npm run build
npm run test:e2e                                    # 38 passed
CI=1 npm run test:e2e                               # 38 passed (against the production build)
cd ../backend                                       # back to backend/ for steps 3 to 11
```

**You should see:** the first line prints nothing from ESLint and TypeScript and ends with
`lint:tokens OK (…)` and `All matched files use Prettier code style!`. `npm test` ends with
`Test Files  117 passed (117)` and `Tests  1587 passed (1587)`. `npm run build` lists the same routes as in Part 8
(Part 9 adds no page). Each E2E run ends with `38 passed`.

- Part 9 changes no page: the verdict copy ("Checked automatically · 95% confidence", "Reviewed by a moderator") and
  the badge polling came with Part 5. Seven new component tests pin the badges and the copy for the stub's real
  answers.
- The E2E backend runs with the stub and **without the kick** (`playwright.config.ts`): several tests need a new fact
  to stay CHECKING FACTS…. The test "a #true fact is checked by the pipeline and its badge turns VERIFIED by itself"
  (in `e2e/post-detail.spec.ts`, which used to flip the status by hand) now runs the real pipeline for its own post
  only (`processPost()` in `e2e/helpers.ts`) and waits for VERIFIED 95% on the card and the post page. No new sign-up.

#### Step 3: Start the servers and make four accounts

**Where:** First window 1 (the Django server) and window 3 (the frontend), then window 2 (the commands).
**Keep using window 2 for steps 4 to 11.**

**What this does:** Windows 1 and 3 run the two servers, with your own settings (the kick is on). In window 2 you sign
up four accounts through the API, mark them verified, and print the pipeline settings the backend uses. The helpers
`mk` (make a post, print its id), `send` (any request, printing the status code and then the answer) and `get` (the
same for a GET) are used by every later step.

Window 1 (in `backend`, venv active):

```bash
python manage.py runserver                          # leave it running
```

Window 3:

```bash
cd frontend                                         # from the repo root
npm run dev                                         # leave it running
```

Window 2 (in `backend` with the venv active: steps 1 and 2 leave you there; needs `jq`). If you opened a new
terminal, first run `cd backend` from the repo root and `source .venv/bin/activate`:

```bash
id=$(date +%H%M%S)                                  # a unique suffix so the addresses are new each run
h=(-H 'Origin: http://localhost:3000' -H 'X-Requested-With: rumor-zero')   # headers every auth call needs
signup() { jq -nc --arg e "$1" --arg u "$2" '{email: $e, username: $u, password: "correct-horse-battery-42", turnstile_token: "XXXX.DUMMY.TOKEN.XXXX"}' | curl -s "${h[@]}" -H "Content-Type: application/json" --data-binary @- http://localhost:8000/api/auth/app/v1/auth/signup | jq -r .meta.access_token; }
ada=$(signup "part9-ada-$id@example.test" "part9_ada_$id")      # $ada = ada's login token (the facts of steps 4 to 6)
bo=$(signup "part9-bo-$id@example.test" "part9_bo_$id")         # $bo, $cy = the facts of steps 7 to 10
cy=$(signup "part9-cy-$id@example.test" "part9_cy_$id")
dee=$(signup "part9-dee-$id@example.test" "part9_dee_$id")      # $dee = reposts in step 10, posts in step 11 and the browser
python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(email__startswith='part9-', email__endswith='$id@example.test').update(is_email_verified=True), 'accounts marked verified')" | tail -1
api=http://localhost:8000/api/v1
mk() { curl -s -H "Authorization: Bearer $1" -H "Content-Type: application/json" --data-binary "$2" $api/posts/ | jq -r .id; }   # mk <token> <json>: makes a post, prints its id
get() { local out; out=$(curl -s -w '\n%{http_code}' ${2:+-H "Authorization: Bearer $2"} "$api$1"); printf '%s  ' "${out##*$'\n'}"; printf '%s' "${out%$'\n'*}" | jq -c "${3:-.}"; }   # get <path> [token] [jq filter]: prints the status code, then the answer
send() { local out; out=$(curl -s -w '\n%{http_code}' -X "$1" ${3:+-H "Authorization: Bearer $3"} ${4:+-H "Content-Type: application/json" --data-binary "$4"} "$api$2"); printf '%s  %s\n' "${out##*$'\n'}" "$(printf '%s' "${out%$'\n'*}" | jq -c "${5:-.}" 2>/dev/null)"; }   # send <METHOD> <path> [token] [json body] [jq filter]: prints the status code, then the answer
python manage.py shell -c "from django.conf import settings; from apps.core.services import get_platform_settings as g; c = g(); print(settings.PIPELINE_BACKEND, settings.PIPELINE_INLINE_KICK, c.confidence_threshold, c.fact_posts_per_day)" | tail -1
echo ${ada:0:10} ${bo:0:10} ${cy:0:10} ${dee:0:10}     # four prefixes, not an empty line
```

**You should see:**

```text
4 accounts marked verified
stub True 85 10
eyJhbGciOi eyJhbGciOi eyJhbGciOi eyJhbGciOi
```

- The second line is the pipeline (`stub`), the kick (`True`), the confidence threshold (`85`) and the fact posts each
  person may make in 24 hours (`10`; steps 4 to 11 need at most 9 per account). If your threshold isn't 85, the
  untagged facts in step 4 may land differently; if your allowance is lower, some posts are refused (`null` ids).
- The shell prints a line about auto-imported objects first; `tail -1` keeps only ours.
- Sign-up is limited to 20 a minute per address (Part 1), and still calls Cloudflare's test widget, so it
  needs internet.

**If it differs:** an empty token means the sign-up failed: `runserver` isn't running, `jq` is missing, or you signed
up more than 20 times in a minute. Fix that and run this step again from `id=$(date +%H%M%S)`.

#### Step 4: The inline kick checks each fact right after it is saved

**Where:** Terminal window 2 (the same terminal as step 3). Window 1 must be running `runserver` with your normal
settings (the kick on).

**What this does:** `ada` posts three facts with the stub's tags, three without, and an opinion. The answer to the
post itself still says `pending` (the check runs after the post is saved); a second later every fact has its verdict.

```bash
r=$(curl -s -H "Authorization: Bearer $ada" -H "Content-Type: application/json" --data-binary '{"content":"Water boils at 100 degrees Celsius at sea level. #true","post_type":"fact"}' $api/posts/)
echo "$r" | jq -c '{status, confidence_score, verdict_source}'   # 1: the 201 answer
t1=$(echo "$r" | jq -r .id)
t2=$(mk "$ada" '{"content":"The Great Wall of China is visible from the Moon. #false","post_type":"fact"}')
t3=$(mk "$ada" '{"content":"Coffee stunts your growth. #unsure","post_type":"fact"}')
h1=$(mk "$ada" '{"content":"Honey never spoils.","post_type":"fact"}')
h2=$(mk "$ada" '{"content":"Sharks are older than trees.","post_type":"fact"}')
h3=$(mk "$ada" '{"content":"The Moon orbits the Earth.","post_type":"fact"}')
o1=$(mk "$ada" '{"content":"I think tea beats coffee.","post_type":"opinion"}')
sleep 1                                             # the checks take a few milliseconds
for p in $t1 $t2 $t3 $h1 $h2 $h3 $o1; do get /posts/$p/ "" '{content, status, confidence_score, verdict_source}'; done   # 2 to 8
```

**You should see:**

```text
{"status":"pending","confidence_score":null,"verdict_source":null}
200  {"content":"Water boils at 100 degrees Celsius at sea level. #true","status":"verified_true","confidence_score":"95.00","verdict_source":"pipeline"}
200  {"content":"The Great Wall of China is visible from the Moon. #false","status":"verified_false","confidence_score":"92.00","verdict_source":"pipeline"}
200  {"content":"Coffee stunts your growth. #unsure","status":"under_review","confidence_score":null,"verdict_source":null}
200  {"content":"Honey never spoils.","status":"verified_true","confidence_score":"88.00","verdict_source":"pipeline"}
200  {"content":"Sharks are older than trees.","status":"verified_false","confidence_score":"95.00","verdict_source":"pipeline"}
200  {"content":"The Moon orbits the Earth.","status":"under_review","confidence_score":null,"verdict_source":null}
200  {"content":"I think tea beats coffee.","status":"published","confidence_score":null,"verdict_source":null}
```

- 1: a new fact is always `pending` in its own answer; the browser shows "Checking facts…" and its polling (Part 5)
  picks up the verdict (step 12).
- 2 to 4: the three tags. 5 to 7: no tag, so the hash of the text decides: "Honey never spoils." gets true at 88 and
  "Sharks are older than trees." false at 95 (both at or above 85, so labelled), "The Moon orbits the Earth." true at
  65, below the threshold, so a moderator decides (UNDER REVIEW). The same text always gets the same answer.
- Under review, the post shows no confidence and no "who decided": only a label shows them.
- 8: the opinion is `published` and never checked.
- Window 1 printed one `Pipeline: post … -> labelled` (or `-> entered_review`) line per fact, a few milliseconds
  after each post.

#### Step 5: What the pipeline stored, and what stays private

**Where:** Terminal window 2.

**What this does:** Reads three of the posts straight from the database, then checks that none of the pipeline's
own fields shows in the API.

```bash
python manage.py shell -c "from apps.posts.models import Post
for pk in '$t1 $t3 $h3'.split():
    p = Post.objects.get(pk=pk)
    print(p.status, p.flagged_reason, p.pre_review_status, p.pipeline_verdict, p.confidence_score, p.pipeline_result, p.pipeline_attempts, p.pipeline_next_attempt_at, round((p.pipeline_checked_at - p.created_at).total_seconds(), 2))" | tail -3     # 1 to 3
get /posts/$t3/ "" 'keys | map(select(test("pipeline|flag|attempt|review")))'          # 4: none of it is public
get "/posts/status/?ids=$t1,$t3" "" '[.results[] | {status, confidence_score, verdict_source}]'   # 5: what the badge poller sees
```

**You should see** (the last number on lines 1 to 3, the seconds between posting and the verdict, differs):

```text
verified_true None None true 95.00 {'rule': '#true', 'stub': True} 1 None 0.03
under_review pipeline pending inconclusive 40.00 {'rule': '#unsure', 'stub': True} 1 None 0.01
under_review pipeline pending true 65.00 {'rule': 'hash', 'stub': True} 1 None 0.01
200  []
200  [{"status":"verified_true","confidence_score":"95.00","verdict_source":"pipeline"},{"status":"under_review","confidence_score":null,"verdict_source":null}]
```

- Each line: the status, why it is under review (`pipeline`: the check couldn't decide) and what it was before, then
  the pipeline's verdict, confidence and raw answer, the number of tries, when to try again (`None`: done), and how
  long after the post the verdict came.
- The verdict and confidence are kept even for a post under review: a moderator sees them in Django Admin (step 14),
  the public doesn't.

#### Step 6: The sources go to the pipeline in the author's order

**Where:** Terminal window 2.

**What this does:** `ada` posts a fact with two sources (a URL, then a DOI). The stub ignores them, but the request a
real pipeline would get (`{post_id, content, sources}`) carries them, in order; a fact without sources sends an empty
list. Nothing ever opens the links.

```bash
src=$(mk "$ada" '{"content":"Solar capacity grew by roughly 30% worldwide last year. #true","post_type":"fact","sources":["https://www.iea.org/reports/renewables-2023","doi:10.1038/s41558-024-02102"]}')
for p in $src $t1; do python manage.py shell -c "import json; from apps.pipeline.contract import PipelineRequest; from apps.posts.models import Post; print(json.dumps(PipelineRequest.for_post(Post.objects.get(pk='$p')).to_json()['sources']))" | tail -1; done   # 1 and 2
```

**You should see:**

```text
["https://www.iea.org/reports/renewables-2023", "10.1038/s41558-024-02102"]
[]
```

- 1: the URL first, then the DOI (stored bare, without `doi:`), as the author entered them. 2: the fact from step 4,
  which has none.
- The tests also check the body the HTTP client would send to a real pipeline, and that the only address it ever
  opens is `PIPELINE_URL` (`test_http_client.py`).

#### Step 7: With the kick off, facts wait until `process_pending` checks them

**Where:** First window 1, then window 2.

**What this does:** Restarts the server **without** the inline kick, the way it runs when the kick is missed (a worker
restart, a sleeping server). New facts then stay pending until something checks them: here the management command.

Window 1: press `Ctrl+C`, then:

```bash
PIPELINE_INLINE_KICK=False python manage.py runserver   # the kick off for this server only; leave it running
```

Window 2:

```bash
python manage.py process_pending | tail -1          # 1: first clears whatever was already waiting
k1=$(mk "$bo" '{"content":"Mount Everest is the tallest mountain above sea level. #true","post_type":"fact"}')
k2=$(mk "$bo" '{"content":"Lightning never strikes the same place twice. #false","post_type":"fact"}')
k3=$(mk "$bo" '{"content":"Cracking your knuckles causes arthritis. #unsure","post_type":"fact"}')
sleep 1
for p in $k1 $k2 $k3; do get /posts/$p/ "" '{status}'; done                          # 2 to 4: nothing checked them
python manage.py process_pending                    # 5: checks the three
for p in $k1 $k2 $k3; do get /posts/$p/ "" '{status, confidence_score, verdict_source}'; done   # 6 to 8
python manage.py process_pending                    # 9: nothing left
```

**You should see** (the first number, the times and the ids differ):

```text
Processed 0 fact posts.
200  {"status":"pending"}
200  {"status":"pending"}
200  {"status":"pending"}
2026-10-10 19:12:51,727 INFO apps.pipeline.processor: Pipeline: post 50f256c2-fa78-4b3d-84d0-b7722b706d56 -> labelled
2026-10-10 19:12:51,733 INFO apps.pipeline.processor: Pipeline: post 0a17e2de-93dd-4595-b0e2-c04423d713d9 -> labelled
2026-10-10 19:12:51,737 INFO apps.pipeline.processor: Pipeline: post 069209e7-a9b5-417f-8706-789ca174f8c4 -> entered_review
Processed 3 fact posts.
200  {"status":"verified_true","confidence_score":"95.00","verdict_source":"pipeline"}
200  {"status":"verified_false","confidence_score":"92.00","verdict_source":"pipeline"}
200  {"status":"under_review","confidence_score":null,"verdict_source":null}
Processed 0 fact posts.
```

- 1: the end-to-end tests (step 2) leave pending facts in your local database, because their backend runs without the
  kick, so the first run checks those too: any number, 0 included (it printed `Processed 116 fact posts.` the first
  time on this machine, then 0). `tail -1` hides their log lines.
- 5: one log line per post, then the count. One run checks **everything** that is due, in batches of 10
  (`--limit` changes the batch size).

#### Step 8: The tick needs the secret, and takes ten posts at a time

**Where:** Terminal window 2. Window 1 still runs without the kick.

**What this does:** The tick is what cron-job.org will call every hour (Part 17). It needs the `X-RZ-Cron-Secret`
header, read here from your own `backend/.env` without printing it. Then `bo` and `cy` leave twelve facts waiting and
three ticks clear them.

```bash
secret=$(grep -m1 '^INTERNAL_CRON_SECRET=' .env | cut -d= -f2- | tr -d '\r')    # sets $secret; nothing is printed
tick() { local out last; out=$(curl -s -w '\n%{http_code} %{time_total}' -X "${2:-POST}" ${1:+-H "X-RZ-Cron-Secret: $1"} http://localhost:8000/api/internal/tick/); last=${out##*$'\n'}; printf '%s  %s  (%s s)\n' "${last% *}" "${out%$'\n'*}" "${last#* }"; }   # tick [secret] [method]: prints the status, the answer and how long it took
tick                                                # 1: no secret
tick wrong-secret                                   # 2: a wrong one
tick "$secret" GET                                  # 3: the right one, but not a POST
tick "$secret"                                      # 4: nothing waits
for i in $(seq 6); do mk "$bo" "{\"content\":\"Backlog claim $i from bo. #true\",\"post_type\":\"fact\"}" > /dev/null; mk "$cy" "{\"content\":\"Backlog claim $i from cy. #false\",\"post_type\":\"fact\"}" > /dev/null; done   # twelve facts wait
tick "$secret"                                      # 5: ten of them
tick "$secret"                                      # 6: the other two
tick "$secret"                                      # 7: none left
```

**You should see** (the seconds differ):

```text
403  {"detail":"You do not have permission to perform this action.","code":"permission_denied"}  (0.001658 s)
403  {"detail":"You do not have permission to perform this action.","code":"permission_denied"}  (0.000825 s)
405  {"detail":"Method \"GET\" not allowed.","code":"method_not_allowed"}  (0.000850 s)
200  {"processed":0}  (0.008398 s)
200  {"processed":10}  (0.048147 s)
200  {"processed":2}  (0.017419 s)
200  {"processed":0}  (0.007578 s)
```

- Without the right secret the tick checks nothing. With it, it takes at most **10 posts** and answers in well under
  a second with the stub; cron-job.org gives it 30 s. It stops taking new posts so it always answers within about 25 s:
  a real pipeline, which may need up to 20 s per post, would check 1 to 5 per call (the tests cover that).
- Window 1 logs one line per post checked.

**If it differs:** if every tick is 403, `$secret` is empty: `INTERNAL_CRON_SECRET` is missing from `backend/.env`.

#### Step 9: The sweeper in a loop

**Where:** A new window 4, then window 2, then window 4 again.

**What this does:** `--loop` keeps checking every few seconds, a stand-in for the kick when you run the server without
it. `cy` posts a fact and the loop picks it up.

Window 4 (from the repo root):

```bash
cd backend
source .venv/bin/activate
python manage.py process_pending --loop --interval 2      # leave it running for now
```

Window 2:

```bash
l1=$(mk "$cy" '{"content":"Octopuses have three hearts. #true","post_type":"fact"}')
sleep 3                                             # one turn of the loop
get /posts/$l1/ "" '{status, confidence_score}'
```

Then press `Ctrl+C` in window 4.

**You should see:** window 2 prints `200  {"status":"verified_true","confidence_score":"95.00"}`. Window 4 shows:

```text
Checking fact posts every 2 s. Press Ctrl+C to stop.
2026-10-10 19:12:56,906 INFO apps.pipeline.processor: Pipeline: post c923b87a-2fdd-4a19-b97c-808faa862766 -> labelled
Processed 1 fact post.
Stopped.
```

- The loop prints only when it checked something. `Ctrl+C` ends it cleanly with "Stopped." (your terminal may show
  `^C` in front of it); close window 4.

#### Step 10: A late answer on a post that reports sent to review

**Where:** Terminal window 2. Window 1 still runs without the kick (so the post isn't checked at once).

**What this does:** `cy` posts a `#false` fact, which is then put under review the way five counting reports would
(Part 8). Only then does the pipeline answer, with a decisive FALSE: a moderator must decide, and nothing reveals the
FALSE meanwhile (user decision 2026-10-11). For comparison, the FALSE post from step 4 is put under review the same
way: it was FALSE in public before, so it still can't be reposted.

```bash
r1=$(mk "$cy" '{"content":"The Sahara is growing every year. #false","post_type":"fact"}')
python manage.py shell -c "from apps.posts.models import Post; print(Post.objects.filter(pk='$r1').update(status='under_review', flagged_reason='reports', pre_review_status='pending'), 'post sent to review, as five reports would')" | tail -1    # 1
python manage.py shell -c "from apps.pipeline.processor import process_post; print(process_post('$r1'))" | tail -1    # 2: the pipeline answers late
python manage.py shell -c "from apps.posts.models import Post; p = Post.objects.get(pk='$r1'); print(p.status, p.flagged_reason, p.pre_review_status, p.verdict_source, p.pipeline_verdict, p.confidence_score)" | tail -1   # 3
get /posts/$r1/ "" '{status, confidence_score, verdict_source}'     # 4: what everyone sees
send POST /posts/$r1/repost/ "$dee"                                 # 5: dee can still repost it
python manage.py shell -c "from apps.posts.models import Post; print(Post.objects.filter(pk='$t2').update(status='under_review', flagged_reason='reports', pre_review_status='verified_false'), 'FALSE post sent to review, as five reports would')" | tail -1    # 6
send POST /posts/$t2/repost/ "$dee"                                 # 7: a post that was FALSE in public can't be
```

**You should see:**

```text
1 post sent to review, as five reports would
True
under_review both pending None false 92.00
200  {"status":"under_review","confidence_score":null,"verdict_source":null}
201  {"reposted":true}
1 FALSE post sent to review, as five reports would
409  {"detail":"Posts labelled FALSE can't be reposted.","code":"cannot_repost_false"}
```

- 3: the post stays UNDER REVIEW and its reason becomes `both` (reports and the pipeline); the FALSE and its 92% are
  kept for the moderator, but nothing is stored as the label to restore, so dismissing the reports (Part 10) can't
  make it FALSE without a human. A late **TRUE** is kept as the label a dismissal restores (the tests cover it).
- 4 and 5: from outside, nothing shows the FALSE: no confidence, no source, and reposting works.
- 7: Part 8's rule still holds for a post whose FALSE label was public before the reports.

#### Step 11: A pipeline that fails is retried, then a moderator decides

**Where:** Terminal window 2. Window 1 still runs without the kick.

**What this does:** The stub never fails, so this step stands in a pipeline that never answers and moves the clock
forward between the tries: a failed try is retried after 2, 4, 8 and 16 minutes, and after the fifth the post goes to
review.

```bash
f1=$(mk "$dee" '{"content":"A claim nobody can check today. #true","post_type":"fact"}')
python manage.py shell <<EOF | grep -v -e 'imported automatically' -e '^$'
from django.utils import timezone
from apps.pipeline.clients import PipelineError
from apps.pipeline.processor import process_post
from apps.posts.models import Post

class Down:  # a pipeline that never answers
    max_seconds = 0
    def check(self, request):
        raise PipelineError("timeout", "no answer in time")

when = timezone.now()
for _ in range(5):
    process_post("$f1", client=Down(), now=when)
    post = Post.objects.get(pk="$f1")
    wait = post.pipeline_next_attempt_at
    print(post.pipeline_attempts, post.status, post.flagged_reason, "next try in", wait - when if wait else None)
    when = wait or when
print(post.pipeline_result)
EOF
get /posts/$f1/ "" '{status, confidence_score, verdict_source}'
```

**You should see** (the times and the id differ):

```text
2026-10-10 19:13:02,399 WARNING apps.pipeline.processor: Pipeline: post c0cdf1cd-5c74-48c3-9184-11df1109645f, try 1 failed (timeout)
1 pending None next try in 0:02:00
2026-10-10 19:13:02,403 WARNING apps.pipeline.processor: Pipeline: post c0cdf1cd-5c74-48c3-9184-11df1109645f, try 2 failed (timeout)
2 pending None next try in 0:04:00
2026-10-10 19:13:02,407 WARNING apps.pipeline.processor: Pipeline: post c0cdf1cd-5c74-48c3-9184-11df1109645f, try 3 failed (timeout)
3 pending None next try in 0:08:00
2026-10-10 19:13:02,411 WARNING apps.pipeline.processor: Pipeline: post c0cdf1cd-5c74-48c3-9184-11df1109645f, try 4 failed (timeout)
4 pending None next try in 0:16:00
2026-10-10 19:13:02,415 ERROR apps.pipeline.processor: Pipeline: post c0cdf1cd-5c74-48c3-9184-11df1109645f given up after 5 tries (timeout)
5 under_review pipeline next try in None
{'error': 'timeout', 'detail': 'no answer in time', 'attempt': 5}
200  {"status":"under_review","confidence_score":null,"verdict_source":null}
```

- The post stays pending while it waits (2, 4, 8 and 16 minutes), then goes to UNDER REVIEW for the pipeline with
  the last error kept for the moderators. A failed try logs a warning; giving up logs an error (in production, one
  Sentry event per post).
- In real life nothing moves the clock: the next try happens at the next tick or loop after the wait.

#### Step 12: In the browser, a new fact's badge turns into its verdict by itself

**Where:** First window 1, then the browser, with `npm run dev` (window 3) running.

**What this does:** Restarts the server with your normal settings (the kick on), then posts three facts through the
composer and watches the cards change on their own, then opens each post's page.

Window 1: press `Ctrl+C`, then:

```bash
python manage.py runserver                          # your normal settings again; leave it running
```

Browser: log in at http://localhost:3000/login as `part9-dee-<id>@example.test` (use the `id` from step 3:
`echo $id` in window 2) with the password `correct-horse-battery-42`.

| Do this | Expect |
|---|---|
| On /home click **New post**, write `Paris is the capital of France. #true`, choose **Fact**, click **Post fact, will be checked** | A toast **"Posted. Checking the facts…"**. The new card is at the top with a grey dashed **CHECKING FACTS…** badge (a spinning glyph) and a grey stripe. After about **10 seconds**, without reloading, it turns into a teal **VERIFIED 95%** badge with a tick, and the stripe turns teal. |
| Post `The Great Wall of China is visible from space. #false` the same way | CHECKING FACTS…, then after about 10 s a red **FALSE 92%** badge with a crossed circle and a red stripe. |
| Post `Bats are blind. #unsure` | CHECKING FACTS…, then an amber **UNDER REVIEW** badge with an hourglass and an amber stripe. No percentage. |
| Click the text of the VERIFIED post | Its page: the VERIFIED 95% badge and, under **Verdict**, a teal box **"CHECKED AUTOMATICALLY · 95% CONFIDENCE"** with "This claim was found to be true." |
| Open the FALSE post's page | **"CHECKED AUTOMATICALLY · 92% CONFIDENCE"** and "This claim was found to be FALSE." The word "debunked" appears nowhere. |
| Open the UNDER REVIEW post's page | **"UNDER REVIEW"** and "A moderator is taking a look at this post. The label changes once they decide." No percentage. |
| Scroll down /home | The facts from steps 4 to 11 show their labels: VERIFIED, FALSE or UNDER REVIEW; "A claim nobody can check today." (step 11) is UNDER REVIEW. |

- The check itself takes a few milliseconds (window 1 logs it at once); the card changes at the page's first status
  check, 10 seconds after posting (Part 5's polling: 10 s, then 15, 22 …, while the tab is visible).
- Measured with headless Chromium: each of the three cards changed 10.4 s after posting.
- A moderator's verdict reads "Reviewed by a moderator" with no percentage (Part 10 adds the actions that make one).

#### Step 13: A phone-sized window

**Where:** Browser, logged in as `dee`.

**What this does:** Checks the badges at phone width. In Firefox or Chrome press `F12`, then the "responsive design" /
device toolbar button, and set the width to 390.

| Do this | Expect |
|---|---|
| Open /home | Each card shows the author line, then the FACT chip and the badge (VERIFIED 95%, FALSE 92%, UNDER REVIEW) on their own line, then the claim. **No sideways scrolling.** |
| Open the UNDER REVIEW post's page | The badge and the Verdict box fit the width. **No sideways scrolling.** |

- Measured with headless Chromium at 390 px: 0 px of horizontal overflow on `/home` and on a post's page.

#### Step 14: Django Admin: what the pipeline stored

**Where:** Browser, while `runserver` is running in window 1.

**What this does:** Shows a checked post in the read-only posts admin, with the fields the public never sees. The
review queue and the moderator actions are Part 10.

| URL / action | Expect |
|---|---|
| http://localhost:8000/admin/ (superuser from Part 0A; if it 404s, `ADMIN_URL_PATH` in `backend/.env` isn't `admin/`: use that path) | **Posts** is listed in the sidebar. |
| http://localhost:8000/admin/posts/post/, then click "Water boils at 100 degrees Celsius at sea level. #true" | **View post**, read-only (no **Save**): **Status** "Verified true", **Confidence score** 95.00, **Pipeline verdict** "True", **Pipeline result** `{"rule": "#true", "stub": true}`, **Pipeline attempts** 1, **Pipeline next attempt at** "-", **Pipeline checked at** the time, **Verdict source** "Pipeline". |
| Open "A claim nobody can check today. #true" (step 11) | **Status** "Under review", **Flagged reason** "Pipeline", **Pipeline attempts** 5, **Pipeline result** `{"error": "timeout", "detail": "no answer in time", "attempt": 5}`. |

- Checked with a scripted browser and a throwaway superuser, not by a person.

#### Step 15: Stop and clean up

**Where:** Every terminal window, plus the browser.

- Stop the servers: `Ctrl+C` in windows 1 and 3 (a leftover `next dev`: step 12 of Part 1).
- Delete the test accounts and their posts and reposts (all go with the accounts). In window 2, in `backend/` with the
  venv active:

  ```bash
  python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(email__startswith='part9-').delete())" | tail -1
  ```

  After one clean run of steps 3 to 11 of this guide it prints `(35, {'social.Repost': 1, 'account.EmailAddress': 4, 'posts.Post': 26, 'accounts.User': 4})`:
  how many rows went in all, and per table (26 posts: 8 by `ada` (steps 4 and 6), 9 by `bo` and 8 by `cy` (steps 7 to
  10), 1 by `dee` (step 11); 1 repost, `dee`'s in step 10). Your count differs if you did the browser steps (3 more
  posts) or made other accounts. Nothing else is touched; the pending facts that step 7 checked belong to the E2E
  tests' accounts, which stay in your local database as in earlier parts (Django Admin → Users deletes them).
- `docker compose down` (repo root) stops the containers and keeps the data; `docker compose down -v`
  wipes the whole local database, which is destructive.
- The only secret used is `INTERNAL_CRON_SECRET` in step 8, read from `backend/.env` into a variable and never
  printed; `unset secret` forgets it. The other values in the commands are Cloudflare's public test token and the
  throwaway password of the test accounts.

---

## Guide 2: Windows (PowerShell)

- The repo root is `C:\Users\Nafis\Downloads\Rumor-Zero`. Backend commands run in `backend\` with the
  venv active (`.\.venv\Scripts\Activate.ps1`; the prompt shows `(.venv)`).
- PowerShell 5.1 has no `&&`; use `;` or `if ($?) { ... }`. Playwright installs with
  `npx playwright install chromium` (no `--with-deps`).
- A server started with `runserver` keeps its window busy. Run everything else in a second window.
- Some recorded outputs were captured on Linux (Part 2) and some on Windows; a note says where it
  matters.

### Part 0A: Backend foundation

This part starts the local database and cache, runs the Django backend, and checks that it works. All commands are PowerShell 5.1. The repo root is `C:\Users\Nafis\Downloads\Rumor-Zero`. PowerShell 5.1 has no `&&`, so run commands on separate lines.

| Window | Used for | Stays busy? |
|---|---|---|
| Terminal window 1 (server) | Steps 1 to 2: containers, migrate, create your admin user, `runserver` | Yes, `runserver` keeps it busy. Leave it running. |
| Terminal window 2 (commands) | Steps 3 to 5: health checks, database rules, tests | No |
| Browser | Step 2 | - |

#### Step 1: Start the services and the backend server

**Where:** Terminal window 1 (server), in the repo root first, then in `backend\`.

**What this does:** `docker compose` starts Postgres (the database) and Redis (the cache) in containers. Then you prepare the backend, create your own admin account and start the Django development server.

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero
docker compose up -d
docker compose ps                     # postgres and redis both say (healthy)
```

**You should see:** two rows, `postgres` and `redis`, both with `(healthy)`. If they say `starting`, wait a few seconds and run `docker compose ps` again.

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py migrate              # "No migrations to apply" on a database that is already migrated
python manage.py createsuperuser      # prompts for Email, Username, Password
python manage.py runserver            # leave this window running
```

**You should see:** after the `Activate.ps1` line the prompt starts with `(.venv)`. `migrate` ends with "No migrations to apply" if the database is already migrated (a fresh database lists many `Applying ...` lines instead). `createsuperuser` asks you for an email, a username and a password (the password is not shown while you type). `runserver` prints that it is running at `http://127.0.0.1:8000/` and then does not return to a prompt. That is normal: the window is now busy serving the backend.

- The username can't be a reserved word (`admin`, `root`, `staff` and others are blocked). Use
  something like `nafis_admin`.
- Django Admin logs in with the **email**, not the username.

#### Step 2: Look at the backend in the browser

**Where:** Browser, while `runserver` is running in window 1.

**What this does:** Opens the health page and Django Admin to confirm the server answers and that your admin account works.

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

#### Step 3: Check the deep health endpoint

**Where:** Terminal window 2 (commands), a new PowerShell window. Window 1 must still be running `runserver`.

**What this does:** The deep health check needs a secret request header, so it can't be done in the browser. The first request has no header and must be refused. The second sends the secret (read from your own `backend\.env` without printing it) and must succeed, which proves Postgres and Redis both answer.

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero\backend
curl.exe -i http://localhost:8000/api/health/deep/
$secret = (Select-String -Path .\.env -Pattern '^INTERNAL_CRON_SECRET=(.*)$').Matches.Groups[1].Value    # sets $secret for the next line; nothing is printed
curl.exe -i -H "X-RZ-Cron-Secret: $secret" http://localhost:8000/api/health/deep/
```

**You should see:**

- First request: **403** with `permission_denied` (no secret, so refused, as intended).
- Second request: **200** with `{"status":"ok","database":"ok","cache":"ok"}`. This proves Postgres
  and Redis.

**If it differs:** a `Failed to connect` means window 1 is not running `runserver`. An empty `$secret` (second request also 403) means `INTERNAL_CRON_SECRET` is missing from `backend\.env`.

#### Step 4: Check that the database refuses bad data

**Where:** Same terminal as step 3 (window 2), in `backend\` with the venv active (run `.\.venv\Scripts\Activate.ps1` if the prompt has no `(.venv)`).

**What this does:** Reads the platform settings, then tries to write a credibility score of 150 (the allowed range is 0 to 100). The database must refuse it.

```powershell
python manage.py shell -c "from apps.core.services import get_platform_settings as g; s=g(); print(s.report_threshold, s.emergency_min_reputation)"
python manage.py shell -c "from apps.accounts.models import User; u=User.objects.first(); print(u.reputation_score); User.objects.filter(pk=u.pk).update(reputation_score=150)"
```

**You should see:**

- First command prints `5 40`.
- Second prints `50`, then a long traceback ending in
  `IntegrityError ... violates check constraint "accounts_user_reputation_score_range"`. That error
  is the expected result: the database refused a score above 100 and the user keeps 50. The
  traceback shows your email and the start of your password hash, so don't share it.

#### Step 5: Run the automated checks

**Where:** Same terminal as step 3 (window 2), in `backend\` with the venv active. Needs the containers from step 1.

**What this does:** Runs the backend test suite, the code-style checks and the Django consistency checks. The test run takes a little while and prints dots as it goes.

```powershell
python -m pytest                                    # 200 passed
python -m pytest --cov=apps --cov=rumor_zero        # same tests plus coverage (about 93%)
ruff check . ; ruff format --check .                # All checks passed! / files already formatted
python manage.py makemigrations --check --dry-run   # No changes detected
python manage.py check                              # System check identified no issues
```

**You should see:** the result in each comment above. The first two commands end with a summary line; the others print one short sentence.

#### Step 6: Stop and clean up

**Where:** Window 1 for the server, then any terminal in the repo root.

- Stop the server: `Ctrl+C` in its window.
- Stop the containers and keep the data: `docker compose down` (repo root).
- Wipe the local database (destructive): `docker compose down -v` (repo root).

---

### Part 0B: Frontend foundation & design system

Everything here runs in `frontend\`. No backend, Docker container or
secret is needed: these pages make no API calls. (Next loads your `frontend\.env.local`
by itself; you never open or print it.)

| Window | Used for | Stays busy? |
|---|---|---|
| Terminal window 1 (server) | Steps 4 and 7: `npm run dev`, later `npm start` | Yes, leave it running while you use the browser |
| Terminal window 2 (commands) | Steps 1 to 3, the second half of step 7, and step 8 | No |
| Browser | Steps 5 to 7 | - |

Steps 1 to 3 need only one terminal. Open a second one when step 4 starts the server.

#### Step 1: Install and check the tools

**Where:** Terminal (the one you will use for the checks).

**What this does:** Confirms Node is the right version and installs the frontend packages.

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero\frontend
node -v                               # v24.x.x (the project pins Node 24)
npm install                           # "up to date, audited 449 packages" and "found 0 vulnerabilities"
```

**You should see:** a Node version starting with `v24`, then npm's summary lines as in the comments. `npm install` can be quiet for a few seconds.

- npm also prints `npm warn allow-scripts ... unrs-resolver`. It is harmless.
- On a fresh clone the first install can stop with `ERR_SSL_CIPHER_OPERATION_FAILED` on this
  network. Run `npm cache verify`, then `npm install` again. Don't turn TLS checks off.

#### Step 2: Run the automated checks

**Where:** Same terminal as step 1, same folder. Nothing else needs to be running.

**What this does:** Runs the linter, the design-token guard, the type checker, the formatter check and the unit tests.

```powershell
npm run lint                          # only the npm header, no findings
npm run lint:tokens                   # lint:tokens OK (no default palette, raw hex, stray radius, shadow or type size)
npm run typecheck                     # only the npm header, no type errors
npm run format:check                  # All matched files use Prettier code style!
npm test                              # Test Files  32 passed (32) / Tests  251 passed (251)
```

**You should see:** the result in each comment. "Only the npm header" means a couple of lines starting with `>` and nothing after them: no news is good news.

#### Step 3: Try to break the design-token guard

**Where:** Same terminal as step 1, in `frontend\`.

**What this does:** `lint:tokens` rejects anything outside the Stitch design system. You add a file that breaks two rules, watch the guard complain, then delete the file and watch it pass again.

```powershell
Set-Content src\tmp-token-check.tsx 'export const x = "bg-blue-500 rounded-md";'   # creates the bad file
npm run lint:tokens                   # must fail
Remove-Item src\tmp-token-check.tsx   # removes the bad file
npm run lint:tokens                   # must pass again
```

**You should see:**

- First run exits with code 1 and prints
  `src/tmp-token-check.tsx:1  Tailwind default palette colour: bg-blue-500`,
  `src/tmp-token-check.tsx:1  radius other than rounded-lg / rounded-full: rounded-md` and
  `lint:tokens found 2 problem(s).`
- Second run (file removed) is back to `lint:tokens OK ...`. Nothing is left behind.

#### Step 4: Start the dev server

**Where:** Terminal window 1 (server), in `frontend\`.

**What this does:** Starts the Next.js development server so you can open the pages in the browser.

```powershell
npm run dev                           # leave this window running
```

**You should see:**

- `▲ Next.js 16.3.8 (Turbopack)`, `- Local:         http://localhost:3000`,
  `- Environments: .env.local` and `✓ Ready in` a few hundred milliseconds. The window then stays busy. That is normal.
- It must not create `frontend\AGENTS.md` or `frontend\CLAUDE.md` (see step 8).

#### Step 5: Look at the pages and try the controls

**Where:** Browser, while `npm run dev` is running in window 1.

**What this does:** Checks the home page, the UI gallery and the 404 page, then tries each control in the gallery.

| URL | Expect |
|---|---|
| http://localhost:3000/ | Heading "Frontend foundation" and one sentence ("The design system is in place. ..."). Tab title "Rumor Zero". |
| http://localhost:3000/dev/ui | The gallery. Tab title and heading "UI gallery", a row of section links, and 13 sections from Icon down to "Stitch b2 and d1: modals". |
| http://localhost:3000/nope | Next's standard 404 page |

On `/dev/ui` (a 1280 px wide window shows it as designed), check the look first:

- Page background is a pale lavender; headings are a serif (Newsreader), body text is Inter, small
  caps labels are monospace.
- Icons are glyphs. If you read words like `check_circle` instead, the icon font didn't load.

Then try each control:

| Do this | Expect |
|---|---|
| Tabs: click **Recent**, or focus a tab and press the right arrow | Recent is selected, the blue underline moves under it, the text below reads "Panel for recent" |
| Post type control: click **Fact** | Nothing is chosen at first; after the click Fact is the raised white pill and Opinion is not |
| Password field (in the "TextField, PasswordField, Textarea" section): click the eye icon | The dots turn into the text `hunter2hunter2`; the button now says "Hide password" |
| "Try a password" box: type `abc`, then `abcdefg1`, then `abcdefg1X`, then `correct horse battery 9` | The label under the bar reads **Weak** (red), **Fair** (amber), **Good** (teal), **Strong** (teal), filling 1, 2, 3 and 4 segments |
| Toggle row: click the first (off) toggle | It switches on. The third toggle is violet (emergency), the last is greyed out and does nothing |
| Radio list ("Why are you reporting this post?"): click **Spam or fake accounts** | Its card gets the blue border and the first card loses it |
| Avatar section, "a photo that fails to load" | Two dark circles with the initials **GH** and **RU**. No broken-image icon. |
| Red alert "Could not log in": click the **×** | The alert disappears |
| **Show a live toast** | A dark toast "Saved just now" appears bottom-centre and is gone after about 4 seconds |

The post cards under "Stitch b1: PostCard" (eight of them, in this order):

- Verified 94%: teal stripe, `VERIFIED 94%`.
- FALSE 88%: red stripe, `FALSE 88%`. The claim is not struck through.
- Emergency: the only card with a **violet** stripe, with `CHECKING FACTS…` and `EMERGENCY` chips.
- Under review: amber stripe, `UNDER REVIEW` and `APPEAL PENDING`.
- Opinion: grey stripe, italic serif text, an `OPINION` chip and no status badge.
- Moderator-verified: `VERIFIED · REVIEWED`, no percentage.
- Moderator-FALSE, emergency over: red again, `FALSE · REVIEWED`, no `EMERGENCY` chip.
- Removed: a small box "Removed by a moderator", with no text, stripe or chips.

The word "debunked" appears nowhere. For a side-by-side look, open
`design\stitch\stitch_website_sitemap_grid_builder\b1_home_feed\code.html`
next to the gallery.
Stitch also shows an affiliation line, an evidence drawer and an action bar (later parts) and
strikes FALSE claims through (deliberately not copied).

#### Step 6: Try the two modals

**Where:** Browser, still on `/dev/ui`. Scroll to "Stitch b2 and d1: modals".

**What this does:** Opens the post composer and the report dialog and checks their behaviour (focus, Esc, counters).

| Do this | Expect |
|---|---|
| Click **Open the composer (b2)** | A 620 px dialog, centred, over a dimmed and slightly blurred page. Header "New post". The cursor is already in the large serif text box, with `0 / 500 characters` under it. Fact is selected, the violet Emergency toggle is on with a violet "Misuse has consequences." callout, and there is a Source field. Footer: "7 of 10 fact posts left today", Cancel, **Post fact, will be checked**. |
| Type `Solar capacity grew 30% last year.` | The counter reads `34 / 500 characters` |
| Click **Opinion** | The button becomes **Post opinion** and the Emergency toggle and Source field disappear |
| Press Tab over and over | Focus cycles through the dialog's own controls and never reaches the page behind it. After the last button it leaves the page for the browser's own controls, then comes back to Close. |
| Press Esc | The dialog closes and focus is back on **Open the composer (b2)** |
| Click **Open the report modal (d1)** | Header "Report this post" with a small "REPORT" line above it, a quoted claim with a dark left edge, five radio cards (the first selected, blue border), a blue "What happens next" note, and a white footer with Cancel and **Submit report**. Focus starts on the × button. |
| Press Esc | The dialog closes and focus returns to **Open the report modal (d1)** |

#### Step 7: Check that the production build hides the gallery

**Where:** Terminal window 1 (server). First stop the dev server with `Ctrl+C`, then run the commands in `frontend\`. The checks afterwards go in window 2.

**What this does:** Builds the production version and starts it. In production the `/dev/ui` gallery must answer 404 while the home page still works.

```powershell
npm run build                         # takes a little while; prints a route list at the end
npm start                             # leave this window running
```

**You should see:**

- Build: `✓ Compiled successfully in` a few seconds, `Generating static pages ... (4/4)`, and a
  route list with `/`, `/_not-found` and `/dev/ui`, all marked `○ (Static)`. The route is listed
  but answers 404 at runtime, as the next commands show.
- Start: `▲ Next.js 16.3.8`, `- Local:         http://localhost:3000`, `✓ Ready in` about 100 ms. The window stays busy.

Now in **Terminal window 2 (commands)**, a second PowerShell window:

```powershell
curl.exe -s -o NUL -w "/        %{http_code}`n" http://localhost:3000/
curl.exe -s -o NUL -w "/dev/ui  %{http_code}`n" http://localhost:3000/dev/ui
```

**You should see:**

- `/        200` and `/dev/ui  404`.
- Browser: http://localhost:3000/dev/ui shows "This page could not be found", while
  http://localhost:3000/ still shows "Frontend foundation".

#### Step 8: Repository checks

**Where:** Terminal window 2 (commands).

**What this does:** Confirms the example env file is tracked by git and that `create-next-app` did not leave agent instruction files in `frontend\`.

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero
git check-ignore frontend\.env.example             # prints nothing: the example env file is tracked
Test-Path frontend\AGENTS.md, frontend\CLAUDE.md   # False, then False
```

**You should see:** nothing from `git check-ignore`, then `False` and `False`.

#### Step 9: Stop and clean up

**Where:** Terminal window 1 for the server.

- Stop the server: `Ctrl+C` in its window.
- Nothing else is running for this part: no containers, no backend.
- Optional: `Remove-Item -Recurse -Force frontend\.next`
  deletes the build output. It is recreated by the next `npm run dev` or `npm run build`.

---

### Part 0D: Brand assets & Logo component

Everything here runs in `frontend\` unless a step says otherwise. No backend, Docker container or
secret is needed. (Next loads your `frontend\.env.local` by itself; you never open or print it.)
The master logo is `design\logo.svg`. It is read-only: nothing below changes it.

| Window | Used for | Stays busy? |
|---|---|---|
| Terminal window 1 (server) | Step 8: `npm run dev` | Yes, leave it running through step 9 |
| Terminal window 2 (commands) | Steps 1 to 7, the fetch part of step 8, steps 10 to 11 | No |
| Browser | Step 9 | - |

Steps 1 to 7 need just one terminal, in `frontend\`.

#### Step 1: Check the tools

**Where:** Terminal window 2 (commands).

**What this does:** Installs the frontend packages and confirms `sharp` (the image library that draws the PNGs) is present.

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero\frontend
npm install                           # "up to date, audited 449 packages" and "found 0 vulnerabilities"
npm ls sharp --depth=0                # `-- sharp@0.35.5
```

**You should see:** the summary lines in the comments.

- npm also prints `npm warn allow-scripts ... unrs-resolver`. It is harmless.
- `sharp` is the image library that draws the PNGs. Only the brand script uses it.

#### Step 2: Build every logo asset

**Where:** Same terminal as step 1, in `frontend\`.

**What this does:** Reads the master logo and generates all icons, social images and the admin logo from it. It can pause for a moment while images are drawn.

```powershell
npm run brand:build
```

**You should see:**

- `brand:build read design\logo.svg and wrote 16 files:` and a list: `logo.svg`, `mark.svg`,
  `icon-192.png`, `icon-512.png`, `icon-maskable-512.png`, `email-logo.png` and
  `google-oauth-logo.png` under `frontend/public/brand/`; `icon.svg`, `favicon.ico`, `apple-icon.png`,
  `opengraph-image.png`, `twitter-image.png` and the two `.alt.txt` files under `frontend/src/app/`;
  `frontend/src/lib/brand-assets.json`; and `backend/apps/core/static/core/brand/logo-admin.png`.
- Then the contrast table, which must read exactly like the one in `docs\ARCHITECTURE.md` section 14:

```text
Contrast on                       grey letters  cyan "0"
surface-container-lowest #ffffff  3.45 : 1      2.42 : 1
surface #faf8ff                   3.28 : 1      2.30 : 1
inverse-surface #283044           3.81 : 1      5.43 : 1
on-surface #131b2e                4.97 : 1      7.09 : 1
```

- The last line is `The contrast table matches ARCHITECTURE 14.` If you ever change the logo's colours and see
  `DIFFERS from ARCHITECTURE 14` instead, update that section.

#### Step 3: Check that nothing under `design\` changes, and a second run changes nothing

**Where:** Same terminal as step 1, in `frontend\`.

**What this does:** Takes a checksum of every generated file, builds again, and compares. Identical checksums mean the build is repeatable. It also confirms git sees no change under `design\`. The variables `$paths`, `$h1` and `$h2` are set inside this block, so run the whole block in one go.

```powershell
$paths = @('public\brand\*', 'src\app\favicon.ico', 'src\app\icon.svg', 'src\app\apple-icon.png', 'src\app\opengraph-image.png', 'src\app\twitter-image.png', 'src\lib\brand-assets.json', '..\design\logo.svg', '..\backend\apps\core\static\core\brand\logo-admin.png')
$h1 = Get-FileHash $paths | Select-Object Path, Hash
$h1.Count                             # 15
npm run brand:build | Out-Null        # runs the build again, output hidden
$h2 = Get-FileHash $paths | Select-Object Path, Hash
@(Compare-Object $h1 $h2 -Property Path, Hash).Count    # 0
cd ..
git status --short design             # prints nothing
cd frontend
```

**You should see:**

- `15` files hashed, and `0` differences: building again gives the same bytes, including
  `design\logo.svg`.
- `git status --short design` prints nothing: the master was only read.

#### Step 4: Check that the build refuses an unsafe logo

**Where:** Same terminal as step 1, in `frontend\`.

**What this does:** The script takes `--master <file>` so you can try another SVG. Each bad file below is a copy of the
real logo with one thing added, kept in your temp folder. The build must refuse all three. The variable `$bad` is set in the first block and reused in the next two, so use the same terminal throughout.

```powershell
$bad = Join-Path $env:TEMP "rz-bad-logo.svg"
(Get-Content ..\design\logo.svg -Raw) -replace '<defs>', '<script>alert(1)</script><text>x</text><defs>' | Set-Content $bad
npm run brand:build -- --master $bad
$LASTEXITCODE
```

**You should see:** `brand:build failed: rz-bad-logo.svg failed the safety check, so nothing was built:` with
`- <script> element (line 3)` and `- <text> element (line 3)`. The exit code (`$LASTEXITCODE`) is `1`.

```powershell
(Get-Content ..\design\logo.svg -Raw) -replace '<defs>', '<use href="https://evil.example/x.svg#a"/><defs>' | Set-Content $bad
npm run brand:build -- --master $bad
```

**You should see:** it fails with `- external href="https://evil.example/x.svg#a" on <use> (line 3)`.

```powershell
(Get-Content ..\design\logo.svg -Raw) -replace 'viewBox="0 0 1000 1000"', '' | Set-Content $bad
npm run brand:build -- --master $bad
Remove-Item $bad                      # deletes the temporary bad file
```

**You should see:** it fails with `- the <svg> root has no viewBox`.

- In all three, no asset is written and `design\logo.svg` is untouched. Running plain
  `npm run brand:build` again afterwards still works.

**If it differs:** if `$bad` is empty (errors about an empty path), you opened a new terminal after the first block. Run `$bad = Join-Path $env:TEMP "rz-bad-logo.svg"` again.

#### Step 5: Run the automated checks

**Where:** Same terminal as step 1, in `frontend\`. Nothing else needs to be running.

**What this does:** Runs lint, the token guard, type check, format check and the unit tests.

```powershell
npm run lint                          # only the npm header, no findings
npm run lint:tokens                   # lint:tokens OK (no default palette, raw hex, stray radius, shadow or type size)
npm run typecheck                     # only the npm header, no type errors
npm run format:check                  # All matched files use Prettier code style!
npm test                              # Test Files  40 passed (40) / Tests  329 passed (329)
```

**You should see:** the result in each comment.

- The new tests are the SVG safety check, the ICO writer, the contrast table (compared with
  `docs\ARCHITECTURE.md`), the PNG sizes, a full build into a scratch folder, `Logo`, `manifest.ts` and
  the brand guard.

#### Step 6: Try to break the brand guard

**Where:** Same terminal as step 1, in `frontend\`.

**What this does:** Only `Logo.tsx`, `brand-assets.json` and `manifest.ts` may know where the logo files are, and nobody
may re-create the old text wordmark. You add two files that break the rules, run the guard test (it must fail), delete the files and run it again (it must pass).

```powershell
Set-Content src\tmp-wordmark.tsx 'export const X = () => <span className="font-headline-sm">Rumor Zero</span>;'
Set-Content src\tmp-logo-ref.ts 'export const src = "/brand/logo.svg";'
npx vitest run src/lib/brand-guard.test.ts     # must show failures
Remove-Item src\tmp-wordmark.tsx, src\tmp-logo-ref.ts    # removes both bad files
npx vitest run src/lib/brand-guard.test.ts     # must pass
```

**You should see:**

- First run: `Tests  3 failed | 3 passed (6)`. The failures name `tmp-logo-ref.ts` (twice: it refers to
  `/brand/` and names a logo image) and `tmp-wordmark.tsx` (it re-creates the text wordmark).
- Second run (files removed): `Tests  6 passed (6)`. Nothing is left behind.

#### Step 7: Check that the production build carries the icon tags

**Where:** Same terminal as step 1, in `frontend\`.

**What this does:** Builds the site and searches the generated home page for the icon, manifest and social-share tags. `$html` is set in this block and used by the two lines after it.

```powershell
npm run build                         # takes a little while
$html = Get-Content .next\server\app\index.html -Raw
[regex]::Matches($html, '<link rel="(?:icon|apple-touch-icon|manifest)"[^>]*>') | ForEach-Object { $_.Value }
[regex]::Matches($html, '<meta (?:property|name)="(?:og:image|twitter:image|twitter:card|og:site_name)"[^>]*>') | ForEach-Object { $_.Value }
```

**You should see:**

- Build: `✓ Compiled successfully`, `Generating static pages ... (10/10)`, and a route list that now also
  has `/apple-icon.png`, `/icon.svg`, `/manifest.webmanifest`, `/opengraph-image.png` and
  `/twitter-image.png`, all `○ (Static)`.
- The links:

```text
<link rel="manifest" href="/manifest.webmanifest"/>
<link rel="icon" href="/favicon.ico?favicon.<hash>.ico" sizes="48x48" type="image/x-icon"/>
<link rel="icon" href="/icon.svg?icon.<hash>.svg" sizes="any" type="image/svg+xml"/>
<link rel="apple-touch-icon" href="/apple-icon.png?apple-icon.<hash>.png" sizes="180x180" type="image/png"/>
```

- The meta tags: `og:site_name` is `Rumor Zero`, `twitter:card` is `summary_large_image`, and `og:image` and
  `twitter:image` are full URLs built from `NEXT_PUBLIC_SITE_URL` (`http://localhost:3000/opengraph-image.png?...`
  with the value from your `.env.local`).
- `<hash>` differs from run to run.

#### Step 8: Start the dev server and fetch every asset

**Where:** `npm run dev` in Terminal window 1 (server); the `curl.exe` commands in Terminal window 2 (commands).

**What this does:** Starts the dev server, then requests every generated file to confirm each one is served with the right content type.

```powershell
npm run dev                           # leave this window running
```

**You should see:** the Next.js start-up lines, then a busy window. That is normal.

Second window (window 2):

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero\frontend
foreach ($u in '/favicon.ico','/icon.svg','/apple-icon.png','/manifest.webmanifest','/opengraph-image.png','/twitter-image.png','/brand/logo.svg','/brand/mark.svg','/brand/icon-192.png','/brand/icon-512.png','/brand/icon-maskable-512.png','/brand/email-logo.png','/brand/google-oauth-logo.png') {
  curl.exe -s -o NUL -w "$u  %{http_code}  %{content_type}`n" "http://localhost:3000$u"
}
curl.exe -s http://localhost:3000/manifest.webmanifest
curl.exe -s -o NUL -w "/brand/nope.png  %{http_code}`n" http://localhost:3000/brand/nope.png
```

**You should see:**

- All 13 lines say `200`. Content types: `image/x-icon` for the .ico, `image/svg+xml` for the three SVGs,
  `application/manifest+json` for the manifest, and `image/png` for the rest.
- The manifest is one line of JSON: name and short name `Rumor Zero`, `"start_url":"/"`,
  `"display":"standalone"`, `theme_color` and `background_color` both `#283044`, and three icons:
  `192x192` (`any`), `512x512` (`any`) and `512x512` (`maskable`).
- The last line says `404`: only generated files exist.

#### Step 9: Look at the logo and icons in the browser

**Where:** Browser, while `npm run dev` is running in window 1.

**What this does:** Checks by eye that the logo renders correctly at each size and on each background, and that every generated image looks right.

| URL | Expect |
|---|---|
| http://localhost:3000/ | Heading "Frontend foundation". The tab shows a dark rounded square with a cyan "0" as its icon (a hard refresh, Ctrl+F5, helps if the old icon is cached). |
| http://localhost:3000/dev/ui#logo | The "Logo" section: three panels, "ON SURFACE" (pale lavender), "ON SURFACE-CONTAINER-LOWEST" (white) and "ON INVERSE-SURFACE" (dark navy). |

In each of the three panels:

- Row one: the wordmark "Rum0r" at **sm, md and lg**, three clearly different sizes (24, 36 and 48 px tall). The letters
  are grey, the "0" and the underline are cyan.
- Row two: the cyan "0" mark alone at sm, md and lg.
- Last line: a small "0" followed by "Rumor Zero (decorative mark: the name is written next to it)".
- On the dark panel the grey letters look dimmer but readable; the cyan stands out.
- The labels under the logos are plain text, not part of the images.

Check the sizes and names in the page itself: press F12, open the **Console** and paste

```js
[...document.querySelectorAll('#logo img')].map(i => [i.alt, i.width, i.height].join(' | ')).slice(0, 7)
```

- Expect `Rumor Zero | 79 | 24`, `Rumor Zero | 119 | 36`, `Rumor Zero | 158 | 48`, `Rumor Zero | 24 | 24`,
  `Rumor Zero | 36 | 36`, `Rumor Zero | 48 | 48` and ` | 24 | 24` (the decorative one has an empty alt).

Now open each generated image in the browser and check what you see:

| URL | Expect |
|---|---|
| http://localhost:3000/brand/logo.svg | The full wordmark on a transparent background, tightly cropped |
| http://localhost:3000/brand/mark.svg | The cyan "0" alone on a transparent background |
| http://localhost:3000/brand/icon-512.png | A dark navy rounded square with a large cyan "0" in the middle; the four corners are transparent |
| http://localhost:3000/brand/icon-maskable-512.png | A full-bleed navy square, the "0" smaller and well inside the middle, no rounded corners |
| http://localhost:3000/apple-icon.png | A full-bleed navy square with the "0" (iOS rounds it itself) |
| http://localhost:3000/opengraph-image.png | A wide navy picture with the whole wordmark centred, grey letters, cyan "0" and underline |
| http://localhost:3000/brand/email-logo.png | A small navy banner with the wordmark |
| http://localhost:3000/brand/google-oauth-logo.png | A small navy square with the wordmark across the middle |

Last, the manifest as the browser reads it: F12 → **Application** → **Manifest**. It shows the name
"Rumor Zero", theme and background colour `#283044`, and the three icons, including one marked
"maskable".

#### Step 10: Check the exact sizes of the generated files

**Where:** Terminal window 2 (commands), in `frontend\`. Stop the dev server first (`Ctrl+C` in window 1), or just use this new window.

**What this does:** A small PowerShell script reads each PNG's width and height and the icon sizes inside `favicon.ico`, and prints them with the file sizes.

```powershell
Add-Type -AssemblyName System.Drawing
$pngs = 'src\app\apple-icon.png','public\brand\icon-192.png','public\brand\icon-512.png','public\brand\icon-maskable-512.png','src\app\opengraph-image.png','src\app\twitter-image.png','public\brand\google-oauth-logo.png','public\brand\email-logo.png','..\backend\apps\core\static\core\brand\logo-admin.png'
foreach ($p in $pngs) { $img = [System.Drawing.Image]::FromFile((Resolve-Path $p)); "{0,-62} {1} x {2}  {3} bytes" -f $p, $img.Width, $img.Height, (Get-Item $p).Length; $img.Dispose() }
$b = [System.IO.File]::ReadAllBytes((Resolve-Path src\app\favicon.ico))
"ico: images=$([BitConverter]::ToUInt16($b,4)); sizes=" + (($b[6], $b[22], $b[38]) -join ',')
```

**You should see** (recorded output):

```text
src\app\apple-icon.png               180 x 180  2333 bytes
public\brand\icon-192.png            192 x 192  3904 bytes
public\brand\icon-512.png            512 x 512  12022 bytes
public\brand\icon-maskable-512.png   512 x 512  6262 bytes
src\app\opengraph-image.png          1200 x 630  12839 bytes
src\app\twitter-image.png            1200 x 630  12839 bytes
public\brand\google-oauth-logo.png   120 x 120  1605 bytes
public\brand\email-logo.png          320 x 96  3541 bytes
..\backend\apps\core\static\core\brand\logo-admin.png   158 x 64  1879 bytes
ico: images=3; sizes=16,32,48
```

- The sizes are exact; the byte counts can differ a little on another machine.
- The Google logo is far under 1 MB. The apple icon is also opaque (its PNG has no alpha channel);
  the automated tests check that.

#### Step 11: Repository checks

**Where:** Terminal window 2 (commands).

**What this does:** Confirms git does not ignore the generated files, marks the binary ones correctly, and that `design\` and `frontend\` have no unexpected changes or files.

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero
git check-ignore frontend\src\app\favicon.ico frontend\public\brand\logo.svg backend\apps\core\static\core\brand\logo-admin.png   # prints nothing: none of them is ignored
git check-attr binary -- frontend/src/app/favicon.ico frontend/src/app/apple-icon.png     # both: binary: set
git status --short design             # prints nothing: design\ is untouched
Test-Path frontend\AGENTS.md, frontend\CLAUDE.md   # False, then False
```

**You should see:** nothing from the first `git` command, two lines saying `binary: set`, nothing from `git status`, then `False` and `False`.

#### Step 12: Stop and clean up

**Where:** Terminal window 1 for the server.

- Stop the server: `Ctrl+C` in its window.
- Nothing else is running for this part: no containers, no backend.
- The generated files are meant to be committed; do not delete them. To change the logo later:
  replace `design\logo.svg` yourself, check that `markSelector` in
  `frontend\scripts\brand\brand.config.json` still picks the "0" (the build fails if it does not
  match exactly one shape), run `npm run brand:build`, and compare the contrast table with
  `docs\ARCHITECTURE.md` section 14.
### Part 0C: App shell, API relay, API client, CI

Needs Part 0A's containers and virtualenv, and your own `backend\.env` and `frontend\.env.local`.
The relay reads `BACKEND_ORIGIN` and `PROXY_SHARED_SECRET` from `frontend\.env.local`. The secret
must be the same as the one in `backend\.env` (ENV_GUIDE §1.2). Nobody can log in yet (Part 1), so
the app pages show the logged-out shell; `/dev/shell` shows the logged-in one with a sample user.

The blocks below use full `C:\...` paths, so each new PowerShell window can start in any folder.

**Windows used in this part** (a "window" is one PowerShell window or tab):

| Window | What it does | Busy? |
|---|---|---|
| Window 1 | Django server (`runserver`), later the stand-in backend (step 5) | Yes: leave it running |
| Window 2 | Frontend dev server (`npm run dev`), or one-off commands when no server is needed | Yes while the dev server runs |
| Window 3 | Extra window for `curl.exe` commands (steps 4 and 5) | No |
| Browser | Steps 6 and 11 | n/a |

A server started with `runserver` or `npm run dev` keeps its window busy until you press `Ctrl+C`.
Open a new window whenever you need to type more commands.

#### Step 1: Install the new tools

**Where:** Any PowerShell window.

**What this does:** Installs the frontend packages and downloads the browser (Chromium) that the
end-to-end tests drive, then prints the tool versions so you know they are present.

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero\frontend
npm install                       # up to date, audited 735 packages ... found 0 vulnerabilities
npx playwright install chromium   # first time: downloads Chromium for the E2E test; later: prints nothing
npx wrangler --version            # 4.145.0
npx playwright --version          # Version 1.63.0
```

**You should see:**

- `npm install`: `up to date, audited 735 packages ... found 0 vulnerabilities`. It can take a
  while the first time.
- `npx playwright install chromium`: a download progress bar the first time (slow, be patient);
  nothing on later runs.
- `4.145.0` from wrangler (Cloudflare's tool) and `Version 1.63.0` from Playwright.

- `npm install` also prints an `allow-scripts` warning: it did not run the install scripts of
  `workerd`, `esbuild` and `unrs-resolver`. That is expected. Their programs come from separate
  platform packages and work without those scripts.
- Don't run `npm run preview`, `deploy` or `upload` on your own machine. They are for CI and
  Cloudflare (which build on Linux), and they would copy your real `.env.local` into the Worker
  bundle.

#### Step 2: Run the automated frontend checks

**Where:** Same window as step 1 (you are in `frontend\`).

**What this does:** Runs the linter, the design-token check, the type checker, the formatter check,
the unit tests and a production build. All of them must pass.

```powershell
npm run lint             # no output after the command line
npm run lint:tokens      # lint:tokens OK (no default palette, raw hex, stray radius, shadow or type size)
npm run typecheck        # no output after the command line
npm run format:check     # All matched files use Prettier code style!
npm test                 # Test Files  51 passed (51) / Tests  412 passed (412)
npm run build            # slow (up to a minute or more); ends with a route list
```

**You should see:** The comment on each line is the expected result. "No output" means success for
`lint` and `typecheck`. The build ends with a route list. These lines matter:

```text
┌ ○ /
├ ƒ /api/[...path]
├ ○ /home
├ ○ /login
├ ○ /signup
└ ƒ /u/[username]
```

- `○` means prerendered at build time; `ƒ` means it runs per request. The relay (`/api/[...path]`)
  must be `ƒ`; the landing and auth pages must be `○`.

#### Step 3: Start Django and the frontend

**Where:** PowerShell window 1 (server), then PowerShell window 2.

**What this does:** Starts the database containers and the Django backend (window 1), then the
Next.js dev server (window 2), so the site is reachable at http://localhost:3000.

Window 1:

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero
docker compose up -d
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py runserver        # leave this window running
```

Window 2:

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero\frontend
npm run dev                       # ✓ Ready in about 0.5 s, then "✓ Running next.config.ts took" 1 to 5 s
```

**You should see:** In window 1 Django prints its "Starting development server at
http://127.0.0.1:8000/" lines. In window 2 `✓ Ready in about 0.5 s`, then
`✓ Running next.config.ts took` 1 to 5 s. Both windows stay busy; that is correct.

- The extra seconds start `workerd`, Cloudflare's local runtime, for the OpenNext dev setup. If
  Windows Firewall asks about it, local access is all it needs.

#### Step 4: Check the relay

**Where:** PowerShell window 3 (a new window).

**What this does:** Sends requests to the frontend on port 3000 and checks that the relay passes
them to Django on port 8000 and handles errors the right way.

```powershell
curl.exe -i http://localhost:3000/api/health/
curl.exe -s -i http://localhost:3000/api/health | Select-String '^HTTP|^location'
curl.exe -s -o NUL -w "%{http_code}`n" "http://localhost:3000/api/a%2Fb/"
curl.exe -s -o NUL -w "%{http_code}`n" http://localhost:3000/api/nope/
curl.exe -s -o NUL -w "%{http_code} %{redirect_url}`n" http://localhost:3000/home/
```

**You should see:** One result per command, in order:

1. `HTTP/1.1 200 OK` and the body `{"status":"ok"}`. That is Django's answer, fetched through the
   relay on port 3000, with no redirect.
2. `HTTP/1.1 301 Moved Permanently` and `location: /api/health/`. That is Django adding the
   missing slash; the relay keeps the target relative, so it stays on port 3000.
3. `400` (an encoded `/` is refused).
4. `404` (Django has no such path).
5. `308 http://localhost:3000/home`. Page URLs drop a trailing slash; API URLs keep it.

Now stop Django (`Ctrl+C` in window 1) and ask again from window 3:

```powershell
curl.exe -s -i http://localhost:3000/api/health/ | Select-String '^HTTP|^retry-after|^cache-control|code'
```

```text
HTTP/1.1 503 Service Unavailable
cache-control: no-store
retry-after: 30
{"detail":"The server is waking up. Try again in a minute.","code":"backend_waking"}
```

It answers at once, because nothing is listening on port 8000. Start `python manage.py runserver`
again in window 1.

#### Step 5: See what the backend receives (stand-in backend)

**Where:** Windows 1, 2 and 3, as marked below.

**What this does:** Django removes the `X-RZ-*` headers before any code can see them, so this check
uses a small stand-in backend. It reports what arrived as true/false and names only. It uses the
made-up value `echo-check-secret`, never your real secret.

First stop `npm run dev` (`Ctrl+C` in window 2): Next runs only one dev server per folder. Then
stop `runserver` in window 1 too; it isn't needed here.

Window 1, the stand-in backend (it keeps the window busy):

```powershell
@'
// Stand-in backend for the Part 0C relay check. It prints header NAMES and true/false only.
const http = require("node:http");
http.createServer((req, res) => {
  const chunks = [];
  req.on("data", (chunk) => chunks.push(chunk));
  req.on("end", () => {
    const path = new URL(req.url, "http://x").pathname;
    if (path === "/api/cookies/") {
      res.setHeader("set-cookie", ["first=1; Path=/; HttpOnly", "second=2; Path=/api/auth/; SameSite=Lax"]);
      return res.end("{}");
    }
    if (path === "/api/etag/") {
      res.setHeader("etag", '"v1"');
      res.setHeader("cache-control", "public, max-age=31536000, immutable");
      if (req.headers["if-none-match"] === '"v1"') { res.statusCode = 304; return res.end(); }
      return res.end("cached body");
    }
    res.setHeader("content-type", "application/json");
    res.end(JSON.stringify({
      method: req.method,
      secretMatches: req.headers["x-rz-proxy-secret"] === "echo-check-secret",
      clientIp: req.headers["x-rz-client-ip"] ?? null,
      forwardedHost: req.headers["x-forwarded-host"] ?? null,
      contentLength: req.headers["content-length"] ?? null,
      chunked: req.headers["transfer-encoding"] === "chunked",
      bodyBytes: Buffer.concat(chunks).length,
    }));
  });
}).listen(8765, "127.0.0.1", () => console.log("stand-in backend on http://127.0.0.1:8765"));
'@ | Set-Content -Encoding utf8 $env:TEMP\rz-echo.cjs
node $env:TEMP\rz-echo.cjs        # stand-in backend on http://127.0.0.1:8765
```

The first command writes the script file (no output); the second runs it and prints
`stand-in backend on http://127.0.0.1:8765`.

Window 2, a dev server pointed at it. The `$env:` values last only for this window;
`.env.local` is not changed:

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero\frontend
$env:BACKEND_ORIGIN = "http://127.0.0.1:8765"; $env:PROXY_SHARED_SECRET = "echo-check-secret"
npx next dev -p 3100
```

Window 3, the checks:

```powershell
curl.exe -s -H "X-RZ-Proxy-Secret: spoofed" -H "X-RZ-Client-IP: 6.6.6.6" -H "X-Forwarded-Host: evil.example" http://localhost:3100/api/echo/
curl.exe -s -H "Content-Type: text/plain" --data "hello relay" http://localhost:3100/api/echo/
curl.exe -s -i http://localhost:3100/api/cookies/ | Select-String '^set-cookie'
curl.exe -s -i http://localhost:3100/api/etag/ | Select-String '^HTTP|^etag|^cache-control'
curl.exe -s -i -H 'If-None-Match: \"v1\"' http://localhost:3100/api/etag/ | Select-String '^HTTP|^etag|^cache-control'
```

**You should see:** One block of output per command, in order (lines 1 to 2 are the first two
commands, then the cookies, then the two etag requests):

```text
{"method":"GET","secretMatches":true,"clientIp":"::1","forwardedHost":null,"contentLength":null,"chunked":false,"bodyBytes":0}
{"method":"POST","secretMatches":true,"clientIp":"::1","forwardedHost":null,"contentLength":"11","chunked":false,"bodyBytes":11}
set-cookie: first=1; Path=/; HttpOnly
set-cookie: second=2; Path=/api/auth/; SameSite=Lax
HTTP/1.1 200 OK
cache-control: public, max-age=31536000, immutable
etag: "v1"
HTTP/1.1 304 Not Modified
cache-control: public, max-age=31536000, immutable
etag: "v1"
```

- **Spoofing:** the faked `X-RZ-Proxy-Secret`, `X-RZ-Client-IP` and `X-Forwarded-Host` never
  arrive. The backend gets the relay's own secret (`secretMatches: true`) and your real address
  (`::1` is this machine).
- **Body:** it arrives with its length (`contentLength: "11"`), never chunked, which Django needs.
- **Cookies and caching:** both cookies and the `304 Not Modified` come back with `etag` and
  `cache-control` unchanged.
- In PowerShell, the quotes inside `If-None-Match` need the `\"` form shown above.

**Clean up:** Stop both servers (`Ctrl+C` in windows 1 and 2), then close window 2 so its
environment values are gone. Delete the script:

```powershell
Remove-Item $env:TEMP\rz-echo.cjs
```

#### Step 6: Look at the layouts in the browser

**Where:** PowerShell windows 1 and 2, then the browser.

**What this does:** Starts the normal servers again and lets you check by eye that every page and
screen size looks right.

Start the normal servers again: `python manage.py runserver` in window 1, and in a **new** window 2
`npm run dev` (in `frontend\`).

| URL | Expect |
|---|---|
| http://localhost:3000/ | Placeholder landing page. Top: the logo, "How it works", "Log in" and a blue "Sign up" button. Footer: the small logo, How verification works · Privacy · Terms, and "© 2026 Rumor Zero". Tab title "Rumor Zero". |
| http://localhost:3000/home | The logged-out app shell. Left rail: the logo, Home (blue) and Search; Log in and Sign up at the bottom. Top bar: "Search posts and people" and a Log in link. Tab title "Home · Rumor Zero". |
| http://localhost:3000/home/ | Redirects to `/home` |
| http://localhost:3000/dev/shell | The logged-in shell with the sample user Ada Lovelace: Home, Search, Notifications, Profile, Bookmarks, a blue "New post" button; Moderation and Settings at the bottom; the user card with "AL" and `@ada` |
| http://localhost:3000/dev/shell?user=none | The same page with the logged-out shell |
| http://localhost:3000/login and /signup | A centred white card with the large logo, "Welcome back" or "Create your account" |
| http://localhost:3000/no-such-page | "Page not found" card with the logo and "Go to the home page" |
| http://localhost:3000/dev/ui | The intro text now links to /dev/shell |

On http://localhost:3000/dev/shell:
- Type in the search box and press Enter: the address becomes `/search?q=…` and the page title is
  Search.
- Click `•••` in the user card: a small menu with Profile and Settings opens above it. `Esc` closes
  it.
- Reload, then press `Tab` once: a blue "Skip to content" link appears at the top left.
- The round "N" button at the bottom left is Next's dev indicator; it doesn't exist in production.

Narrower screens: open DevTools (`F12`), switch on the device toolbar (`Ctrl+Shift+M`) and set the
width. The layout switches at 1280 and 768 px.

| Width | Expect on /dev/shell |
|---|---|
| 1280 | The full 256 px rail with labels |
| 1024 | An icon dock: the cyan "0" mark at the top, icons only (hovering shows each name), the "AL" avatar at the bottom |
| 390 | A top bar with the small logo and the "AL" avatar; a bottom bar with Home · Search · New post · Notifications · Profile. Tapping the avatar opens a sheet from the bottom with Bookmarks, Settings and Moderation; `Esc` or a tap outside closes it. No sideways scrolling. |

Compare with Stitch: open
`C:\Users\Nafis\Downloads\Rumor-Zero\design\stitch\stitch_website_sitemap_grid_builder\b1_home_feed\code.html`
in the browser (it needs internet for its Tailwind script), next to /dev/shell, both at 1280.
- The rail width, item positions, blue Home item, top bar height and search box line up.
- Expected differences: the logo image instead of the "Rumor Zero" text; Bookmarks added; "New
  post" instead of "Submit Claim"; Moderation instead of "Audit Queue"; no "Verification Ledger"
  pill; and sample cards instead of Stitch's feed.

#### Step 7: Run the E2E smoke test

**Where:** A PowerShell window (any free window, for example window 3).

**What this does:** Playwright opens a real Chromium browser and clicks through the main pages
automatically. It needs the containers from step 3. Django and the dev server may be running or
not: Playwright starts what is missing and reuses what is already running. A reused dev server
keeps its own `BACKEND_ORIGIN`.

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero\frontend
npm run test:e2e                  # takes about 10 s once started
```

**You should see:** A list of 8 passing tests and `8 passed`:

```text
Running 8 tests using 6 workers

  ok 1 [chromium] › e2e\smoke.spec.ts:8:5 › the relay forwards /api/health/ to Django (120ms)
  ok 5 [chromium] › e2e\smoke.spec.ts:14:5 › the landing page shows the logo and the footer (1.4s)
  ok 7 [chromium] › e2e\smoke.spec.ts:73:5 › the auth card shows the large logo (1.7s)
  ok 2 [chromium] › e2e\smoke.spec.ts:25:5 › page URLs drop a trailing slash (2.2s)
  ok 3 [chromium] › e2e\smoke.spec.ts:31:5 › the app shell has the full rail at 1280px (2.2s)
  ok 6 [chromium] › e2e\smoke.spec.ts:60:5 › the app shell has a top bar and bottom bar at 390px (2.0s)
  ok 8 [chromium] › e2e\smoke.spec.ts:82:5 › an unknown URL shows the 404 page with the logo (745ms)
  ok 4 [chromium] › e2e\smoke.spec.ts:44:5 › the app shell has the icon dock at 1024px (2.3s)

  8 passed (9.3s)
```

- The order and timings vary (six tests run in parallel). `[WebServer]` lines are Django's request
  log.

#### Step 8: Run the same test the way CI runs it

**Where:** A PowerShell window.

**What this does:** CI tests the production build and starts its own servers. First stop
`npm run dev` and `runserver` (`Ctrl+C`); in this mode Playwright won't reuse them.

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero\frontend
npm run build                     # slow, no need to watch it
$env:CI = "1"
npm run test:e2e         # 8 passed, this time against `next start`
Remove-Item Env:CI
```

**You should see:** `8 passed`. `$env:CI = "1"` only lasts for this window; `Remove-Item Env:CI`
removes it again.

#### Step 9: Check the backend is unchanged and still passes

**Where:** Any PowerShell window; this one needs the virtualenv.

**What this does:** Part 0C touched only the frontend, so the backend tests and lint must still
pass exactly as before.

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero\backend
.\.venv\Scripts\Activate.ps1
python -m pytest                                    # 200 passed
ruff check . ; ruff format --check .                # All checks passed! / 43 files already formatted
python manage.py makemigrations --check --dry-run   # No changes detected
```

**You should see:** `200 passed`, then `All checks passed!` and `43 files already formatted`, then
`No changes detected` (no new database changes are pending).

#### Step 10: Repository checks

**Where:** Any PowerShell window.

**What this does:** Confirms that `design\` was not modified, that no unwanted agent files appeared
in `frontend\`, and that git ignores the test reports but not the config files.

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero
git status --short design                          # prints nothing: design\ is untouched
Test-Path frontend\AGENTS.md, frontend\CLAUDE.md   # False, then False
git check-ignore frontend/playwright-report frontend/test-results   # prints both: test reports are never committed
git check-ignore .github/workflows/ci.yml frontend/wrangler.jsonc frontend/playwright.config.ts   # prints nothing: all three are committed
```

**You should see:** Nothing for the first command; `False` and `False`; the two report paths; then
nothing for the last command.

#### Step 11: CI on GitHub (after you push)

**Where:** Browser.

**What this does:** This is the one check the agent could not run, because only you push.

| URL | Expect |
|---|---|
| Your repository's **Actions** tab on github.com | A "CI" run for your push with three green jobs: "Backend (ruff, migrations, pytest)", "Frontend (lint, types, tests, OpenNext build)" and "E2E (Playwright, Chromium)" |

- The frontend job's last step, "OpenNext build", proves the Cloudflare build works on Linux.
- If the E2E job fails, its run page has a "playwright-report" artifact (kept 7 days) that shows
  why.
- Seen on 2026-10-01: the first run failed at "OpenNext build" (`Cannot find package 'esbuild'`).
  The run on `60cfffc` ("Fix: add missing esbuild dependency") had all three jobs green.
- Optional, only if you install the GitHub CLI (`gh`, not installed on the Windows machine yet):
  `gh run list --workflow ci.yml --limit 1` shows `completed` and `success`.

#### Step 12: Stop and clean up

**Where:** Every PowerShell window you still have open.

**What this does:** Shuts everything down.

- Stop the servers: `Ctrl+C` in each window.
- If `npm run dev` later says "Another next dev server is already running" with a PID, the old
  server is still alive. End it with `taskkill /PID <that PID> /T /F`.
- Stop the containers and keep the data: `docker compose down` (repo root).
- `frontend\playwright-report` and `frontend\test-results` are git-ignored; delete them whenever
  you like.

---

### Part 1: Auth core (sign up, log in, tokens, log out)

Needs Part 0A's containers and virtualenv, Part 0C's frontend, and your own `backend\.env` and
`frontend\.env.local`. Both keep Cloudflare's Turnstile **test** keys (ENV_GUIDE §1.5). Two things
to know first:

- Sign-up calls Cloudflare even with the test keys (the widget in the browser, siteverify from
  Django), so it needs internet.
- Open the site as **http://localhost:3000**. Every `/api/auth/` request must carry exactly the
  `Origin` in `FRONTEND_ORIGIN` (`http://localhost:3000`); `http://127.0.0.1:3000` gets 403
  `csrf_failed`.

**Windows used in this part:**

| Window | What it does | Busy? |
|---|---|---|
| Window 1 | Django server (`runserver`, venv active, in `backend\`) | Yes: leave it running |
| Window 2 | Commands: `curl.exe` checks in steps 3 to 5 (variables like `$h` and `$access` live here; do not close it between steps 3 and 4) | No |
| Window 3 | Frontend dev server (`npm run dev`, in `frontend\`), needed from step 5 | Yes |
| Browser | Steps 6, 7 and 11 | n/a |

A server started with `runserver` or `npm run dev` keeps its window busy until you press `Ctrl+C`.

#### Step 1: Migrate and check the settings

**Where:** PowerShell window 1 (it will become the server window in step 3).

**What this does:** Starts the database, applies the new Part 1 database changes, runs Django's
self-check, and checks your JWT signing key length without showing the key.

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero
docker compose up -d
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py migrate
python manage.py check                # System check identified no issues (0 silenced).
(Select-String -Path .\.env -Pattern '^JWT_SIGNING_KEY=(.*)$').Matches.Groups[1].Value.Trim().Length
python manage.py shell -c "from apps.accounts.models import User; print([(u.is_email_verified, list(u.emailaddress_set.values_list('verified', 'primary'))) for u in User.objects.filter(is_superuser=True)])"
```

**You should see:**

- `migrate`, the first time after Part 1: `Applying account.0001_initial... OK` through
  `Applying account.0009_emailaddress_unique_primary_email... OK`, then
  `Applying accounts.0002_verify_superuser_emails... OK`. Later runs: `No migrations to apply.`
- `check`: `System check identified no issues (0 silenced).`
- The length line prints only a number (`67` here). Under 32, Django refuses to start with
  `JWT_SIGNING_KEY must be at least 32 characters`; make a new key with ENV_GUIDE §1.2. Only the
  length is shown, never the key.
- The last command prints `9 objects imported automatically`, then `[(True, [(True, True)])]`: your
  superuser from 0A now counts as verified and has a verified, primary email address (the backfill
  migration).

#### Step 2: Run the automated backend checks

**Where:** Same window as step 1 (`backend\`, venv active).

**What this does:** Runs the whole backend test suite plus lint and the migration check.

```powershell
python -m pytest                                    # 440 passed
python -m pytest apps/accounts                      # 327 passed (the auth tests)
ruff check . ; ruff format --check .                # All checks passed! / 66 files already formatted
python manage.py makemigrations --check --dry-run   # No changes detected
python -m pytest apps/accounts/tests/test_permissions.py -v   # 4 passed
```

**You should see:** The count in each comment. The full test run takes a while.

- Four of the auth tests run refreshes and logouts in two threads at once. One of them is a control
  run: allauth's stock token strategy loses a tab's token, ours doesn't.
- Verified-only endpoints arrive with posts in Part 4, so the last command checks the permission on
  a test-only view: unverified → 403 `email_unverified`, verified → 201, anonymous → 401.

#### Step 3: Sign up against Django

**Where:** PowerShell window 1 (server), then PowerShell window 2 (commands).

**What this does:** Creates a real account by calling Django's sign-up endpoint with `curl.exe`,
shows the cookies Django sets (the refresh token is hidden), and reads your profile with the access
token.

Window 1: `python manage.py runserver` (in `backend\`, venv active). Leave it running.

Window 2 (no venv needed). **Keep this window open until the end of step 4**: it sets the
variables `$id`, `$h`, `$out`, `$body` and `$access` that step 4 reuses, and the helper files
`rz-signup.json` and `rz-jar.txt` in `$env:TEMP`:

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero\backend
$id = Get-Date -Format "HHmmss"
$h = '-H', 'Origin: http://localhost:3000', '-H', 'X-Requested-With: rumor-zero'
@"
{"email": "part1-$id@example.test", "username": "part1_$id", "password": "correct-horse-battery-42", "turnstile_token": "XXXX.DUMMY.TOKEN.XXXX"}
"@ | Set-Content -Encoding ascii $env:TEMP\rz-signup.json
$out = curl.exe -s -i -c $env:TEMP\rz-jar.txt @h -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-signup.json" http://localhost:8000/api/auth/app/v1/auth/signup
$out | Select-String '^HTTP|^Set-Cookie|^Cache-Control' | ForEach-Object { $_.Line -replace 'rz_refresh=[^;]+', 'rz_refresh=<token>' }
$body = $out[-1] | ConvertFrom-Json
$access = $body.meta.access_token
"user: $($body.data.user.username); meta fields: $(($body.meta.PSObject.Properties.Name) -join ', '); access token: $($access.Length) characters"
curl.exe -s -H "Authorization: Bearer $access" http://localhost:8000/api/v1/me/
```

**You should see:** The first four lines are the HTTP status and headers (from the `Select-String`
line), the fifth is the summary (the line that starts with `"user:`), and the last is your profile
(from the final `curl.exe`):

```text
HTTP/1.1 200 OK
Cache-Control: max-age=0, no-cache, no-store, must-revalidate, private
Set-Cookie:  rz_refresh=<token>; expires=…; HttpOnly; Max-Age=1209600; Path=/api/auth/; SameSite=Lax
Set-Cookie:  rz_session=1; expires=…; Max-Age=1209600; Path=/; SameSite=Lax
user: part1_014515; meta fields: is_authenticated, access_token; access token: 373 characters
{"id":"…","username":"part1_014515","display_name":"","email":"part1-014515@example.test","is_email_verified":false,"role":"user","has_usable_password":true,"google_connected":false,"avatar_url":null}
```

Sanity check that `$access` is set: `$access.Length` should print a number near `373`. If it prints
nothing or `0`, redo this step (usually Django is not running in window 1, or you are offline).

- The number in the name is the time you ran it. PowerShell 5.1 strips the quotes from JSON typed
  on the curl line, so the body goes through a file.
- `meta` has only `is_authenticated` and `access_token`: no `refresh_token` and no
  `session_token`. The refresh token lives only in the HttpOnly cookie (no `Domain`,
  `Path=/api/auth/`). `Secure` is missing because `AUTH_COOKIE_SECURE=False` locally.
- `rz_session=1` is the readable hint that tells the frontend there is a session to restore.
- The `-replace` hides the cookie value. The access token stays in `$access` and is never printed.
- `XXXX.DUMMY.TOKEN.XXXX` is the token Cloudflare's test widget produces. Django checked it with
  siteverify, using the test secret.

Window 1 now shows the verification email:

```text
Subject: [Rumor Zero] Please Confirm Your Email Address
From: Rumor Zero <no-reply@example.com>
To: part1-014515@example.test
...
To confirm this is correct, go to http://localhost:3000/verify-email/<key>
```

- The link points at the frontend (the page itself arrives in Part 2).
- The text still says "Hello from localhost:8000!": allauth's default wording, which Part 2's
  branded templates replace.

Still in window 2, the live username check (it uses `$id` from above):

```powershell
foreach ($u in 'Ada_Lovelace', 'ADMIN', 'ab', "part1_$id") { curl.exe -s "http://localhost:8000/api/v1/auth/username-available/?u=$u"; "" }
```

```text
{"username":"ada_lovelace","available":true,"reason":null,"message":"Available"}
{"username":"admin","available":false,"reason":"reserved","message":"This username is reserved."}
{"username":"ab","available":false,"reason":"invalid","message":"Usernames are 3–30 characters: lowercase letters, numbers and underscores only."}
{"username":"part1_014515","available":false,"reason":"taken","message":"That username is taken."}
```

Four lines, one per name: free, reserved, invalid format, taken (your own new account).

- An older Windows console may show the dash in `3–30` as other characters; that is only the
  console's code page.

#### Step 4: Refresh, rotation, the CSRF guard and log out

**Where:** Same window as step 3 (window 2).

**What this does:** Shows how the refresh cookie rotates, that the old cookie works for 60 seconds,
that requests without the right headers are refused, and what log out does.

This window must still have `$h`, `$access`, `$id` and the cookie jar `$env:TEMP\rz-jar.txt` from
step 3. Sanity check: `$h` prints the two headers and `Test-Path $env:TEMP\rz-jar.txt` prints
`True`. If not, redo step 3.

```powershell
$refresh = 'http://localhost:8000/api/auth/app/v1/tokens/refresh'
function Get-RefreshCookie { ((Get-Content $env:TEMP\rz-jar.txt) -match 'rz_refresh' -split "`t")[-1] }
$first = Get-RefreshCookie
curl.exe -s -b $env:TEMP\rz-jar.txt -c $env:TEMP\rz-jar.txt @h -X POST $refresh | ForEach-Object { $_ -replace '"access_token": "[^"]+"', '"access_token": "<token>"' }
""
"cookie rotated: $($first -ne (Get-RefreshCookie))"
curl.exe -s -o NUL -w "old cookie at once: %{http_code}`n" @h -X POST -b "rz_refresh=$first" $refresh
Start-Sleep -Seconds 61              # nothing prints for 61 seconds: this wait is on purpose
curl.exe -s -w " %{http_code}`n" @h -X POST -b "rz_refresh=$first" $refresh
curl.exe -s -o NUL -w "current cookie: %{http_code}`n" -b $env:TEMP\rz-jar.txt -c $env:TEMP\rz-jar.txt @h -X POST $refresh
```

**You should see:**

```text
{"status": 200, "data": {"access_token": "<token>"}}

cookie rotated: True
old cookie at once: 200
{"status": 400} 400
current cookie: 200
```

- Line 1: the first refresh succeeded. `cookie rotated: True`: the cookie in the jar changed.
- `old cookie at once: 200`: the old cookie still works right away.
- After the 61 s wait, `{"status": 400} 400`: the old cookie is dead. `current cookie: 200`: the new
  one works.
- Every refresh replaces the cookie. The old one keeps working for 60 seconds, so two tabs
  refreshing together, or a reply lost on a bad connection, never log you out. After that minute it
  is dead (400).

Without the `Origin` or the `X-Requested-With` header:

```powershell
curl.exe -s -w " %{http_code}`n" -b $env:TEMP\rz-jar.txt -H "X-Requested-With: rumor-zero" -X POST $refresh
curl.exe -s -w " %{http_code}`n" -b $env:TEMP\rz-jar.txt -H "Origin: http://localhost:3000" -X POST $refresh
curl.exe -s -w " %{http_code}`n" -b $env:TEMP\rz-jar.txt -H "Origin: http://localhost:3000" -X POST http://localhost:8000/api/auth/logout/
```

- All three print
  `{"status": 403, "errors": [{"code": "csrf_failed", "message": "Reload the page and try again."}]} 403`.
- Login and signup are guarded the same way.

Log out:

```powershell
$last = Get-RefreshCookie
curl.exe -s -i -b $env:TEMP\rz-jar.txt -c $env:TEMP\rz-jar.txt @h -X POST http://localhost:8000/api/auth/logout/ | Select-String '^HTTP|^Set-Cookie'
curl.exe -s -w " %{http_code}`n" @h -X POST -b "rz_refresh=$last" $refresh
curl.exe -s -w " %{http_code}`n" @h -X POST $refresh
curl.exe -s -o NUL -w "logout again: %{http_code}`n" @h -X POST http://localhost:8000/api/auth/logout/
curl.exe -s -o NUL -w "access token after logout: %{http_code}`n" -H "Authorization: Bearer $access" http://localhost:8000/api/v1/me/
curl.exe -s -w " %{http_code}`n" @h -X POST http://localhost:8000/api/auth/app/v1/auth/session
```

```text
HTTP/1.1 204 No Content
Set-Cookie:  rz_refresh=""; expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly; Max-Age=0; Path=/api/auth/; SameSite=Lax
Set-Cookie:  rz_session=""; expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=0; Path=/; SameSite=Lax
{"status": 400} 400
{"status": 401} 401
logout again: 204
access token after logout: 200
{"status": 404, "errors": [{"code": "not_found", "message": "Not found."}]} 404
```

- The first three lines come from the logout call itself (204 and both cookies cleared).
- `400`: the last refresh cookie now fails. `401`: with no cookie at all. `logout again: 204`:
  logging out twice is fine.
- `access token after logout: 200`: the access token keeps working until it expires (at most 15
  minutes after step 3; after that the line says 401). That's by design: access tokens are checked
  by signature and expiry only, and the browser forgets its copy at once.
- Only login, signup, refresh and logout exist under `/api/auth/`. allauth's other endpoints, like
  `auth/session` here, answer 404.

#### Step 5: Failed logins are limited per real client IP, through the relay

**Where:** PowerShell window 3 (frontend), then window 2 (commands).

**What this does:** Sends 11 wrong logins through the frontend relay to show that Django limits
them by your real address, and that a different address is not blocked.

Window 3: `npm run dev` (in `frontend\`). It keeps the window busy. Back in window 2 (it uses `$h`
from step 3; sanity check: `$h` prints the two headers):

```powershell
1..11 | ForEach-Object {
  "{""email"": ""nobody$_@example.test"", ""password"": ""wrong-password""}" | Set-Content -Encoding ascii $env:TEMP\rz-login.json
  $r = curl.exe -s @h -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-login.json" http://localhost:3000/api/auth/app/v1/auth/login | ConvertFrom-Json
  "{0,2}  {1}  {2}" -f $_, $r.status, $r.errors[0].code
}
curl.exe -s @h -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-login.json" http://127.0.0.1:8000/api/auth/app/v1/auth/login; ""
```

**You should see:** Eleven numbered lines, then Django's answer to the last request:

```text
 1  400  email_password_mismatch
 2  400  email_password_mismatch
 3  400  email_password_mismatch
 4  400  email_password_mismatch
 5  400  email_password_mismatch
 6  400  email_password_mismatch
 7  400  email_password_mismatch
 8  400  email_password_mismatch
 9  400  email_password_mismatch
10  400  email_password_mismatch
11  400  too_many_login_attempts
{"status": 400, "errors": [{"message": "The email address and/or password you specified are not correct.", "code": "email_password_mismatch", "param": "password"}]}
```

- The first eleven go through the relay on port 3000. Each uses another email, so only the
  per-address limit (10 failures a minute) is hit (line 11); the per-account limit is 5 failures in
  5 minutes.
- The relay passed your real address (`::1` on the Windows PC this guide was written on) to Django
  with the shared secret. The last request goes straight to Django from a different address
  (`127.0.0.1`), so it isn't blocked (it gets the normal "not correct" answer).
- Within that minute, logging in at http://localhost:3000/login, even with a right password, shows
  the red banner "Too many attempts. Try again in a few minutes."

#### Step 6: Browser: sign up, stay logged in, log out

**Where:** Browser. Window 3's `npm run dev` and window 1's `runserver` must be running.

**What this does:** Walks through the real sign-up screens. Wait a minute after step 5 so the
login limit has cleared.

| Do this | Expect |
|---|---|
| Open http://localhost:3000/signup | The a2 card: the logo, "Create your account", Email address, Username, Password with a bar labelled "Password strength", the Cloudflare widget, a blue "Create account", the Terms/Privacy note and "Already have an account? Log in". No Google button yet (Part 3). |
| Look at the widget | It says "Success!" after a second or two, with a red "For testing only…" line: that is the test key. "Create account" is pale (disabled) until then. |
| Type a username, e.g. `Ada_Lovelace` | After a short pause, a teal "Available: @ada_lovelace" and a check mark in the field. `admin` says "This username is reserved."; `ab` shows the format rule at once. |
| Fill a new email, a username and `correct-horse-battery-42`, then click **Create account** | The button spins briefly, then /home: the shell with your @username in the rail and an amber banner "Verify your email to post, comment and report. Check your inbox for the link." The email appears in window 1. |
| F12 → Application → Cookies → http://localhost:3000 | `rz_refresh` (HttpOnly ✓, SameSite Lax, Path `/api/auth/`) and `rz_session` = `1` (Path `/`, not HttpOnly). Local storage and Session storage are empty. |
| F12 → Console: `document.cookie` | `'rz_session=1'`. Scripts can't see the refresh token. |
| Reload (F5) | Still logged in. The account area at the bottom of the rail shows grey placeholders for a moment while the session is restored. |
| Open http://localhost:3000/home in a second tab | Logged in there too |
| First tab: `•••` in the user card | A menu with Profile, Settings and **Log out** |
| Click **Log out** | You land on /login, both cookies are gone (Application → Cookies), and the second tab switches to the logged-out shell by itself. |
| Open http://localhost:3000/settings | It redirects to `/login?next=%2Fsettings`. Log in with the same email and password: you are back on /settings. |
| Phone width (F12 → device toolbar, 390 px): tap the avatar at the top right | The account sheet ends with Log out |

#### Step 7: Browser: the error states

**Where:** Browser, still on http://localhost:3000; one part needs window 1.

**What this does:** Triggers each sign-up and login error on purpose to see the messages.

| Do this | Expect |
|---|---|
| /signup with the email from step 6 and a new username | Under Email: "A user is already registered with this email address." |
| /signup with the username from step 6 | While typing: "That username is taken." |
| /signup with the password `password123` | After Create account: "This password is too common." under Password. The strength bar says Fair: it is only advice; Django decides. |
| Any failed sign-up | The widget runs again ("Verifying…"), and Create account waits for its new token: each token works once. |
| /login with a wrong password | A red banner "That email and password don't match." with an × that closes it |

A failed bot check needs Cloudflare's always-fail **test** secret on the backend. Stop `runserver`
in window 1 (`Ctrl+C`), then in window 1 (in `backend\`, venv active):

```powershell
$env:TURNSTILE_SECRET_KEY = "2x0000000000000000000000000000000AA"; python manage.py runserver
```

- Sign up with a new email and username: under the widget, "The bot check didn't pass. Try it
  again.", and the widget starts over.
- The `$env:` value lasts only for this window, and `backend\.env` is not changed. Stop the
  server (`Ctrl+C`), **close the window**, and start `python manage.py runserver` normally in a new
  one (venv active).

#### Step 8: Run the automated frontend checks

**Where:** A PowerShell window in `frontend\`. Stop `npm run dev` first (`Ctrl+C` in window 3),
then you can reuse window 3.

**What this does:** The same lint, type, format and unit-test checks as Part 0C, now with the auth
tests included, plus a production build.

```powershell
npm run lint             # no output after the command line
npm run lint:tokens      # lint:tokens OK (no default palette, raw hex, stray radius, shadow or type size)
npm run typecheck        # no output after the command line
npm run format:check     # All matched files use Prettier code style!
npm test                 # Test Files  59 passed (59) / Tests  562 passed (562)
npm run build            # slow; ends with the route list below
```

**You should see:** The comment on each line is the expected result. The build's route list still
has these lines:

```text
├ ƒ /api/[...path]
├ ○ /login
├ ○ /signup
```

- The auth pages stay prerendered (`○`); the relay runs per request (`ƒ`).

#### Step 9: The E2E tests, dev mode and CI mode

**Where:** A PowerShell window in `frontend\` (window 3).

**What this does:** Playwright drives a real browser through sign-up, reload and log out.

Stop `runserver` too (`Ctrl+C` in window 1): Playwright then starts its own Django with an
in-memory cache, so step 5's rate limit can't get in the way.

```powershell
npm run test:e2e
```

**You should see:** 11 passed:

```text
Running 11 tests using 6 workers

  ok  6 [chromium] › e2e\smoke.spec.ts:8:5 › the relay forwards /api/health/ to Django (79ms)
  ...
  ok  2 [chromium] › e2e\auth.spec.ts:122:5 › two tabs open at token expiry both stay logged in (6.3s)
  ok  3 [chromium] › e2e\auth.spec.ts:106:5 › two tabs that load at once, then reload together, stay logged in (6.8s)
  ok  5 [chromium] › e2e\auth.spec.ts:43:5 › sign up, stay logged in across a reload, log out (7.8s)

  11 passed (14.5s)
```

- The timings and the worker count vary from machine to machine.
- The eight 0C smoke tests are unchanged. The three new ones sign up with the test widget, check
  the cookie flags and that storage is empty, reload, log out, try the dead cookie (400) and a
  refresh without the header (403), and use `/settings` → `/login?next=` → back.
- "At token expiry" fast-forwards both tabs' clocks by 14½ minutes, so both refresh at the same
  moment.

Then the way CI runs it:

```powershell
npm run build
$env:CI = "1"
npm run test:e2e         # 11 passed, this time against `next start`
Remove-Item Env:CI
```

#### Step 10: Repository checks

**Where:** Any PowerShell window.

**What this does:** Confirms `design\` is untouched, no unwanted agent files appeared, and that
saved test emails are git-ignored.

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero
git status --short design                          # prints nothing: design\ is untouched
Test-Path frontend\AGENTS.md, frontend\CLAUDE.md   # False, then False
git check-ignore backend/tmp/mail/example.eml      # prints the path: emails written by EMAIL_PROVIDER=file are never committed
```

**You should see:** Nothing; `False` and `False`; then `backend/tmp/mail/example.eml`.

#### Step 11: CI on GitHub (after you push)

**Where:** Browser.

**What this does:** Checks that GitHub's automatic build passes after you push.

| URL | Expect |
|---|---|
| Your repository's **Actions** tab on github.com | A "CI" run for your push with three green jobs |

- New in this part: the E2E job signs up with the Turnstile test key, so the GitHub runner must reach
  `challenges.cloudflare.com` (the browser and Django both call it). If the sign-up tests fail at
  the widget, the run's "playwright-report" artifact shows the page.
- The agent couldn't run CI: only you push.

#### Step 12: Stop and clean up

**Where:** Every PowerShell window you still have open.

**What this does:** Shuts everything down and removes helper files.

- Stop the servers: `Ctrl+C` in each window. If `npm run dev` later says "Another next dev server is
  already running" with a PID, end it with `taskkill /PID <that PID> /T /F`.
- Delete the helper files:
  `Remove-Item $env:TEMP\rz-signup.json, $env:TEMP\rz-jar.txt, $env:TEMP\rz-login.json`.
- The test accounts stay in your local database: `part1_…` from step 3, the E2E's `e2e_…`,
  `tabs_…` and `expiry_…`, and the agent's own checks (`manual_check`, `visual_…`, `tf_…`,
  `phone_…`). Delete them in Django Admin → Users if you like.
  `docker compose down -v` (repo root) wipes the whole local database, which is destructive.
- Stop the containers and keep the data: `docker compose down` (repo root).
### Part 2: Email verification & password reset

Needs Part 0A's containers and virtualenv, Part 0C's frontend, and your own `backend\.env` and
`frontend\.env.local`. `EMAIL_PROVIDER=console` (the default) prints every email in the `runserver`
terminal. Part 2 adds no migration, no dependency and no env variable.

**Which terminal window for what.** Open the windows once and keep using the same ones:

| Window | What runs in it | Used in steps |
|---|---|---|
| Window 1 (server) | `python manage.py runserver` in `backend\`, venv active. Leave it running. Every email the app "sends" is printed here. | 3 to 9 (step 9 restarts it) |
| Window 2 (commands) | All the `curl.exe` commands. **Use the same window for steps 3 to 7**: the variables you set in step 3 (`$id`, `$h`, `$access`, `$resend`) and later (`$raw`, `$key`, `$verify`, `$rp`, `$login`, `$refresh`, `$rk`, `$reset`) only live in that one PowerShell window. If you close it, or open a new one, redo step 3. | 1 to 7, 9, 12 |
| Window 3 (frontend) | `npm run dev` in `frontend\`. Leave it running. | 8 (stopped before step 10) |

Things to know first:

- Sign-up still calls Cloudflare (Turnstile test keys), so it needs internet.
- Open the site as **http://localhost:3000**, as in Part 1.
- The outputs below were recorded on Linux on 2026-10-07. Numbers in names and times differ per run.
  On Windows the shape is the same.
- A link in an email carries a key: the verification key has two `:` that arrive as `%3A`, and the
  commands below turn them back (`[uri]::UnescapeDataString`). A browser does this for you.
- The limits count per address and per IP, and your local Redis remembers them for up to a day.
  Every command here uses a new address, so repeated runs are fine; if you test the per-IP limit of
  50 reset requests a day by hand, wait a day or restart Redis (`docker compose restart redis`).
- Use `curl.exe` (with `.exe`), never plain `curl`: in PowerShell 5.1 plain `curl` is a different
  command. The commands already say `curl.exe`.

#### Step 1: Check that nothing needs migrating and the email templates are in place

**Where:** Terminal window 2 (commands), PowerShell.

**What this does:** Starts the database containers, activates the Python environment and confirms
Django has nothing to migrate (Part 2 adds no tables) and that the new email templates exist.

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero
docker compose up -d
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py migrate                          # No migrations to apply.
python manage.py check                            # System check identified no issues (0 silenced).
python manage.py makemigrations --check --dry-run # No changes detected
dir templates\account\email
```

**You should see:** the three comments above are the expected messages of the three `python` lines
(nothing to apply, no problems, no model changes). `dir` prints a table (Mode, LastWriteTime, Length,
Name) with these names:

```text
base_message.html
base_message.txt
email_confirmation_message.html
email_confirmation_message.txt
email_confirmation_signup_message.html
email_confirmation_signup_message.txt
email_confirmation_signup_subject.txt
email_confirmation_subject.txt
password_reset_key_message.html
password_reset_key_message.txt
password_reset_key_subject.txt
```

- The templates live in `backend\templates\`, not inside the app: `allauth` comes before
  `apps.accounts` in `INSTALLED_APPS`, so its own templates would win.

#### Step 2: Run the automated backend checks

**Where:** Same terminal as step 1 (window 2, in `backend\`, venv active).

**What this does:** Runs the whole backend test suite, then only the new Part 2 test files, then the
linter and formatter check.

```powershell
python -m pytest                                    # 577 passed
python -m pytest apps/accounts/tests/test_email_verification.py apps/accounts/tests/test_resend_verification.py apps/accounts/tests/test_password_reset.py apps/accounts/tests/test_emails.py apps/accounts/tests/test_startup.py -q   # 101 passed
ruff check . ; ruff format --check .                # All checks passed! / 73 files already formatted
```

**You should see:** the full run takes a while and ends with `577 passed`; the second command ends
with `101 passed`; the last prints `All checks passed!` and `73 files already formatted`. (Counts may
grow later; what matters is that nothing fails.)

- The new files cover the verification link (including the `%3A` key and the exact 24-hour expiry),
  the resend cooldown and daily cap, the reset flow (identical answers and bytes for existing,
  unknown and inactive addresses, the limits, expiry, other browsers' refresh tokens), the emails
  themselves (subject, `From`, every link and the logo on the frontend origin, the Brevo payload) and
  the startup preload of allauth's deferred libraries.
- `test_middleware.py` and the settings tests changed too: the verify and password endpoints are now
  on the allow-list, and the new limits are pinned.

#### Step 3: Sign up a test account, and try the resend limits

**Where:** First window 1 (start the server), then window 2 (the commands). **Keep using window 2
for steps 4 to 7.**

**What this does:** Window 1 runs the Django server. In window 2 you create a brand-new account
through the API (which makes the server print the sign-up email in window 1), then check the account
is not verified yet.

Window 1: `python manage.py runserver` (in `backend\`, venv active). Leave it running; it prints
nothing more until a request or an email arrives.

Window 2 (no venv needed):

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero\backend
$id = Get-Date -Format "HHmmss"                                          # a unique suffix so the address is new each run
$h = '-H', 'Origin: http://localhost:3000', '-H', 'X-Requested-With: rumor-zero'   # headers every API call needs
@"
{"email": "part2-$id@example.test", "username": "part2_$id", "password": "correct-horse-battery-42", "turnstile_token": "XXXX.DUMMY.TOKEN.XXXX"}
"@ | Set-Content -Encoding ascii $env:TEMP\rz-signup.json
$access = (curl.exe -s @h -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-signup.json" http://localhost:8000/api/auth/app/v1/auth/signup | ConvertFrom-Json).meta.access_token   # $access = your login token
curl.exe -s -H "Authorization: Bearer $access" http://localhost:8000/api/v1/me/ | ConvertFrom-Json | Select-Object username, is_email_verified | ConvertTo-Json -Compress
```

Sanity check (this step sets `$id`, `$h` and `$access`; `$access` must not be empty):

```powershell
$access.Substring(0,10)               # prints the first 10 characters of the token, not an error
```

**You should see** in window 2 (the number in the name is your `$id`, so it differs):

```text
{"username":"part2_010027","is_email_verified":false}
```

That means the account exists and its email is not verified yet.

**If it differs:** if `$access` is empty (the sanity check errors), the sign-up failed
(`runserver` is probably not running). Fix that and run this step again from
`$id = Get-Date -Format "HHmmss"`.

Window 1 now shows the sign-up email:

```text
Subject: [Rumor Zero] Welcome to Rumor Zero: verify your email
From: Rumor Zero <no-reply@example.com>
To: part2-010027@example.test
...
Content-Type: text/plain; charset="utf-8"

Welcome to Rumor Zero

You can already read everything. Confirm your email address to post, comment and report.

Verify your email:
http://localhost:3000/verify-email/NzU%3A1xEAOb%3AbiPbvPBWC_1KxA5hYCK9XQPDSoulXssAgTKbBUd_AKE

This link expires 24 hours after it was sent. If you didn't create this account, you can ignore this email.

Rumor Zero
...
Content-Type: text/html; charset="utf-8"

<!DOCTYPE html>
...
<img src="http://localhost:3000/brand/email-logo.png" alt="Rumor Zero" width="160" ...>
```

- Two parts: the plain text (no image), then the HTML with the logo. No "Hello from localhost:8000!"
  any more. Every link, and the logo, points at `http://localhost:3000`; `From` is
  `DEFAULT_FROM_EMAIL`.

**Now the resend limits.** Run this in **window 2, the same PowerShell window that signed up** (it
uses `$access` from the block above). Three requests to the "send me a verification email again"
address:

- line 1: asks for a new link with your token, right after sign-up;
- line 2: asks again without any token;
- line 3: after waiting 61 seconds, asks again with your token.

```powershell
$resend = 'http://localhost:8000/api/v1/me/verification-email/'
curl.exe -s -w " %{http_code}`n" -X POST -H "Authorization: Bearer $access" $resend     # 1: with token, too soon
curl.exe -s -w " %{http_code}`n" -X POST $resend                                        # 2: no token
Start-Sleep -Seconds 61                                                                 # 3: nothing prints for 61 seconds: normal, just wait
curl.exe -s -o NUL -w "after 61 s: %{http_code}`n" -X POST -H "Authorization: Bearer $access" $resend
```

**You should see** three output lines, one per curl (the `Start-Sleep` prints nothing):

```text
{"detail":"We sent one recently. Wait a little before asking again.","code":"verification_email_throttled"} 429
{"detail":"Authentication credentials were not provided.","code":"not_authenticated"} 401
after 61 s: 204
```

1. `429`: cooldown refused. The sign-up email counts for the 60-second cooldown, so the first resend
   is refused.
2. `401`: no token, so the server doesn't know who you are.
3. `204`: sent. After a minute it works, and window 1 prints a second email, now called "Verify your
   email" (no "Welcome").

- The answer to the throttled call has no `Retry-After`: the full bucket may be the minute one or
  the daily one (10 resends a day per address; the sign-up email doesn't count).
- The command waits 61 seconds on purpose.

**If it differs:** if line 1 says `401` instead of `429`, `$access` is empty: redo the sign-up part
of this step. If it says `204` instead of `429`, more than a minute passed since sign-up (that is
fine, the limit just wasn't tested).

#### Step 4: Verify the account with the link from the email

**Where:** Same terminal as step 3 (window 2). Needs `$h`, `$access` and `$resend` from step 3.

**What this does:** Pretends to be the browser opening the link from the email: it sends the key to
the verify endpoint, then checks the account is now verified, then tries several things that must
fail (reusing the link, a forged key, no headers, resending once verified).

Copy the part of the **last** link in window 1 after `/verify-email/` into `$raw` (the `%3A` stays
as it is). Replace the placeholder text:

```powershell
$raw = 'PASTE_THE_PART_AFTER_/verify-email/'
$key = [uri]::UnescapeDataString($raw)       # turn %3A back into :
$verify = 'http://localhost:8000/api/auth/app/v1/auth/email/verify'
"{""key"": ""$key""}" | Set-Content -Encoding ascii $env:TEMP\rz-verify.json
curl.exe -s -i @h -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-verify.json" $verify | Select-String '^HTTP|^Cache-Control|^Set-Cookie|^\{'   # 1: verify (prints 3 lines)
curl.exe -s -H "Authorization: Bearer $access" http://localhost:8000/api/v1/me/ | ConvertFrom-Json | Select-Object username, is_email_verified | ConvertTo-Json -Compress   # 2: am I verified now?
curl.exe -s -w " %{http_code}`n" @h -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-verify.json" $verify   # 3: same link again
'{"key": "forged"}' | Set-Content -Encoding ascii $env:TEMP\rz-forged.json
curl.exe -s -w " %{http_code}`n" @h -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-forged.json" $verify   # 4: made-up key
curl.exe -s -w " %{http_code}`n" -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-verify.json" $verify     # 5: without Origin / X-Requested-With headers
curl.exe -s -w " %{http_code}`n" -X POST -H "Authorization: Bearer $access" $resend                                          # 6: resend when already verified
curl.exe -s -w " %{http_code}`n" @h -X POST http://localhost:8000/api/auth/app/v1/auth/email/verify/resend                   # 7: allauth's own resend address
```

**You should see** (7 `curl.exe` commands, 9 lines; command 1 prints 3 lines):

```text
HTTP/1.1 200 OK
Cache-Control: max-age=0, no-cache, no-store, must-revalidate, private
{"status": 200}
{"username":"part2_010027","is_email_verified":true}
{"status": 400, "errors": [{"message": "Invalid or expired key.", "code": "invalid_or_expired_key", "param": "key"}]} 400
{"status": 400, "errors": [{"message": "Invalid or expired key.", "code": "invalid_or_expired_key", "param": "key"}]} 400
{"status": 403, "errors": [{"code": "csrf_failed", "message": "Reload the page and try again."}]} 403
{"detail":"Your email is already verified.","code":"already_verified"} 409
{"status": 404, "errors": [{"code": "not_found", "message": "Not found."}]} 404
```

1. Lines 1 to 3: the verification worked (`200`), with no cookie line.
2. Line 4: `is_email_verified` is now `true`.
3. Line 5: `400`, the same link used a second time is refused.
4. Line 6: `400`, a forged key is refused with the same message.
5. Line 7: `403`, refused because the `Origin` and `X-Requested-With` headers were missing.
6. Line 8: `409`, already verified, so nothing is sent.
7. Line 9: `404`, allauth's own resend address stays closed.

- The verification answered 200 with no cookies: a link never logs anyone in. allauth itself says
  401 here ("verified, but nobody is logged in"); the middleware turns that into 200.
- The same link again, and a forged one, both say `invalid_or_expired_key`: an expired link says
  the same. The call without `Origin` and `X-Requested-With` is refused like every other unsafe
  `/api/auth/` call.
- Once verified, the resend is a 409 and sends nothing. allauth's own `auth/email/verify/resend` is
  the code-flow view and stays closed (404).

**If it differs:** if command 1 prints a 400 and no `200`, the pasted key is from an older email or
still has a stray character; copy the **last** link in window 1 again. If commands 2 and later fail
with 401, `$access` is empty: redo step 3.

#### Step 5: Forgot password gives the same answer for every address

**Where:** Same terminal as step 3 (window 2). Needs `$h` and `$id` from step 3.

**What this does:** Asks for a password reset for a real address and for an address that does not
exist, and checks the server answers byte for byte the same, so nobody can find out who has an
account.

```powershell
$rp = 'http://localhost:8000/api/auth/app/v1/auth/password/request'
function Ask($email) {
  "{""email"": ""$email""}" | Set-Content -Encoding ascii $env:TEMP\rz-ask.json
  curl.exe -s -i @h -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-ask.json" $rp | Where-Object { $_ -notmatch '^(Date|Expires|Set-Cookie):' }
}
Ask "part2-$id@example.test" | Set-Content $env:TEMP\rz-known.txt      # real account: answer saved to a file
Ask "nobody-$id@example.test" | Set-Content $env:TEMP\rz-unknown.txt   # unknown address: answer saved to a file
Get-Content $env:TEMP\rz-known.txt
if ((Get-Content $env:TEMP\rz-known.txt -Raw) -eq (Get-Content $env:TEMP\rz-unknown.txt -Raw)) { "identical: status, headers and body" } else { "DIFFERENT" }
```

**You should see:** the `function Ask` block and the two `Ask ...` lines print nothing (their output
goes to files). `Get-Content` shows the saved answer, then the last line compares the two files:

```text
HTTP/1.1 200 OK
Server: WSGIServer/0.2 CPython/3.13.16
Content-Type: application/json
Cache-Control: max-age=0, no-cache, no-store, must-revalidate, private
X-Frame-Options: DENY
Content-Length: 15
X-Content-Type-Options: nosniff
Referrer-Policy: same-origin
Cross-Origin-Opener-Policy: same-origin

{"status": 200}
identical: status, headers and body
```

- Window 1 shows **one** new email, "Reset your password", addressed to the real account. Nothing is
  printed for the unknown address. The time-dependent headers (`Date`, `Expires`) are left out of the
  comparison on purpose.
- The link in that email is `http://localhost:3000/reset-password/<key>`: 32 hex digits, a time and
  a hash, valid for 24 hours and for one use.

**If it differs:** if the last line prints `DIFFERENT`, that is a real bug in the server; note it
down. If the answer is `403`, `$h` is empty: redo step 3.

**The limits** (each uses a new address, and an address that doesn't exist is limited the same way,
so the limit leaks nothing). Same window 2. The loop sends 6 requests for one address in a row, then
one request with a malformed address:

```powershell
1..6 | ForEach-Object {
  "{""email"": ""busy-$id@example.test""}" | Set-Content -Encoding ascii $env:TEMP\rz-ask.json
  $r = curl.exe -s -w " %{http_code}" @h -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-ask.json" $rp
  "{0}  {1}" -f $_, $r
}
'{"email": "not-an-email"}' | Set-Content -Encoding ascii $env:TEMP\rz-ask.json
curl.exe -s -w " %{http_code}`n" @h -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-ask.json" $rp
```

**You should see:**

```text
1  {"status": 200} 200
2  {"status": 200} 200
3  {"status": 200} 200
4  {"status": 200} 200
5  {"status": 200} 200
6  {"status": 429} 429
{"status": 400, "errors": [{"message": "Enter a valid email address.", "code": "invalid", "param": "email"}]} 400
```

Requests 1 to 5 are accepted (`200`), request 6 is refused (`429`, too many), and the malformed
address is a `400`.

- Five a minute per address. There are also 10 a day per address and 50 a day per IP (the
  automated tests walk through both with a moved clock). A malformed address is a 400 and never
  counts.

#### Step 6: The reset logs you in and ends the other sessions

**Where:** Same terminal as step 3 (window 2), with window 1 open to read the email. Needs `$h`,
`$id` and `$rp` from steps 3 and 5.

**What this does:** Logs in "in another browser" with the old password (its own cookie file), then
resets the password with the emailed key. Afterwards the other browser must be logged out, the new
session must work, and only the new password must log in.

First, log in "in another browser" with the old password. The `-c` option saves that browser's
cookies to `rz-other.txt` in your temp folder:

```powershell
$login = 'http://localhost:8000/api/auth/app/v1/auth/login'
$refresh = 'http://localhost:8000/api/auth/app/v1/tokens/refresh'
"{""email"": ""part2-$id@example.test"", ""password"": ""correct-horse-battery-42""}" | Set-Content -Encoding ascii $env:TEMP\rz-login.json
curl.exe -s -c $env:TEMP\rz-other.txt @h -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-login.json" $login | ConvertFrom-Json | Select-Object status | ConvertTo-Json -Compress
curl.exe -s -o NUL -w "other browser refresh before the reset: %{http_code}`n" -b $env:TEMP\rz-other.txt -c $env:TEMP\rz-other.txt @h -X POST $refresh
```

**You should see:**

```text
{"status":200}
other browser refresh before the reset: 200
```

The login worked and the other browser can refresh its session.

Next, ask for a link for the real address once more, wait for it in window 1, and copy the part
after `/reset-password/` into `$rk` (replace the placeholder):

```powershell
"{""email"": ""part2-$id@example.test""}" | Set-Content -Encoding ascii $env:TEMP\rz-ask.json
curl.exe -s -o NUL -w "request: %{http_code}`n" @h -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-ask.json" $rp
$rk = 'PASTE_THE_PART_AFTER_/reset-password/'
$reset = 'http://localhost:8000/api/auth/app/v1/auth/password/reset'
curl.exe -s -o NUL -w "key check: %{http_code}`n" -H "X-Password-Reset-Key: $rk" $reset
curl.exe -s -w " %{http_code}`n" -H "X-Password-Reset-Key: nonsense" $reset
"{""key"": ""$rk"", ""password"": ""short""}" | Set-Content -Encoding ascii $env:TEMP\rz-reset.json
curl.exe -s -w " %{http_code}`n" @h -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-reset.json" $reset
"{""key"": ""$rk"", ""password"": ""a-brand-new-passphrase-77""}" | Set-Content -Encoding ascii $env:TEMP\rz-reset.json
$out = curl.exe -s -i -c $env:TEMP\rz-new.txt @h -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-reset.json" $reset
$out | Select-String '^HTTP|^Set-Cookie|^Cache-Control' | ForEach-Object { $_.Line -replace 'rz_refresh=[^;]+', 'rz_refresh=<token>' }
$body = $out[-1] | ConvertFrom-Json
"user: $($body.data.user.username); meta fields: $(($body.meta.PSObject.Properties.Name) -join ', '); access token: $($body.meta.access_token.Length) characters"
curl.exe -s -w " %{http_code}`n" -b $env:TEMP\rz-other.txt @h -X POST $refresh
curl.exe -s -o NUL -w "the new session refreshes: %{http_code}`n" -b $env:TEMP\rz-new.txt -c $env:TEMP\rz-new.txt @h -X POST $refresh
"{""key"": ""$rk"", ""password"": ""yet-another-passphrase-55""}" | Set-Content -Encoding ascii $env:TEMP\rz-reset.json
curl.exe -s -w " %{http_code}`n" @h -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-reset.json" $reset
"{""email"": ""part2-$id@example.test"", ""password"": ""correct-horse-battery-42""}" | Set-Content -Encoding ascii $env:TEMP\rz-login.json
curl.exe -s -o NUL -w "old password: %{http_code}`n" @h -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-login.json" $login
"{""email"": ""part2-$id@example.test"", ""password"": ""a-brand-new-passphrase-77""}" | Set-Content -Encoding ascii $env:TEMP\rz-login.json
curl.exe -s -o NUL -w "new password: %{http_code}`n" @h -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-login.json" $login
```

**You should see** (the lines that write JSON files, and the `$rk`, `$reset`, `$out`, `$body` lines,
print nothing):

```text
request: 200
key check: 200
{"status": 400, "errors": [{"message": "The password reset token was invalid.", "code": "invalid_password_reset", "param": "key"}]} 400
{"status": 400, "errors": [{"message": "This password is too short. It must contain at least 8 characters.", "code": "password_too_short", "param": "password"}]} 400
HTTP/1.1 200 OK
Cache-Control: max-age=0, no-cache, no-store, must-revalidate, private
Set-Cookie:  rz_refresh=<token>; expires=…; HttpOnly; Max-Age=1209600; Path=/api/auth/; SameSite=Lax
Set-Cookie:  rz_session=1; expires=…; Max-Age=1209600; Path=/; SameSite=Lax
user: part2_010027; meta fields: is_authenticated, access_token; access token: 373 characters
{"status": 400} 400
the new session refreshes: 200
{"status": 400, "errors": [{"message": "The password reset token was invalid.", "code": "invalid_password_reset", "param": "key"}]} 400
old password: 400
new password: 200
```

What each line means, in order:

1. `request: 200`: the reset email was requested (it appears in window 1).
2. `key check: 200`: the emailed key is valid.
3. `... 400` with "token was invalid": the made-up key `nonsense` is refused.
4. `... 400` with "too short": a weak password is refused (and does not use the key up).
5. Lines `HTTP/1.1 200 OK` to the two `Set-Cookie` lines, then `user: ...`: the real reset worked and
   logged this session in (an access token and two cookies, like a login).
6. `{"status": 400} 400`: **the other browser's refresh now fails**.
7. `the new session refreshes: 200`: the session created by the reset still works.
8. `... 400` with "token was invalid": the same link a second time is refused.
9. `old password: 400`: the old password no longer logs in.
10. `new password: 200`: the new password does.

- The key check is the page's pre-check: `GET` with the key in `X-Password-Reset-Key` (it answers
  with the account's details, which the page ignores). A refused weak password doesn't use the key up.
- The reset answers like a login: an access token in `meta` and the same two cookies, and the
  browser that did it is logged in.
- **The other browser's refresh now fails (400):** the password changed, so every other session
  ends the next time it refreshes. Its access token still works for up to 15 minutes, like after a
  logout. The same link again is refused.

**If it differs:** if `key check` is not `200`, `$rk` is wrong or empty: copy the part after
`/reset-password/` from the **last** reset email in window 1 and set `$rk` again.

#### Step 7: An expired verification link

**Where:** A PowerShell window in `backend\` with the venv active (window 2 after
`.\.venv\Scripts\Activate.ps1`, or a spare window). It only reads the database, so `runserver` can
keep running.

**What this does:** Builds the key a verification link would have had 25 hours ago, so you can see
the "expired" screen in step 8.

Needs an account whose address is still unverified: sign up another one the way step 3 does (a new
`$id`), then forge the key a link would have had 25 hours ago:

```powershell
# in backend/ with the venv active; replace ID with the id of the unverified account
python manage.py shell -c "import time; from unittest import mock; from allauth.account.models import EmailAddress, EmailConfirmationHMAC; a = EmailAddress.objects.get(email='part2-ID@example.test'); real = time.time; mock.patch('time.time', lambda: real() - 25 * 3600).start(); print(EmailConfirmationHMAC(a).key)"
```

**You should see:** a key with two `:` (after Django's "objects imported" line).

- Open `http://localhost:3000/verify-email/<that key>` in the browser (step 8) and you get the
  expired state, with a working "Send a new link" once you are logged in as that account.
- The automated tests do the same with an exact 86 399 s / 86 401 s boundary.

**If it differs:** if you get `EmailAddress matching query does not exist`, the `ID` is wrong; use
the `$id` of the account you signed up (its email is `part2-<id>@example.test`).

#### Step 8: Look at the pages in the browser

**Where:** Browser (http://localhost:3000), with window 1 (`runserver`) and window 3 (`npm run dev`)
running.

**What this does:** Walks through every new screen by hand: verify email, forgot password and reset
password.

Window 1's `runserver` and a third window's `npm run dev` (in `frontend\`) are running. Use
http://localhost:3000, a new email address each time, and compare with the Stitch screens
`a4_verify_email`, `a5_forgot_password` and `a6_reset_password` in
`design/stitch/stitch_website_sitemap_grid_builder/` (the logo replaces their emblem tiles, and
their state switcher, "Simulate instant link click" and jargon footers are gone).

**You should see**, for each row, what is in the "Expect" column:

| Do this | Expect |
|---|---|
| Sign up at /signup with a new email, username and `correct-horse-battery-42` | You land on **/verify-email** (not /home): "Verify your email", "We sent a verification link to **your address**", a blue "Read-only for now" callout, a tinted "Resend email (58s)" counting down, the spam hint, "Continue browsing read-only →" and "Links expire 24 hours after they're sent." |
| Wait for the countdown to reach 0 | The button turns blue: "Resend email". Click it: the text "We sent a new verification link. Check your inbox." appears under it, the countdown starts again at 60, and window 1 prints a second email. |
| Click "Continue browsing read-only →" | /home with the amber banner "Verify your email to post, comment and report." and a **Resend link** button. The rail's **New post** button is faded. |
| Click **New post** (rail, or the bottom tab at 390 px) | Nothing opens; a dark toast says "Verify your email to post. Check your inbox, or resend the link from the banner." Tab to the button: it takes focus, and a screen reader reads "Verify your email to post." |
| Click **Resend link** twice in a row | The first click is refused if you signed up less than a minute ago (toast: "We sent one recently. Wait a little before asking again.") and the button shows "Resend link (60s)"; after a minute it works (toast: "We sent a new verification link. Check your inbox."). |
| Copy the link from the **last** email in window 1 and open it in a second tab | "Your email is verified" with **Start posting →**. The first tab's banner disappears by itself within a moment (the tabs tell each other), and New post is no longer faded. |
| Reload the link's tab | "Your email is already verified": the link was used. |
| Log out, then open the same link again | "This link has expired" with "Log in to send a new link" (it points at `/login?next=%2Fverify-email`). |
| Open `/verify-email/Mg%3A1vABcd%3Aabc-DEF_123` | The same expired state (a made-up key). |
| Open /login and click **Forgot password?** (right under the password field) | /forgot-password: "Reset your password", an email field, "Send reset link →", "Back to log in". |
| Submit an empty field, then `not-an-email` | "Enter your email address.", then "Enter a valid email address." under the field. |
| Submit the real address, then repeat with an address that doesn't exist | The same "Check your inbox" message both times: "If an account exists for **that address**, we've sent a link to reset your password. It expires in 24 hours." Window 1 printed an email only for the real one. "Use a different email" goes back to the form. |
| Open the link from the reset email | A short skeleton, then "Create new password": New password with the strength bar, Confirm new password, show/hide toggles, "Use at least 8 characters.", and the callout "This also signs you out on your other devices." |
| Type `abc` and `abd`, submit | "Use at least 8 characters." under New password; nothing is sent. |
| Type a good password and a different confirmation | "The passwords don't match." under Confirm; nothing is sent. |
| Type `password1234` in both | Django refuses it: "This password is too common." under New password. |
| Type a good password in both and submit | The toast "Password changed. You're logged in." and /home with your @username in the rail. |
| Open the same reset link again | "This link has expired" with **Request a new link** (→ /forgot-password), before any password field is shown. |
| Log out and log in with the new password | /home. The old password says "That email and password don't match." |
| Phone width (F12 → device toolbar, 390 px) on every page above | No sideways scrolling; the Resend button, the callouts and the form fit the card. |

#### Step 9: The emails on disk, and where every link points

**Where:** First window 1 (restart the server), then window 2 (from the repo root).

**What this does:** Restarts the server so emails are written to files instead of the terminal, then
inspects the newest email file to prove every link points at the frontend (`localhost:3000`) and never
at the backend.

Stop `runserver` in window 1 (`Ctrl+C`) and start it so that emails go to files (in `backend\`, venv
active):

```powershell
$env:EMAIL_PROVIDER = "file"; python manage.py runserver
```

Sign up or request a reset in the browser (so an email is written), then in window 2 (repo root):

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero
$f = Get-ChildItem backend\tmp\mail\*.log | Sort-Object LastWriteTime -Descending | Select-Object -First 1   # the newest email file
Select-String -Path $f.FullName -Pattern '^(From|To|Subject):' | ForEach-Object { $_.Line }                  # who, to whom, subject
Select-String -Path $f.FullName -Pattern '(href|src)="[^"]+"' -AllMatches | ForEach-Object { $_.Matches.Value -replace '(="https?://[^/"]+).*', '$1…' } | Sort-Object -Unique   # every link and the logo, shortened to the origin
Select-String -Path $f.FullName -Pattern 'https?://[^ "<]+' -AllMatches | ForEach-Object { $_.Matches.Value -replace '^(https?://[^/]+).*', '$1' } | Sort-Object -Unique           # every URL in the file, shortened to the origin
git check-ignore "backend/tmp/mail/$($f.Name)"                                                                # prints the path if git ignores it
```

**You should see** (the subject depends on which email you triggered; the address and file name
differ, and the order of the `href`/`src` lines may differ):

```text
Subject: [Rumor Zero] Reset your password
From: Rumor Zero <no-reply@example.com>
To: part2-012510@example.test
href="http://localhost:3000…
src="http://localhost:3000…
http://localhost:3000
backend/tmp/mail/20261006-192649-135804298251632.log
```

- `From` is your `DEFAULT_FROM_EMAIL`. Every `href`, the logo `src` and every URL in the file start
  with `http://localhost:3000` (your `FRONTEND_ORIGIN`): there is no backend address in any email.
- `git check-ignore` prints the path: emails written by `EMAIL_PROVIDER=file` are never committed.
  This is the folder the E2E tests read.
- Stop this server and start a normal `python manage.py runserver` again if you want the console
  emails back (in PowerShell: `Remove-Item Env:EMAIL_PROVIDER` first, or open a new window).

**If it differs:** if `Get-ChildItem` says it cannot find the path, the server was not started with
`$env:EMAIL_PROVIDER = "file"`, or no email was triggered yet; start it as above and sign up again.

#### Step 10: Automated frontend checks

**Where:** A PowerShell window in `frontend\` (stop `npm run dev` in window 3 first with `Ctrl+C`,
then reuse window 3).

**What this does:** Runs the frontend linters, type check, unit tests and a production build.

```powershell
npm run lint             # no output after the command line
npm run lint:tokens      # lint:tokens OK (no default palette, raw hex, stray radius, shadow or type size)
npm run typecheck        # no output after the command line
npm run format:check     # All matched files use Prettier code style!
npm test                 # Test Files  65 passed (65) / Tests  708 passed (708)
npm run build
```

**You should see:** the messages in the comments (`npm run lint` and `npm run typecheck` print
nothing after the command line; that means success). `npm run build` takes a minute and ends with a
route list that gains these lines (the two key pages are dynamic, because the key is a route
parameter):

```text
├ ○ /forgot-password
├ ƒ /reset-password/[key]
├ ○ /verify-email
└ ƒ /verify-email/[key]
```

- The new screens have tests for every state: verifying, verified, already verified, expired and
  failed; the idle and sent forms; the expired, checking, mismatch and weak-password states; the
  resend countdown; New post gating (both copies, with their own hint ids); the banner's Resend; the
  sign-up redirect with and without `?next=`; the two-tab "user-changed" message.

#### Step 11: The E2E tests, dev mode and CI mode

**Where:** The same PowerShell window in `frontend\` (window 3). Stop `runserver` in window 1 first.

**What this does:** Playwright drives a real browser through the whole flow. It starts its own
servers, so window 1 must be stopped to free the ports.

Stop `runserver` too: Playwright then starts its own Django with an in-memory cache, and with
`EMAIL_PROVIDER=file`.

```powershell
npm run test:e2e
```

**You should see** (takes about half a minute; the order of the tests and the timings differ):

```text
Running 15 tests using 6 workers

  ok   4 [chromium] › e2e/email-flows.spec.ts:101:5 › an unknown address gets the same page and no email (6.0s)
  ...
  ok   6 [chromium] › e2e/email-flows.spec.ts:53:5 › forgot password → read the email → reset → logged in → log in with the new password (18.3s)

  15 passed (29.2s)
```

- Eleven tests are Parts 0C and 1 (`auth.spec.ts` now continues from `/verify-email` to `/home`). The
  four new ones are in `email-flows.spec.ts`:
  1. sign up → New post is `aria-disabled` → read the email from `backend/tmp/mail` → open the link
     → verified → "Start posting" → the banner is gone and New post is enabled → the used link says
     "already verified";
  2. forgot password → read the email → a mismatch error → reset → logged in → log out → the old
     password fails and the new one works, and the used link is expired;
  3. an unknown address gets the same page and no email;
  4. dead reset and verification links show their expired states.
- The first request of a cold Django used to fail now and then with a 500 when several sign-ups
  arrived together; that is fixed (MEMORY, 2026-10-07).

Then the way CI runs it (a production build, tested with `next start`):

```powershell
npm run build
$env:CI = "1"
npm run test:e2e         # 15 passed, this time against `next start`
Remove-Item Env:CI
```

**You should see:** `15 passed` again. (`Remove-Item Env:CI` switches CI mode off again.)

#### Step 12: Repository checks

**Where:** Terminal window 2 (any PowerShell window; the first command moves to the repo root).

**What this does:** Confirms nothing you should not commit (design files, env files, mail logs) is
pending in git. These are read-only git commands.

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero
git status --short design                          # prints nothing: design\ is untouched
git status --short | Select-String '\.env|tmp/'    # prints nothing: no env file and no mail file is a candidate for a commit
git status --short backend/templates               # ?? backend/templates/ (new, until you commit it)
```

**You should see:** nothing from the second and third lines of output (the comments explain), and
`?? backend/templates/` from the last command until you commit it.

#### Step 13: CI on GitHub (after you push)

**Where:** Browser.

**What this does:** Checks that the automatic tests also pass on GitHub once you have pushed.

| URL | Expect |
|---|---|
| Your repository's **Actions** tab on github.com | A "CI" run for your push with three green jobs |

- No workflow change was needed: Playwright sets `EMAIL_PROVIDER=file` for the Django it starts, and
  the process environment wins over the `backend/.env` the job copies from `.env.example`.
- The agent couldn't run CI: only you push.

#### Step 14: Stop and clean up

**Where:** Every terminal window, plus the repo root for the last commands.

**What this does:** Stops the servers and removes the temporary files these steps created.

- Stop the servers: `Ctrl+C` in each window (leftover `next dev`: step 12 of Part 1).
- Delete the helper files:

  ```powershell
  Remove-Item $env:TEMP\rz-signup.json, $env:TEMP\rz-verify.json, $env:TEMP\rz-forged.json, $env:TEMP\rz-ask.json, $env:TEMP\rz-known.txt, $env:TEMP\rz-unknown.txt, $env:TEMP\rz-login.json, $env:TEMP\rz-reset.json, $env:TEMP\rz-other.txt, $env:TEMP\rz-new.txt
  ```

- `backend\tmp\mail\` fills up with `.log` files from `EMAIL_PROVIDER=file` and the E2E runs. It is
  git-ignored; delete the folder whenever you like.
- The test accounts stay in your local database: `part2_…` from these steps, the E2E's `verify_…`
  and `reset_…`, and the agent's `shot_…`/`p_shot_…`. Delete them in Django Admin → Users if you
  like. `docker compose down -v` (repo root) wipes the whole local database, which is destructive.
- Stop the containers and keep the data: `docker compose down` (repo root).

### Part 3: Continue with Google

Needs Part 0A's containers and virtualenv, Part 0C's frontend, and your own `backend\.env` and
`frontend\.env.local`. Part 3 adds no dependency and no env variable (both Google client-ID variables
have been in the example files since Part 0A). It does add allauth's own `socialaccount` tables:
`migrate` applies six migrations of theirs, and we add none.

**Which terminal window for what.** Open the windows once and keep using the same ones:

| Window | What runs in it | Used in steps |
|---|---|---|
| Window 1 (server) | `python manage.py runserver` in `backend\`, venv active. Leave it running; it is restarted in steps 5 and 6. | 4 to 8 |
| Window 2 (commands) | All the `curl.exe` and `python manage.py` commands. **Use the same window for step 5**: the variables and functions you set there only live in that one PowerShell window. | 1 to 8 |
| Window 3 (frontend) | `npm run dev` in `frontend\`. Leave it running; it is restarted in step 6. | 6 to 8 |
| Browser | Steps 6 to 8 | 6 to 8 |

Things to know first:

- **Steps 1 to 6 need no Google account.** Steps 7 and 8 do: they are the manual check from
  `task.md` ("works end to end on `http://localhost:3000` with your client ID"), because a real
  Google sign-in can't be automated. The agent that built this part could not run steps 7 and 8.
- **The PowerShell blocks below were not run on Windows.** The agent works on the Linux PC; it ran
  the bash twin of every command in the Linux guide on 2026-10-08, and the outputs below are those.
  The PowerShell commands follow the patterns Parts 1 and 2 proved on Windows (JSON written to a file
  and sent with `--data-binary "@file"`, `curl.exe`, no `&&`). If one behaves differently, tell the
  agent which.
- Steps 4 and 5 use **no real client ID**: step 4 leaves it blank, step 5 uses a made-up one
  (`rz-manual-test.apps.googleusercontent.com`) that is set only for that `runserver`. Neither step
  edits `backend\.env`, and neither needs your real client ID.
- The new-user and linking rules (staff, inactive, Gmail or Workspace only, password wipe, verified
  address) are covered by 98 automated tests that sign real RS256 tokens against a fake Google
  certificate (step 2). Step 5 only checks what is visible from outside.
- Google's script and certificates need internet. Step 5's last request asks Google for its
  certificates, so it needs internet too.
- Your Google client's **Authorized JavaScript origins** must contain `http://localhost:3000` (and
  `http://localhost`): ENV_GUIDE §1.6. New origins can take minutes (rarely hours) to start working.
- **PowerShell can't set an empty environment variable:** `$env:NAME = ""` *deletes* the variable, and
  the server would then read the real value from `backend\.env`. Steps 4 and 6 therefore start the
  program from a tiny `python -c` / `node -e` line that passes the variable as an empty string.

#### Step 1: Apply allauth's Google tables and check nothing else changed

**Where:** Terminal window 2 (commands), PowerShell.

**What this does:** Starts the database containers, activates the Python environment, applies
allauth's `socialaccount` migrations and confirms we have no model changes of our own.

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero
docker compose up -d
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py migrate                           # first time: six "Applying socialaccount.… OK" lines
python manage.py check                             # System check identified no issues (0 silenced).
python manage.py makemigrations --check --dry-run  # No changes detected
python manage.py showmigrations socialaccount
```

**You should see:** the first run of `migrate` after pulling Part 3 lists these lines (a database
that already has them says `No migrations to apply.`):

```text
  Applying socialaccount.0001_initial... OK
  Applying socialaccount.0002_token_max_lengths... OK
  Applying socialaccount.0003_extra_data_default_dict... OK
  Applying socialaccount.0004_app_provider_id_settings... OK
  Applying socialaccount.0005_socialtoken_nullable_app... OK
  Applying socialaccount.0006_alter_socialaccount_extra_data... OK
```

Then the two checks print their messages (in the comments above), and `showmigrations` ends with:

```text
socialaccount
 [X] 0001_initial
 [X] 0002_token_max_lengths
 [X] 0003_extra_data_default_dict
 [X] 0004_app_provider_id_settings
 [X] 0005_socialtoken_nullable_app
 [X] 0006_alter_socialaccount_extra_data
```

#### Step 2: Run the automated backend checks

**Where:** Same terminal as step 1 (window 2, in `backend\`, venv active).

**What this does:** Runs the whole backend test suite, then only the new Part 3 test files, then the
linter and formatter check.

```powershell
python -m pytest                                    # 704 passed
python -m pytest apps/accounts/tests/test_google_login.py apps/accounts/tests/test_usernames.py -q   # 98 passed
ruff check . ; ruff format --check .                # All checks passed! / 77 files already formatted
```

**You should see:** the full run ends with `704 passed`, the second command with `98 passed` (60 in
`test_google_login.py`, 38 in `test_usernames.py`), and the last prints `All checks passed!` and
`77 files already formatted`. (Counts may grow later; what matters is that nothing fails.)

- `test_google_login.py` signs real RS256 ID tokens with a test key and serves the matching
  certificate in place of Google's, so allauth's own checks (`aud`, `iss`, `exp`, `iat`, signature and
  replay) run unpatched. It covers: a new user (verified, generated username, no display name, no
  password), linking a verified or unverified account, Gmail and Workspace only, no staff linking,
  inactive accounts, every kind of bad token and request, the 404 when disabled, the session rules
  and the rate limit.
- `test_usernames.py` covers the username rules ("Ada", "José", "Mary-Jane", "李", reserved words,
  collisions).

#### Step 3: Run the automated frontend checks

**Where:** Terminal window 2, then `cd ..\frontend`. Playwright (the last command) starts Django and
Next itself, so **no servers may be running on ports 3000 and 8000** (it reuses them if they are, with
whatever settings they have).

**What this does:** Runs the linters, the type check, the component tests, the production build and
the end-to-end tests.

```powershell
cd ..\frontend                                      # from backend\
npm run lint ; npm run lint:tokens ; npm run typecheck ; npm run format:check
npm test                                            # 67 files, 747 tests passed
npm run build
npm run test:e2e                                    # 15 passed
```

**You should see:** the first line prints nothing from ESLint and TypeScript and ends with
`lint:tokens OK (…)` and `All matched files use Prettier code style!`. `npm test` ends with
`Test Files  67 passed (67)` and `Tests  747 passed (747)`. `npm run build` lists the routes (as in
Part 2). `npm run test:e2e` ends with `15 passed`.

- The new component tests are `GoogleButton.test.tsx` (20) and `google-identity.test.ts` (7); the login
  and sign-up form tests and `auth-api.test.ts` grew too.
- The E2E run pins an empty Google client ID for both servers, so it never contacts Google: the button
  is hidden there. (The Linux guide also runs the E2E in CI mode against a build with no client ID
  baked in; on Windows `$env:CI = "1"` after `npm run build` works as in Part 1, but it can't blank the
  client ID, so a `frontend\.env.local` with your real ID makes that run less representative.)

#### Step 4: With no client ID, Google sign-in is switched off

**Where:** First window 1 (start the server), then window 2 (the commands).

**What this does:** An empty `GOOGLE_OAUTH_CLIENT_ID` disables the feature "cleanly": the endpoint
answers 404, exactly like a path that doesn't exist. The variable is emptied for this one `runserver`
only (the process environment beats `backend\.env`).

Window 1 (in `backend\`, venv active; stop any other `runserver` first with `Ctrl+C`). It starts
`manage.py` from Python, because that can pass an *empty* value (see the note above):

```powershell
python -c "import os, subprocess, sys; subprocess.run([sys.executable, 'manage.py', 'runserver'], env={**os.environ, 'GOOGLE_OAUTH_CLIENT_ID': ''})"
```

Window 2:

```powershell
$h = '-H', 'Origin: http://localhost:3000', '-H', 'X-Requested-With: rumor-zero'    # headers every API call needs
$url = 'http://localhost:8000/api/auth/app/v1/auth/provider/token'
'{"provider":"google","process":"login","token":{"client_id":"x.apps.googleusercontent.com","id_token":"a.b.c"}}' | Set-Content -Encoding ascii $env:TEMP\rz-google.json
curl.exe -s -w ' %{http_code}\n' @h -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-google.json" $url   # 1: the sign-in
curl.exe -s -w ' %{http_code}\n' @h $url                                                                                  # 2: a GET
curl.exe -s -o NUL -w '%{http_code}\n' @h -X POST -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-google.json" http://localhost:8000/api/auth/app/v1/auth/provider/signup   # 3: allauth's other social paths
curl.exe -s -o NUL -w '%{http_code}\n' @h http://localhost:8000/api/auth/app/v1/account/providers                                                                                      # 4
```

**You should see** (four commands, four answers):

```text
{"status": 404, "errors": [{"code": "not_found", "message": "Not found."}]} 404
{"status": 404, "errors": [{"code": "not_found", "message": "Not found."}]} 404
404
404
```

- Commands 3 and 4 show that allauth's other social endpoints (`auth/provider/signup`,
  `account/providers`, and `auth/provider/redirect`) are never reachable, with or without a client ID.

#### Step 5: With a client ID, check what an outsider can and can't do

**Where:** Window 1 (restart the server), then window 2. Window 2 must be the same PowerShell window
for the whole step (the variables and functions only live there).

**What this does:** Restarts the server with a made-up client ID, so the endpoint is on. Then it sends
requests that are not a real Google sign-in. Each must be refused, and none may crash the server. (A
real, signed token can only come from Google, so the success cases are in step 2's tests and steps 7
and 8.)

Window 1 (`Ctrl+C` the server of step 4, then, in `backend\` with the venv active):

```powershell
$env:GOOGLE_OAUTH_CLIENT_ID = "rz-manual-test.apps.googleusercontent.com"; python manage.py runserver
```

(That variable only lives in window 1. Before step 6, in window 1 after `Ctrl+C`:
`Remove-Item Env:GOOGLE_OAUTH_CLIENT_ID`.)

Window 2:

```powershell
$h = '-H', 'Origin: http://localhost:3000', '-H', 'X-Requested-With: rumor-zero'
$url = 'http://localhost:8000/api/auth/app/v1/auth/provider/token'
$cid = 'rz-manual-test.apps.googleusercontent.com'
function b64($s) { [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($s)).TrimEnd('=').Replace('+','-').Replace('/','_') }    # base64url, as JWTs use
$payload = b64 ('{"iss":"https://accounts.google.com","aud":"' + $cid + '","sub":"1","email":"x@gmail.com","email_verified":true,"exp":4000000000}')
$rs    = (b64 '{"alg":"RS256","kid":"forged-kid","typ":"JWT"}') + '.' + $payload + '.' + (b64 'not-a-real-signature')   # looks like Google's, is not
$hs    = (b64 '{"alg":"HS256","kid":"k","typ":"JWT"}') + '.' + $payload + '.' + (b64 'sig')                             # the wrong algorithm
$nokid = (b64 '{"alg":"RS256","typ":"JWT"}') + '.' + $payload + '.' + (b64 'sig')                                      # no key id
function mk($client, $token) { '{"provider":"google","process":"login","token":{"client_id":"' + $client + '","id_token":"' + $token + '"}}' }
function post($json) { $json | Set-Content -Encoding ascii $env:TEMP\rz-google.json; curl.exe -s -w ' %{http_code}\n' @h -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-google.json" $url }
"1 no headers:";      mk $cid $rs | Set-Content -Encoding ascii $env:TEMP\rz-google.json; curl.exe -s -w ' %{http_code}\n' -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-google.json" $url
"2 garbage token:";   post (mk $cid 'not-a-jwt')
"3 HS256:";           post (mk $cid $hs)
"4 no kid:";          post (mk $cid $nokid)
"5 wrong client_id:"; post (mk 'other.apps.googleusercontent.com' $rs)
"6 connect:";         post ('{"provider":"google","process":"connect","token":{"client_id":"' + $cid + '","id_token":"' + $rs + '"}}')
"7 GET:";             curl.exe -s -w ' %{http_code}\n' @h $url
"8 forged RS256 (asks Google for its certificates; needs internet):"; post (mk $cid $rs)
```

**You should see** (eight labels, each followed by one answer):

```text
1 no headers:
{"status": 403, "errors": [{"code": "csrf_failed", "message": "Reload the page and try again."}]} 403
2 garbage token:
{"status": 400, "errors": [{"code": "invalid_token", "message": "Invalid token.", "param": "token"}]} 400
3 HS256:
{"status": 400, "errors": [{"code": "invalid_token", "message": "Invalid token.", "param": "token"}]} 400
4 no kid:
{"status": 400, "errors": [{"code": "invalid_token", "message": "Invalid token.", "param": "token"}]} 400
5 wrong client_id:
{"status": 400, "errors": [{"code": "invalid_token", "message": "Invalid token.", "param": "token"}]} 400
6 connect:
{"status": 400, "errors": [{"code": "invalid_token", "message": "Invalid token.", "param": "token"}]} 400
7 GET:
{"status": 404, "errors": [{"code": "not_found", "message": "Not found."}]} 404
8 forged RS256 (asks Google for its certificates; needs internet):
{"status": 400, "errors": [{"message": "Invalid token.", "code": "invalid_token", "param": "token"}]} 400
```

- 1: no `Origin` / `X-Requested-With`, so refused before anything else (the same guard as login).
- 2 to 6: refused by our own shape check (`apps/accounts/google.py`) without calling Google. Without
  it, 3 and 4 would crash allauth with a 500. A real token has an `RS256` header with a key id, a
  client ID equal to the server's, and `process` "login".
- 8: passes our check, so allauth asks Google for its certificates, finds no key called
  `forged-kid` and refuses. (The key order in this body is allauth's own, so it differs from 2 to 6.)
- Window 1 printed one line for command 5, naming the variables and never the values:
  `WARNING apps.accounts.google: A Google sign-in used a client_id that differs from GOOGLE_OAUTH_CLIENT_ID; check that NEXT_PUBLIC_GOOGLE_CLIENT_ID holds the same value`.

**Now the rate limit.** A Google sign-in shares allauth's `login` limit: 30 a minute per IP. Every
attempt counts, valid or not, and it is the same bucket as your password logins, so start it with a
quiet minute (nothing else logging in). Run it in the same window as the block above (it uses `$h`,
`$url`, `$cid` and `mk` from there):

```powershell
mk $cid 'not-a-jwt' | Set-Content -Encoding ascii $env:TEMP\rz-google.json
1..31 | ForEach-Object { curl.exe -s -o NUL -w '%{http_code}\n' @h -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-google.json" $url } | Group-Object | ForEach-Object { '{0,7} {1}' -f $_.Count, $_.Name }
curl.exe -s -w ' %{http_code}\n' @h -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-google.json" $url
```

**You should see:**

```text
     30 400
      1 429
{"status": 429} 429
```

That is 30 refusals, then the 31st and every later request refused for the minute (`429`). (If you
logged in or tried Google in the last minute, fewer than 30 come back `400` before the first `429`.)

**If it differs:** `curl: (7) Failed to connect` means window 1 isn't running `runserver`; `404` on
command 2 means the server still runs with no client ID (restart it as above).

#### Step 6: Look at the Google button in the browser

**Where:** Window 1 (restart the server **without** the override), window 3 (frontend), then the
Browser.

**What this does:** Starts both servers the normal way, so they read **your own** `backend\.env` and
`frontend\.env.local` (the same client ID in both; this step never prints it), then shows what the two
pages look like with and without a client ID.

Window 1 (`Ctrl+C` the server of step 5, then `Remove-Item Env:GOOGLE_OAUTH_CLIENT_ID`, then in
`backend\` with the venv active):

```powershell
python manage.py runserver
```

Window 3 (in `frontend\`):

```powershell
npm run dev
```

In the Browser:

| URL | You should see |
|---|---|
| http://localhost:3000/login | Under the "Welcome back" text: a white button, **Continue with Google** (Google's own button, with its colourful "G"), then a thin line with **or log in with email**, then the email and password form |
| http://localhost:3000/signup | The same button under "Create your account", then **or continue with email** and the form with the Turnstile box |

- At phone width (shrink the window to about 390 px, or use the browser's device toolbar) the button
  stays inside the card and the page doesn't scroll sideways.
- The button is Google's, not ours: its width follows the card (up to 400 px) and its text is always
  English.
- **Close the popup.** Type something in the email and password boxes, then click the Google button.
  A Google window opens ("Sign in with Google"). Close it without choosing an account. Nothing
  changes on the page: your typed text is still there, there is no error and nothing says "Signing in".
  Google gives a page no signal for a closed popup, so "nothing happens" is the correct behaviour.
- **Without a client ID the button is hidden.** Stop window 3 (`Ctrl+C`) and start the dev server from
  Node, which can pass an empty value:
  `node -e "require('child_process').spawnSync('npm', ['run', 'dev'], { stdio: 'inherit', shell: true, env: { ...process.env, NEXT_PUBLIC_GOOGLE_CLIENT_ID: '' } })"`.
  Reload both pages: no Google button and no "or" line, just the form. (The value is read when the dev
  server starts.) Stop it and run `npm run dev` again before step 7.

**If it differs:** if the button area stays empty, open the browser console: "The given client ID is
not found" means the ID in `frontend\.env.local` is wrong; "Not a valid origin for the client" means
`http://localhost:3000` isn't in the client's Authorized JavaScript origins yet (ENV_GUIDE §1.6; wait a
few minutes after adding it). If a red box says "Google sign-in couldn't load. Check your connection,
or use email.", the script `https://accounts.google.com/gsi/client` is blocked (ad blocker, offline).

#### Step 7: Sign up with Google (manual, needs a Google account)

**Where:** Browser, then window 2.

**What this does:** A brand-new person signs up with one click. The agent could not run this step.

1. Open http://localhost:3000/signup and click **Continue with Google**. In the popup choose a Google
   account whose address has **no account here yet**.
2. You should land on **/home** (or the page named in `?next=`), logged in. There is **no** yellow
   "Verify your email" banner, and the New post button is enabled: a Google address is already verified.
3. The side menu shows your handle, **`@` plus your Google first name in lowercase**: `@ada`, or `@ada_`
   and four digits when that name is taken, or `@member_` and six characters when the first name has
   no Latin letters. It is never made from your email address. The display name stays empty.
4. Reload the page: you stay logged in. Log out from the account menu.

Then, in window 2 (in `backend\`, venv active), look at what was created. (Django may first print
`12 objects imported automatically …`; that is not part of the answer.)

```powershell
python manage.py shell -c "from allauth.socialaccount.models import SocialAccount; a = SocialAccount.objects.filter(provider='google').select_related('user').order_by('-date_joined').first(); print(a.user.username, a.user.is_email_verified, a.user.has_usable_password(), repr(a.user.display_name), sorted(a.extra_data))"
```

**You should see** one line shaped like this (your own handle):

```text
ada True False '' ['email', 'email_verified', 'sub']
```

That reads: the generated handle, email verified, **no usable password** (a Google-only account; it can
still set one with "Forgot password?"), a blank display name, and only these Google claims kept
(`hd` appears too for a Workspace address). Your name and picture are not stored.

Finally, log in again: open http://localhost:3000/login, click **Continue with Google** and choose the
same account. You land on /home again, and no second account was made:

```powershell
python manage.py shell -c "from allauth.socialaccount.models import SocialAccount; from apps.accounts.models import User; print(SocialAccount.objects.count(), User.objects.count())"
```

The two numbers are the same as before the second login.

**If it differs:** a red banner under the heading says what happened:
"Google sign-in didn't work. Try again." (the server refused the token: see below),
"Your Google account's email address isn't verified…", or "Too many attempts…" (the 30-a-minute limit).
For "didn't work", `runserver` only logs a `Bad Request: …/provider/token` line, so check, in order:
that `GOOGLE_OAUTH_CLIENT_ID` in `backend\.env` and `NEXT_PUBLIC_GOOGLE_CLIENT_ID` in
`frontend\.env.local` are the **same** value (a mismatch makes window 1 print the WARNING from
step 5); that the computer's clock is right (Settings → Time & language → Date & time → "Sync now": a
clock that is even a little behind Google's makes the token "issued in the future" and is refused);
that `runserver` was restarted after you edited `backend\.env`; and that the dev server was restarted
after you edited `frontend\.env.local`.

#### Step 8: Google with an address that already has an account (manual, needs a Gmail address)

**Where:** Browser, then window 2.

**What this does:** Checks that a Google sign-in lands in the **same** account as an email and
password sign-up with the same Gmail address, and that the password is locked, which is how someone who
signed up with *your* address without owning it is locked out. The agent could not run this step.

Use a Gmail (`@gmail.com`) address that has no account here yet. If you already used yours in step 7,
use a second Google account, or first delete that user in Django Admin
(http://localhost:8000/admin/accounts/user/, which also deletes its Google link).

1. Open http://localhost:3000/signup and make an **email and password** account with that Gmail
   address (any username and password; Turnstile uses the test key). You land on /verify-email. **Do
   not open the email link**: the account must stay unverified.
2. Log out, open http://localhost:3000/login and click **Continue with Google**, choosing that Gmail
   account.
3. You land on /home logged in, as the **username you chose in step 1** (not a generated one), and the
   "Verify your email" banner is gone.
4. Log out and try the **password** you chose in step 1 on /login: it says "That email and password
   don't match." Google proved you own the address, so the unverified account's password was wiped. To
   get a password back use **Forgot password?** (the link goes to your real inbox).

Check it in window 2:

```powershell
python manage.py shell -c "from allauth.socialaccount.models import SocialAccount; a = SocialAccount.objects.filter(provider='google').select_related('user').order_by('-date_joined').first(); print(a.user.username, a.user.is_email_verified, a.user.has_usable_password())"
```

**You should see** the username from step 1, then `True False`.

- Two more rules (`docs/ARCHITECTURE.md` §7; both covered by step 2's tests):
  - Only addresses Google itself hosts link to an existing account: `@gmail.com`, or a Google
    Workspace domain. Any other address (say `you@example.org`) that matches an existing account gets
    "An account with this email already exists. Log in with your password.", because Google can't
    vouch for who owns such an address today. A *new* person with that address can still sign up.
  - **Staff accounts** (moderators and superusers) are never linked by email: "Staff accounts log in
    with their password." If your own superuser has a Gmail address you can see this: click
    Continue with Google with it and expect the red banner.

#### Step 9: Stop and clean up

**Where:** Every terminal window, plus the browser.

- Stop the servers: `Ctrl+C` in windows 1 and 3 (leftover `next dev`: step 12 of Part 1).
- Delete the helper file:

  ```powershell
  Remove-Item $env:TEMP\rz-google.json
  ```

- The accounts from steps 7 and 8, and any `part…`/E2E ones, stay in your local database. Delete the
  Google ones in Django Admin → **Users** (their Google links go with them; **Social accounts** lists
  them). Nothing else was created: Part 3 stores no tokens and no Google profile data.
- `docker compose down` (repo root) stops the containers and keeps the data; `docker compose down -v`
  wipes the whole local database, which is destructive.
- Real Google data never goes into git: the client ID stays in your own `.env` files (it is public by
  design), and there is no client secret anywhere.

### Part 4: Posts (composer + Recent feed)

Needs Part 0A's containers and virtualenv, Part 0C's frontend, and your own `backend\.env` and
`frontend\.env.local`. Part 4 adds one migration (`posts.0001_initial`), one pinned dependency
(`idna==3.20`, which was already installed through `requests`, so `pip install` says "Requirement
already satisfied") and no env variable.

**Which terminal window for what.** Open the windows once and keep using the same ones:

| Window | What runs in it | Used in steps |
|---|---|---|
| Window 1 (server) | `python manage.py runserver` in `backend\`, venv active. Leave it running. Start it in step 4, **after** step 3 (Playwright starts its own servers and needs ports 3000 and 8000 free). | 4 to 14 |
| Window 2 (commands) | All the `curl.exe` and `python manage.py` commands. **Use the same window for steps 4 to 9**: the variables and functions you set in step 4 (`$id`, `$h`, `$ada`, `$bo`, `$cy`, `$api`, `Signup`, `Post`) only live in that one PowerShell window. If you close it, redo step 4. | 1 to 11, 15 |
| Window 3 (frontend) | `npm run dev` in `frontend\`. Leave it running. | 13 and 14 |
| Browser | Steps 12 to 14 | 12 to 14 |

Things to know first:

- Steps 4 to 10 talk to the API directly with `curl.exe` (with `.exe`: in PowerShell 5.1 plain `curl` is a
  different command). Steps 12 to 14 use the browser. Step 4 makes three accounts: `ada` for the API steps (step 8 uses up her whole fact
  allowance), `bo` (unverified) and `cy`, who stays untouched for the browser steps.
- **The PowerShell blocks below were not run on Windows.** The agent works on the Linux PC; it ran the bash
  twin of every command in the Linux guide on 2026-10-08, and the outputs below are those, reshaped to what
  `ConvertTo-Json -Compress` and `-join` print. The PowerShell commands follow the patterns Parts 1 to 3
  proved on Windows (JSON written to a file and sent with `--data-binary "@file"`, `curl.exe`, no `&&`). If
  one behaves differently, tell the agent which. The browser steps were checked the same day with headless
  Chromium (screenshots at 1280 and 390 px), not by a person at a keyboard. Numbers in names, times and
  token prefixes differ on every run.
- **The fact allowance comes from your own settings.** `FACT_POSTS_PER_DAY` in `backend\.env` (the
  example file says 10) seeds it, and Django Admin → Platform settings changes it. Step 8 reads the
  number from the server, so it works with any value of 1 or more; the sample output uses 10. It is a
  **rolling 24 hours**, not a calendar day.
- A post is limited to 30 per hour per account (`post_create`). Steps 5 to 9 use about 25 of them
  (refused attempts count). If you repeat steps 6 to 8 within an hour, make new accounts (step 4 again)
  or you will see `429 throttled` instead.
- Nothing here sends an email: step 4 marks two accounts verified with a shell command, which stands in
  for clicking the link (Part 2 shows the real flow).

#### Step 1: Apply the migration and check the schema

**Where:** Terminal window 2 (commands), starting in the repo root.

**What this does:** Starts the database containers, activates the Python environment, installs what
`requirements.txt` pins, creates the `posts` table and counts its database rules.

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero
docker compose up -d
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt 2>&1 | Select-String idna       # Requirement already satisfied: idna==3.20 …
python manage.py migrate                                   # first time: "Applying posts.0001_initial... OK"
python manage.py check                                     # System check identified no issues (0 silenced).
python manage.py makemigrations --check --dry-run          # No changes detected
python manage.py showmigrations posts
python manage.py shell -c "from django.db import connection as c; cur = c.cursor(); k = c.introspection.get_constraints(cur, 'posts_post'); print(len([n for n, v in k.items() if v['check']]), 'checks;', sorted(n for n in k if n.endswith('_idx')))" | Select-Object -Last 1
```

**You should see:** the first `migrate` after pulling Part 4 prints `Applying posts.0001_initial... OK`
(a database that already has it says `No migrations to apply.`). The two checks print their messages,
`showmigrations` prints `[X] 0001_initial`, and the last line is:

```text
19 checks; ['posts_author_created_idx', 'posts_pending_queue_idx', 'posts_pinned_emerg_idx', 'posts_recent_idx', 'posts_review_queue_idx', 'posts_status_created_idx']
```

- The 19 checks are our 17 rules (content length, every status and type, "an opinion can't carry a
  fact status", "a fact can't be `published`", at most 5 sources, no sources on an opinion, no empty or
  NULL source, no emergency opinion, the emergency expiry, the confidence range) plus Django's own two
  "not negative" checks on the two counters.
- `posts_recent_idx` is the one index that is not in the original data model: Recent lists every status
  except `removed`, which `(status, created_at)` can't serve.

#### Step 2: Run the automated backend checks

**Where:** Same terminal as step 1 (window 2, in `backend\`, venv active).

**What this does:** Runs the whole backend test suite, then only the new posts tests, then the linter and
formatter check.

```powershell
python -m pytest                                    # 1087 passed
python -m pytest apps/posts -q                      # 383 passed
ruff check . ; ruff format --check .                # All checks passed! / 103 files already formatted
```

**You should see:** the full run ends with `1087 passed`, the second command with `383 passed`, and the
last prints `All checks passed!` and `103 files already formatted`. (Counts may grow later; what matters
is that nothing fails.)

- The 383 are spread over: `test_models.py` (69: one test per database rule, which constraint fired,
  and the indexes), `test_validators.py` (195: the shared source vectors plus the codes and messages),
  `test_services.py` (24: status by type, the rolling quota to the microsecond, and two simultaneous
  fact posts at 9 of 10, which let exactly one through, plus a control run without the lock that lets
  both through), `test_api_create.py` (41), `test_api_feed.py` (25: ordering, exclusions, no repeats or
  skips when posts arrive between pages, a crafted cursor, query counts), `test_api_quota.py` (7),
  `test_emergency.py` (14), `test_no_network.py` (4) and `test_admin.py` (4).
- `apps/accounts/tests/test_tokens.py` changed too: its `run_together` helper moved to that folder's
  `conftest.py` so the posts tests can share it.

#### Step 3: Run the automated frontend checks

**Where:** Terminal window 2, then `cd ..\frontend`. Playwright (the last two commands) starts Django and
Next itself, so **no servers may be running on ports 3000 and 8000** (it reuses them if they are, with
whatever settings they have).

**What this does:** Runs the linters, the type check, the component tests, the production build and the
end-to-end tests.

```powershell
cd ..\frontend                                      # from backend\
npm run lint ; npm run lint:tokens ; npm run typecheck ; npm run format:check
npm test                                            # 80 files, 1089 tests passed
npm run build
npm run test:e2e                                    # 20 passed
$env:CI = "1" ; npm run test:e2e ; Remove-Item Env:CI   # 20 passed (against the production build)
cd ..\backend                                       # back to backend\ for steps 4 to 11
```

**You should see:** the first line prints nothing from ESLint and TypeScript and ends with
`lint:tokens OK (…)` and `All matched files use Prettier code style!`. `npm test` ends with
`Test Files  80 passed (80)` and `Tests  1089 passed (1089)`. `npm run build` lists the routes as in Part 3
(`/home` is still `○`: the page is static, and the feed loads in the browser). Each E2E run ends with
`20 passed`: the 15 earlier tests and 5 new ones in `e2e/posts.spec.ts`.

- The E2E tests sign up their own accounts and verify them through the file mailbox, then: post a fact
  with a DOI and a URL (CHECKING FACTS… and "doi.org/… +1 more", the allowance down by one, still there
  after a reload and visible to a visitor), post an opinion (OPINION in italic, no source line), check
  that a bad post is blocked on the page before anything is sent, check an unverified account can read but
  not post, and check the composer at phone width.
- On Windows `npm run build` can't blank `NEXT_PUBLIC_GOOGLE_CLIENT_ID` (PowerShell's `$env:NAME = ""` *deletes* the
  variable), so a `frontend\.env.local` with your real client ID is baked into that build and the CI-mode run is less
  representative than on Linux. The default run pins an empty client ID for both servers, so it is unaffected.

#### Step 4: Start the server and make two accounts

**Where:** First window 1 (start the server), then window 2 (the commands). **Keep using window 2 for
steps 5 to 9.**

**What this does:** Window 1 runs the Django server. In window 2 you sign up three accounts through the
API: `ada` and `cy`, which you mark verified with a shell command (it stands in for the email link), and
`bo`, who stays unverified.

Window 1 (in `backend\`, venv active):

```powershell
python manage.py runserver                          # leave it running
```

Window 2 (in `backend\` with the venv active: steps 1 to 3 leave you there). If you opened a new window,
first run `cd C:\Users\Nafis\Downloads\Rumor-Zero\backend` and `.\.venv\Scripts\Activate.ps1`:

```powershell
$id = Get-Date -Format "HHmmss"                     # a unique suffix so the addresses are new each run
$h = '-H', 'Origin: http://localhost:3000', '-H', 'X-Requested-With: rumor-zero'   # headers every auth call needs
function Signup($email, $username) {
@"
{"email": "$email", "username": "$username", "password": "correct-horse-battery-42", "turnstile_token": "XXXX.DUMMY.TOKEN.XXXX"}
"@ | Set-Content -Encoding ascii $env:TEMP\rz-signup.json
  (curl.exe -s @h -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-signup.json" http://localhost:8000/api/auth/app/v1/auth/signup | ConvertFrom-Json).meta.access_token
}
$ada = Signup "part4-ada-$id@example.test" "part4_ada_$id"      # $ada = ada's login token
$bo = Signup "part4-bo-$id@example.test" "part4_bo_$id"         # $bo = bo's login token
$cy = Signup "part4-cy-$id@example.test" "part4_cy_$id"         # $cy = cy's login token (kept for the browser)
python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(email__in=['part4-ada-$id@example.test', 'part4-cy-$id@example.test']).update(is_email_verified=True), 'accounts marked verified')" | Select-Object -Last 1
foreach ($t in $ada, $bo, $cy) { curl.exe -s -H "Authorization: Bearer $t" http://localhost:8000/api/v1/me/ | ConvertFrom-Json | Select-Object username, is_email_verified | ConvertTo-Json -Compress }
$api = 'http://localhost:8000/api/v1'
# Post <token> <json> [fields]: prints the HTTP status, then the answer (cut down to `fields` when given)
function Post($token, $json, $props) {
  $json | Set-Content -Encoding ascii $env:TEMP\rz-post.json
  $out = curl.exe -s -w "`n%{http_code}" -H "Authorization: Bearer $token" -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-post.json" "$api/posts/"
  $body = $out[0..($out.Count - 2)] -join ''
  if ($props) { $body = $body | ConvertFrom-Json | Select-Object $props | ConvertTo-Json -Depth 5 -Compress }
  "$($out[-1])  $body"
}
```

Sanity check (this step sets `$id`, `$ada`, `$bo`, `$cy`, `$api` and `Post`; the tokens must not be empty):

```powershell
"$($ada.Substring(0,10)) $($bo.Substring(0,10)) $($cy.Substring(0,10))"      # three prefixes, not an error
```

**You should see** (the number in the names is your `id`, so it differs):

```text
2 accounts marked verified
{"username":"part4_ada_235103","is_email_verified":true}
{"username":"part4_bo_235103","is_email_verified":false}
{"username":"part4_cy_235103","is_email_verified":true}
```

and, from the sanity check, `eyJhbGciOi eyJhbGciOi eyJhbGciOi` (every token of this kind starts that way).

- `Post` is a helper for the next steps: it sends a JSON body with a login token, prints the HTTP status,
  then the answer (optionally cut down to the fields you name).
- The shell prints a line about auto-imported objects first; `Select-Object -Last 1` keeps only ours.
- Sign-up is limited to 20 a minute per address (Part 1), and still calls Cloudflare's test widget, so it
  needs internet.

**If it differs:** empty tokens mean the sign-up failed: `runserver` isn't running, or you signed up more than 20 times in a minute. Fix that and run this step again from
`$id = Get-Date …`.

#### Step 5: Who may post

**Where:** Terminal window 2 (the same terminal as step 4).

**What this does:** Tries to post as nobody, as the unverified account, and reads the feed with no login.
Posting needs a **verified email**; reading doesn't.

```powershell
'{"content":"hi","post_type":"opinion"}' | Set-Content -Encoding ascii $env:TEMP\rz-post.json
curl.exe -s -w '  %{http_code}\n' -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-post.json" "$api/posts/"   # 1: nobody
Post $bo '{"content":"hi","post_type":"opinion"}'                                                                   # 2: unverified
curl.exe -s -o NUL -w '%{http_code}\n' "$api/posts/"                                                                 # 3: the feed, no login
curl.exe -s -o NUL -w '%{http_code}\n' -H "Authorization: Bearer $bo" "$api/me/fact-quota/"                          # 4: the allowance, unverified
```

**You should see** (four commands, four answers):

```text
{"detail":"Authentication credentials were not provided.","code":"not_authenticated"}  401
403  {"detail":"Verify your email address first. Check your inbox for the link.","code":"email_unverified"}
200
200
```

- 401 means "log in first", 403 `email_unverified` means "logged in but not verified". Reading the feed
  needs nothing. Asking for your allowance needs a login only, so the composer can show it.

#### Step 6: Post an opinion and a fact

**Where:** Terminal window 2.

**What this does:** Posts as `ada` (verified) and shows what the server stored. An opinion is
`published` at once; a fact is `pending` ("Checking facts…") because the fact-check pipeline arrives in
Part 9. Sources are normalised, never fetched.

```powershell
Post $ada '{"content":"I think the new tram line will change how the city moves.","post_type":"opinion"}' 'status','post_type','sources','is_mine','confidence_score','emergency_active'
Post $ada '{"content":"Solar capacity grew by roughly 30% worldwide last year.","post_type":"fact","sources":["doi:10.1038/s41558-024-02102","HTTPS://www.IEA.org/reports/renewables-2023"]}' 'status','post_type','sources',@{n='author';e={$_.author.username}}
Post $ada '{"content":"  Water boils at 100C at sea level.  ","post_type":"fact"}' 'status','content','sources'
Post $ada '{"content":"Opinion with a bad idea","post_type":"opinion","status":"verified_true","confidence_score":"99.00"}' 'status','confidence_score'
Post $ada '{"content":"Hosts are folded to punycode","post_type":"fact","sources":["https://b\u00fccher.example/\u00fcber?q=1","https://fa\u00df.de:443/x"]}' 'sources'
```

**You should see** (five commands; `201` is "created"):

```text
201  {"status":"published","post_type":"opinion","sources":[],"is_mine":true,"confidence_score":null,"emergency_active":false}
201  {"status":"pending","post_type":"fact","sources":[{"value":"10.1038/s41558-024-02102","kind":"doi"},{"value":"https://www.iea.org/reports/renewables-2023","kind":"url"}],"author":"part4_ada_235103"}
201  {"status":"pending","content":"Water boils at 100C at sea level.","sources":[]}
201  {"status":"published","confidence_score":null}
201  {"sources":[{"value":"https://xn--bcher-kva.example/%C3%BCber?q=1","kind":"url"},{"value":"https://xn--fa-hia.de/x","kind":"url"}]}
```

- **Line 2:** `doi:10.1038/…` is stored as the bare DOI `10.1038/s41558-024-02102` with kind `doi`; the second
  source's scheme and host are lower-cased (`HTTPS://www.IEA.org/…` → `https://www.iea.org/…`). The
  order you gave is the order kept.
- **Line 3:** the text is trimmed. A fact with no sources is fine (sources are optional).
- **Line 4:** `status` and `confidence_score` in the request are ignored: only the server sets them.
- **Line 5:** `bücher.example` and `faß.de` become punycode, the way a browser opens them (`faß.de` is
  `xn--fa-hia.de`, not the `fass.de` of the old IDNA 2003 rules), the `ü` in the path is percent-encoded,
  and the default port `:443` is dropped.
- No source is ever visited by the server. Step 11 runs the test that blocks the network to prove it.

#### Step 7: See what the server refuses

**Where:** Terminal window 2.

**What this does:** Sends eight bad posts. Each answer says which field is wrong; nothing is saved.

```powershell
Post $ada '{"content":"No type"}'
Post $ada '{"content":"   ","post_type":"opinion"}'
Post $ada ('{"content":"' + ('x' * 501) + '","post_type":"opinion"}')
Post $ada '{"content":"Only facts have sources","post_type":"opinion","sources":["10.1000/xyz"]}'
Post $ada '{"content":"Bad sources","post_type":"fact","sources":["10.1000/ok","javascript:alert(1)","http://127.0.0.1/admin","https://user:pw@example.org/"]}'
Post $ada '{"content":"Repeats","post_type":"fact","sources":["doi:10.1000/xyz","https://doi.org/10.1000/XYZ"]}'
Post $ada '{"content":"Too many","post_type":"fact","sources":["10.1000/a","10.1000/b","10.1000/c","10.1000/d","10.1000/e","javascript:x"]}'
Post $ada '{"content":"Emergency","post_type":"fact","is_emergency":true}'
```

**You should see** (eight commands, eight answers, all `400`):

```text
400  {"post_type":["Choose Opinion or Fact."]}
400  {"content":["Write something first."]}
400  {"content":["Keep it to 500 characters."]}
400  {"sources":["Only fact posts can have sources."]}
400  {"sources":{"1":["Enter a link that starts with https:// or http://, or a DOI such as 10.1000/xyz."],"2":["Links to IP addresses and localhost aren't allowed."],"3":["Links with a username or password aren't allowed."]}}
400  {"sources":{"1":["Same as source 1."]}}
400  {"sources":["You can add up to 5 sources."]}
400  {"detail":"Emergency posts aren't available yet.","code":"emergency_unavailable"}
```

- **Line 5:** the numbers are the position in your list (0 is the first): sources 1, 2 and 3 are wrong,
  all reported at once, and the good first one doesn't save the post.
- **Line 6:** `doi:10.1000/xyz` and `https://doi.org/10.1000/XYZ` are the same DOI (DOIs ignore case), so the
  later one is the repeat.
- **Line 7:** six sources are refused with only the list message, even though one of them is also bad.
- **Line 8:** emergency posts are Part 11C; until then the flag is refused.

#### Step 8: The fact allowance

**Where:** Terminal window 2.

**What this does:** Reads how many fact posts `ada` may still make in the last 24 hours, uses them all,
and shows the refusal. Each fact post counts for 24 hours, even if it is deleted or removed later, so
deleting and reposting can't get around the limit. Opinions never count.

```powershell
curl.exe -s -H "Authorization: Bearer $ada" "$api/me/fact-quota/"
$left = (curl.exe -s -H "Authorization: Bearer $ada" "$api/me/fact-quota/" | ConvertFrom-Json).remaining
"posting $left more facts"
1..$left | ForEach-Object { Post $ada ('{"content":"Quota claim N","post_type":"fact"}'.Replace('N', "$_")) 'status' }
curl.exe -s -H "Authorization: Bearer $ada" "$api/me/fact-quota/"
'{"content":"One too many","post_type":"fact"}' | Set-Content -Encoding ascii $env:TEMP\rz-post.json
curl.exe -s -i -H "Authorization: Bearer $ada" -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-post.json" "$api/posts/" | Select-String -Pattern '^HTTP|^Retry-After|^\{'
Post $ada '{"content":"Opinions are not limited","post_type":"opinion"}' 'status'
```

**You should see** (with a limit of 10; the times and `Retry-After` differ):

```text
{"limit":10,"used":3,"remaining":7,"window_hours":24,"next_slot_at":null}
posting 7 more facts
201  {"status":"pending"}
201  {"status":"pending"}
201  {"status":"pending"}
201  {"status":"pending"}
201  {"status":"pending"}
201  {"status":"pending"}
201  {"status":"pending"}
{"limit":10,"used":10,"remaining":0,"window_hours":24,"next_slot_at":"2026-10-09T17:51:04.118320Z"}
HTTP/1.1 429 Too Many Requests
Retry-After: 86382
{"detail":"You've used all 10 of your fact posts for the last 24 hours. You can post another at 17:51 UTC.","code":"fact_quota_exceeded"}
201  {"status":"published"}
```

- `used` was 3 because steps 6 and 7 made three fact posts. When nothing is left, `next_slot_at` is the
  moment the oldest counted post is 24 hours old: the composer shows it as "next at 5:51 PM" in your own
  time zone.
- The refusal is **429 `fact_quota_exceeded`** with a `Retry-After` in seconds (about 24 hours here). It
  is a different 429 from `throttled`, so the page can tell "you've used your allowance" from "you're
  posting too fast". An allowance of 0 (Django Admin → Platform settings) answers **403
  `fact_posts_paused`** instead.

#### Step 9: The Recent feed and its cursor

**Where:** Terminal window 2.

**What this does:** Reads the public feed (no login), pages through it three posts at a time and tries a
fake cursor.

```powershell
$f = curl.exe -s "$api/posts/?page_size=3" | ConvertFrom-Json
"pinned: $($f.pinned.Count), pinned_total: $($f.pinned_total), kinds: $($f.results.kind -join ','), has_next: $([bool]$f.next_cursor)"
$f.results.post.content -join ' | '
$c = $f.next_cursor
$f2 = curl.exe -s "$api/posts/?page_size=3&cursor=$c" | ConvertFrom-Json
"$($f2.results.post.content -join ' | '), has_next: $([bool]$f2.next_cursor)"
curl.exe -s -w '  %{http_code}\n' "$api/posts/?cursor=not-a-cursor"
curl.exe -s -w '  %{http_code}\n' "$api/posts/?cursor=cD1nYXJiYWdl"
$mine = (curl.exe -s -H "Authorization: Bearer $ada" "$api/posts/?page_size=1" | ConvertFrom-Json).results[0].post
"is_mine: $($mine.is_mine), keys: $(($mine | Get-Member -MemberType NoteProperty).Count)"
$theirs = (curl.exe -s "$api/posts/?page_size=1" | ConvertFrom-Json).results[0].post
"is_mine: $($theirs.is_mine), keys: $(($theirs | Get-Member -MemberType NoteProperty).Count)"
```

**You should see:**

```text
pinned: 0, pinned_total: 0, kinds: post,post,post, has_next: True
Opinions are not limited | Quota claim 7 | Quota claim 6
Quota claim 5 | Quota claim 4 | Quota claim 3, has_next: True
{"detail":"Invalid cursor","code":"not_found"}  404
{"detail":"Invalid cursor","code":"not_found"}  404
is_mine: True, keys: 23
is_mine: False, keys: 23
```

- Newest first. `pinned` is empty until emergency posts (Part 11C), and Recent only has `post` items
  (reposts are Part 7B).
- The next page starts exactly where the last one ended: a post made between two page loads never
  repeats or skips a post (the automated tests make 5 new posts between pages 1 and 2).
- `cD1nYXJiYWdl` is the base64 of `p=garbage`, a hand-made cursor. It is a clean **404**, not a server
  error.
- Every post has the same 23 fields; `is_mine` depends on who is asking. The feed has no counts yet (likes,
  comments and reposts arrive in Parts 7 and 7B), so those fields are 0 or false.

#### Step 10: The database refuses bad rows

**Where:** Terminal window 2, in `backend\` with the venv active.

**What this does:** Tries to write six impossible posts straight into the database, skipping the API.
The database itself must refuse each one, and say which rule stopped it. Every attempt is rolled back.

```powershell
$py = @"
from django.db import IntegrityError, transaction
from django.utils import timezone
from apps.accounts.models import User
from apps.posts.models import Post
user = User.objects.get(email='part4-ada-$id@example.test')
cases = {
    'an opinion with a source': dict(post_type='opinion', status='published', sources=['10.1000/xyz']),
    'an opinion that is verified': dict(post_type='opinion', status='verified_true'),
    'a published fact': dict(post_type='fact', status='published'),
    'six sources': dict(post_type='fact', status='pending', sources=['10.1/a','10.1/b','10.1/c','10.1/d','10.1/e','10.1/f']),
    'an empty source': dict(post_type='fact', status='pending', sources=['']),
    'an emergency opinion': dict(post_type='opinion', status='published', is_emergency=True, emergency_expires_at=timezone.now()),
}
for name, fields in cases.items():
    try:
        with transaction.atomic():
            Post.objects.create(author=user, content='x', **fields)
    except IntegrityError as error:
        print(name + ' ->', error.__cause__.diag.constraint_name)
print(Post.objects.filter(content='x').count(), 'rows written')
"@
$py | Set-Content -Encoding ascii $env:TEMP\rz-db.py
python manage.py shell -c (Get-Content -Raw $env:TEMP\rz-db.py) | Select-Object -Last 7
```

**You should see:**

```text
an opinion with a source -> posts_post_sources_fact_only
an opinion that is verified -> posts_post_opinion_status
a published fact -> posts_post_fact_not_published
six sources -> posts_post_sources_max
an empty source -> posts_post_sources_not_empty
an emergency opinion -> posts_post_emergency_fact_only
0 rows written
```

- Each line is the name of the database rule that fired. `0 rows written` confirms nothing got through.
- One more rule the database can't state: a source over 500 characters. Postgres would *truncate* it
  silently through Django's cast, so `validators.normalize_source` refuses it first (step 7's tests cover
  499, 500 and 501 characters).

#### Step 11: No source is ever fetched

**Where:** Terminal window 2, in `backend\` with the venv active.

**What this does:** Runs the test that blocks every way Python can reach the network (sockets, DNS,
`urllib`, `requests`, `http.client`), then posts a fact with five kinds of source. It must still work,
because the server only validates and stores a link.

```powershell
python -m pytest apps/posts/tests/test_no_network.py -v 2>&1 | Select-String -Pattern 'PASSED|passed|FAILED'
```

**You should see:**

```text
apps/posts/tests/test_no_network.py::test_creating_a_post_with_sources_makes_no_network_request PASSED [ 25%]
apps/posts/tests/test_no_network.py::test_a_refused_source_makes_no_request_either PASSED [ 50%]
apps/posts/tests/test_no_network.py::test_the_blocker_really_blocks PASSED [ 75%]
apps/posts/tests/test_no_network.py::test_the_posts_code_imports_nothing_that_can_fetch PASSED [100%]
============================== 4 passed in 0.41s ===============================
```

- The last test also reads every file in `apps/posts/` and fails if one imports a library that can fetch.
  This is what keeps a user's link from ever becoming a request from our server.

#### Step 12: Django Admin shows the posts, read-only

**Where:** Browser, while `runserver` is running in window 1.

**What this does:** Opens the admin list of posts. Part 10 adds the moderator actions; until then nobody can
change a post from here, so nothing can skip the rules the API enforces.

| URL | Expect |
|---|---|
| http://localhost:8000/admin/ | Sign in with the superuser you made in Part 0A (email and password). If it 404s, `ADMIN_URL_PATH` in `backend\.env` isn't `admin/`; use that path. |
| http://localhost:8000/admin/posts/post/ | The posts, newest first, with columns Post, Post type, Status, Author, Created at and Deleted at, a filter panel (type, status) and a search box (text or username). **No "Add post" button.** |
| Search `tram` or `Quota` | Only the matching posts (the opinion about the tram line, or the seven "Quota claim" facts) |
| Open one post | Its fields are shown but not editable, and there are no Save buttons or Delete button |

- The same rules are checked by the automated tests (add, change and delete are refused with 403).

#### Step 13: The composer and the Recent feed in the browser

**Where:** First window 3 (start the frontend), then the browser. Window 1 must still be running `runserver`.

**What this does:** Starts the Next.js dev server and uses the composer as `cy` (verified, with a full
allowance) and `bo` (unverified).

Window 3:

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero\frontend
npm run dev                                         # leave it running
```

Browser. Log in at http://localhost:3000/login as **`cy`**, with `part4-cy-<your id>@example.test` and
`correct-horse-battery-42` (the id from step 4), then:

| Do this | Expect |
|---|---|
| Open http://localhost:3000/home | A white column titled by the **RECENT** tab (blue underline), then a card that looks like a text box: a pencil tile, "What do you want to say?" and a blue **New post** pill. Below it, the posts from steps 6 to 9, newest first. |
| Look at a fact card | A grey **FACT** chip and a dashed **CHECKING FACTS…** chip with a spinning glyph, the claim in upright serif, and under it one row with a link glyph: `doi.org/10.1038/s41558-024-02102 ↗` and `+1 more`. The left edge stripe is a pale grey-green. |
| Look at an opinion card | A grey **OPINION** chip only (no status chip), the text in *italic* serif, and no source row. |
| Click the card (or the rail's blue **New post**) | A dialog **New post** with the cursor in the text. Under the text: `0 / 500 characters`. Then "Post type  Choose one to continue", a pill with **Opinion** and **Fact** (neither selected), and a footer: `10/10 fact posts left` (your limit), **Cancel** and **Post**. |
| Click **Post** with nothing typed | Nothing is sent. Under the text: "Write something first." Under the choice: "Choose Opinion or Fact." The cursor goes back to the text. |
| Type a sentence and click **Fact** | A **Source (URL or DOI) (optional)** group appears with one field, "DOI preferred" (teal, top right) and **+ Add another source**. The button now says **Post fact, will be checked**. The hint beside "Post type" says "Fact posts are checked after you post". |
| Click **Opinion** | The source group disappears (your text stays) and the button says **Post opinion**. Click **Fact** again. |
| Type `http://127.0.0.1/admin` in the field and press Tab | The field turns red: "Links to IP addresses and localhost aren't allowed." |
| Replace it with `doi:10.1000/xyz`, click **Add another source** | The error goes; a second field appears with the cursor in it and a **×** to its right. Add up to five fields in total, then the add button disappears. |
| Type `https://doi.org/10.1000/XYZ` in the second field and click **Post fact…** | The second field turns red: "Same as source 1." Nothing is sent. Change it to `https://example.org/report`. |
| Click **Post fact, will be checked** | The button shows **Posting…**, then the dialog closes, a dark toast says **Posted. Checking the facts…**, and your post is at the top of the feed with **CHECKING FACTS…** and `doi.org/10.1000/xyz` `+1 more`. The page did not reload. |
| Open the composer again | The text is empty again, and the footer says one fact post fewer (`9/10 …`). |
| Type something, press **Esc**, open the composer again | Your text is still there: closing keeps the draft. |
| Reload the page | The posts come back from the server, in the same order. |

- Not in the table, but covered by the automated tests: pasting more than 500 characters (the counter turns
  red and "Keep it to 500 characters." appears on **Post**; an emoji counts as one character, as on the
  server), the allowance reaching 0 (the footer shows `0/10 fact posts left · next at 5:51 PM` and a fact is
  refused on the page without sending anything; `ada`, whose allowance step 8 used up, shows exactly
  that), and closing the dialog while a post is still being sent.
- Log in as `bo` (a private window): the card and the rail's **New post** are greyed out; clicking either
  shows the toast "Verify your email to post. Check your inbox, or resend the link from the banner." and
  opens nothing. The feed still loads.
- Log out and open http://localhost:3000/home: the card says "Log in to share an opinion or a fact." with a
  blue **Log in to post** link, and the feed is the same.

#### Step 14: A phone-sized window

**Where:** Browser, logged in as `cy`.

**What this does:** Checks the same screens at phone width. In Firefox or Chrome press `F12`, then the
"responsive design" / device toolbar button, and set the width to 390.

| Do this | Expect |
|---|---|
| Open http://localhost:3000/home | A top bar with the logo and your avatar, the Recent tab, the card (placeholder "What do you want to say?" in full, no blue pill), the posts and a bottom bar (Home, Search, New post, Notifications, Profile). No sideways scrolling. |
| Look at a post's header | The author's name sits on one line (long names get "…"); the FACT and status chips wrap onto a line of their own under it. |
| Tap **New post** in the bottom bar | The same dialog, almost full width. Pick **Fact**, add sources up to five: each row keeps its **×**, long links scroll inside their field, and the page still doesn't scroll sideways. |
| Look at the footer | `9/10 fact posts left` (or `10/10` if you haven't posted yet) on its own line, with **Cancel** and the submit button below it (the long label may wrap onto two lines). |

#### Step 15: Stop and clean up

**Where:** Every terminal window, plus the browser.

- Stop the servers: `Ctrl+C` in windows 1 and 3 (a leftover `next dev`: step 12 of Part 1).
- Delete the test accounts and their posts (the posts go with them). In window 2, in `backend\` with the
  venv active:

  ```powershell
  python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(email__startswith='part4-').delete())" | Select-Object -Last 1
  ```

  After one clean run of this guide it prints `(19, {'posts.Post': 13, 'account.EmailAddress': 3,
  'accounts.User': 3})`: how many rows went in all, and per table (13 posts: 5 from step 6 and 8 from step 8;
  you get more if you made posts as `cy` or ran the guide twice). Nothing else is touched. (The E2E tests' accounts stay in your local database, as in
  earlier parts: Django Admin → Users deletes them.)
- `docker compose down` (repo root) stops the containers and keeps the data; `docker compose down -v`
  wipes the whole local database, which is destructive.
- No secret was used or printed in this part: the only values in the commands are Cloudflare's public test
  token and the throwaway password of the test accounts.

### Part 5: Post detail, sharing, deletion, status polling

Needs Part 0A's containers and virtualenv, Part 0C's frontend, and your own `backend\.env` and
`frontend\.env.local`. Part 5 adds **no migration, no dependency and no env variable**. It adds one throttle
scope (`status_poll`, in code) and three endpoints: `GET` and `DELETE /api/v1/posts/{id}/` and
`GET /api/v1/posts/status/`.

**Which terminal window for what.** Open the windows once and keep using the same ones:

| Window | What runs in it | Used in steps |
|---|---|---|
| Window 1 (server) | `python manage.py runserver` in `backend\`, venv active. Leave it running. Start it in step 3, **after** step 2 (Playwright starts its own servers and needs ports 3000 and 8000 free). | 3 to 13 |
| Window 2 (commands) | All the `curl.exe` and `python manage.py` commands. **Use the same window for steps 3 to 9**: the variables and functions you set in step 3 (`$id`, `$h`, `$ada`, `$bo`, `$cy`, `$api`, `$fact`, `$op`, `Signup`, `Mk`, `Fetch`) only live in that one terminal. If you close it, redo step 3. | 1 to 10, 14 |
| Window 3 (frontend) | `npm run dev` in `frontend\`. Leave it running. | 9 to 13 |
| Browser | Steps 10 to 13 | 10 to 13 |

Things to know first:

- Steps 3 to 9 talk to the API directly with `curl.exe` (with `.exe`: in PowerShell 5.1 plain `curl` is a
  different command). Steps 10 to 13 use the browser. Step 3 makes three accounts, all verified: `ada` writes the posts, `bo` is "another user", and
  `cy` stays untouched for the browser steps.
- **The PowerShell blocks below were not run on Windows.** The agent works on the Linux PC; it ran the bash
  twin of every command in the Linux guide on 2026-10-09, and the outputs below are those, reshaped to what
  `ConvertTo-Json -Compress`, `Group-Object` and `Select-String` print. The PowerShell commands follow the
  patterns Parts 1 to 4 proved on Windows (JSON written to a file and sent with `--data-binary "@file"`,
  `curl.exe`, no `&&`). If one behaves differently, tell the agent which. The API and page outputs were
  recorded on Linux on 2026-10-09. The browser steps were checked the same
  day with headless Chromium (screenshots at 1280 and 390 px), not by a person at a keyboard. Ids, numbers in
  names, times and token prefixes differ on every run.
- Nothing here sends an email: step 3 marks the accounts verified with a shell command, which stands in for
  clicking the link (Part 2 shows the real flow). Step 7 sets a post to `removed` the same way, because the
  moderator tools that do it for real arrive in Part 10.
- **Part 5 doesn't change any post's text or sources**; a post can only be deleted by its author, and "deleted"
  only hides it (the row stays, so a moderator can still find it).

#### Step 1: Run the automated backend checks

**Where:** Terminal window 2 (commands), starting in the repo root.

**What this does:** Starts the database containers, activates the Python environment, confirms there is no
new migration, then runs the whole backend test suite, the new posts tests, the linter and the formatter check.

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero
docker compose up -d
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py makemigrations --check --dry-run   # No changes detected
python manage.py check                              # System check identified no issues (0 silenced).
python -m pytest                                    # 1160 passed
python -m pytest apps/posts -q                      # 456 passed
ruff check . ; ruff format --check .                # All checks passed! / 106 files already formatted
```

**You should see:** `No changes detected` and `System check identified no issues (0 silenced).`, then the full
run ends with `1160 passed`, the posts run with `456 passed`, and the last line pair is `All checks passed!` and
`106 files already formatted`. (Counts may grow later; what matters is that nothing fails.)

- The 73 new posts tests: `test_api_detail.py` (33: who sees what in every status, the removed tombstone, 404s,
  query counts), `test_api_delete.py` (22: permissions, soft delete, two simultaneous deletes give one success
  and one 404, the row lock), `test_api_status.py` (17: the four-key shape, the 50-id cap, one query for 50
  posts, the 120-a-minute throttle) and one more in `test_models.py` (`not_deleted()`).
- `apps/core/tests/test_settings.py` now expects eleven throttle scopes (`status_poll` is the new one).

#### Step 2: Run the automated frontend checks

**Where:** Terminal window 2, then `cd ..\frontend`. Playwright (the last two commands) starts Django and
Next itself, so **no servers may be running on ports 3000 and 8000** (it reuses them if they are, with
whatever settings they have).

**What this does:** Runs the linters, the type check, the component tests, the production build and the
end-to-end tests.

```powershell
cd ..\frontend                                      # from backend\
npm run lint ; npm run lint:tokens ; npm run typecheck ; npm run format:check
npm test                                            # 91 files, 1210 tests passed
npm run build
npm run test:e2e                                    # 24 passed
$env:CI = "1" ; npm run test:e2e ; Remove-Item Env:CI   # 24 passed (against the production build)
cd ..\backend                                       # back to backend\ for steps 3 to 9
```

**You should see:** the first line prints nothing from ESLint and TypeScript and ends with
`lint:tokens OK (…)` and `All matched files use Prettier code style!`. `npm test` ends with
`Test Files  91 passed (91)` and `Tests  1210 passed (1210)`. `npm run build` lists the routes as in Part 4, plus
`ƒ /p/[id]` (dynamic: it is rendered on the server for each post). Each E2E run ends with `24 passed`: the 20
earlier tests and 4 new ones in `e2e/post-detail.spec.ts`.

- The new E2E tests sign up their own accounts, then: open a fact from its card (sources numbered `01`, `02`,
  Copy link, and an anonymous request for `/p/<id>` returning the claim, the `<title>` and the Open Graph tags);
  delete an opinion (gone from Recent, a 404 page and a 404 from the API); watch a pending fact turn into
  `VERIFIED 94%` on the feed and on its own page after a status change made in the database (about 10 to 15
  seconds); and check a removed post (a tombstone for a visitor, the full text for its author).
- On Windows `npm run build` can't blank `NEXT_PUBLIC_GOOGLE_CLIENT_ID` (PowerShell's `$env:NAME = ""` *deletes* the
  variable), so a `frontend\.env.local` with your real client ID is baked into that build and the CI-mode run is less
  representative than on Linux. The default run pins an empty client ID for both servers, so it is unaffected.
- One of them is an E2E-only trick worth knowing: `e2e/helpers.ts` changes the status by running `manage.py
  shell` against the same database, exactly as step 12 below does by hand.

#### Step 3: Start the servers and make three accounts and two posts

**Where:** First window 1 (the Django server) and window 3 (the frontend), then window 2 (the commands).
**Keep using window 2 for steps 4 to 9.**

**What this does:** Windows 1 and 3 run the two servers. In window 2 you sign up three accounts through the API
and mark them verified, then `ada` posts a fact with two sources and an opinion. The helpers `Mk` (make a post,
print its id) and `Fetch` (print the status code, then the answer) are used by the next steps.

Window 1 (in `backend\`, venv active):

```powershell
python manage.py runserver                          # leave it running
```

Window 3:

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero\frontend
npm run dev                                         # leave it running
```

Window 2 (in `backend\` with the venv active: steps 1 and 2 leave you there). If you opened a new window,
first run `cd C:\Users\Nafis\Downloads\Rumor-Zero\backend` and `.\.venv\Scripts\Activate.ps1`:

```powershell
$id = Get-Date -Format "HHmmss"                     # a unique suffix so the addresses are new each run
$h = '-H', 'Origin: http://localhost:3000', '-H', 'X-Requested-With: rumor-zero'   # headers every auth call needs
function Signup($email, $username) {
@"
{"email": "$email", "username": "$username", "password": "correct-horse-battery-42", "turnstile_token": "XXXX.DUMMY.TOKEN.XXXX"}
"@ | Set-Content -Encoding ascii $env:TEMP\rz-signup.json
  (curl.exe -s @h -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-signup.json" http://localhost:8000/api/auth/app/v1/auth/signup | ConvertFrom-Json).meta.access_token
}
$ada = Signup "part5-ada-$id@example.test" "part5_ada_$id"      # $ada = ada's login token (the author)
$bo = Signup "part5-bo-$id@example.test" "part5_bo_$id"         # $bo = bo's login token (another reader)
$cy = Signup "part5-cy-$id@example.test" "part5_cy_$id"         # $cy = cy's login token (kept for the browser)
python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(email__startswith='part5-', email__endswith='$id@example.test').update(is_email_verified=True), 'accounts marked verified')" | Select-Object -Last 1
foreach ($t in $ada, $bo, $cy) { curl.exe -s -H "Authorization: Bearer $t" http://localhost:8000/api/v1/me/ | ConvertFrom-Json | Select-Object username, is_email_verified | ConvertTo-Json -Compress }
$api = 'http://localhost:8000/api/v1'
# Mk <token> <json>: makes a post, prints its id
function Mk($token, $json) {
  $json | Set-Content -Encoding ascii $env:TEMP\rz-post.json
  (curl.exe -s -H "Authorization: Bearer $token" -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-post.json" "$api/posts/" | ConvertFrom-Json).id
}
# Fetch <path> [token] [fields]: prints the HTTP status, then the answer (cut down to `fields` when given)
function Fetch($path, $token, $props) {
  $a = @()
  if ($token) { $a = '-H', "Authorization: Bearer $token" }
  $out = curl.exe -s -w "`n%{http_code}" @a "$api$path"
  $body = $out[0..($out.Count - 2)] -join ''
  if ($props -and $body) { $body = $body | ConvertFrom-Json | Select-Object $props | ConvertTo-Json -Depth 5 -Compress }
  "$($out[-1])  $body"
}
$fact = Mk $ada '{"content":"Solar capacity grew by roughly 30% worldwide last year.","post_type":"fact","sources":["doi:10.1038/s41558-024-02102","https://www.iea.org/reports/renewables-2023"]}'
$op = Mk $ada '{"content":"I think the new tram line will change how the city moves.","post_type":"opinion"}'
"$($ada.Substring(0,10)) $($bo.Substring(0,10)) $($cy.Substring(0,10))"      # three prefixes, not an error
"fact=$fact"; "op=$op"                                                      # two ids, not empty
```

**You should see** (the number in the names is your `id`, and the ids differ):

```text
3 accounts marked verified
{"username":"part5_ada_190845","is_email_verified":true}
{"username":"part5_bo_190845","is_email_verified":true}
{"username":"part5_cy_190845","is_email_verified":true}
eyJhbGciOi eyJhbGciOi eyJhbGciOi
fact=fb1fc4a4-232f-4d10-830c-d83b343e5b5a
op=d51f9804-6080-4107-bda3-90e1bdd1f27d
```

- The shell prints a line about auto-imported objects first; `Select-Object -Last 1` keeps only ours.
- Sign-up is limited to 20 a minute per address (Part 1), and still calls Cloudflare's test widget, so it
  needs internet.

**If it differs:** an empty token or an empty `$fact` means the sign-up or the post failed: `runserver` isn't
running, or you signed up more than 20 times in a minute. Fix that and run this step again
from `$id = Get-Date …`.

#### Step 4: Read a post

**Where:** Terminal window 2 (the same terminal as step 3).

**What this does:** Reads the post's page data, `GET /api/v1/posts/{id}/`, as nobody, as another user and as
the author. Anyone can read a post; only `is_mine` differs. Then two bad ids.

```powershell
Fetch "/posts/$fact/" $null @('status', 'post_type', 'content', @{n='sources'; e={@($_.sources.kind)}}, 'is_mine', 'verdict_note', 'confidence_score', @{n='keys'; e={@($_.PSObject.Properties).Count}})   # 1: anyone, no login
Fetch "/posts/$fact/" $bo @('is_mine')                                                                                       # 2: another user
Fetch "/posts/$fact/" $ada @('is_mine')                                                                                      # 3: the author
Fetch "/posts/$op/" $null @('status', 'post_type', 'content', 'sources', 'is_mine')                                          # 4: an opinion
Fetch "/posts/not-a-post-id/"                                                                                                # 5: not an id at all
Fetch "/posts/00000000-0000-4000-8000-000000000000/"                                                                         # 6: no such post
```

**You should see** (six commands, six answers):

```text
200  {"status":"pending","post_type":"fact","content":"Solar capacity grew by roughly 30% worldwide last year.","sources":["doi","url"],"is_mine":false,"verdict_note":"","confidence_score":null,"keys":23}
200  {"is_mine":false}
200  {"is_mine":true}
200  {"status":"published","post_type":"opinion","content":"I think the new tram line will change how the city moves.","sources":[],"is_mine":false}
404  {"detail":"Not found.","code":"not_found"}
404  {"detail":"Not found.","code":"not_found"}
```

- The answer has the same 23 keys as a post in the feed. The sources come with their kind (`doi`, `url`) in the
  order you gave them.
- An id that isn't an id gets the same JSON 404 as an unknown one, never a server error.

#### Step 5: Ask for the live status of several posts

**Where:** Terminal window 2.

**What this does:** Calls `GET /api/v1/posts/status/?ids=…`, the endpoint the badges poll. It is public, takes up
to 50 ids and returns only what a badge needs.

```powershell
Fetch "/posts/status/?ids=$fact,$op,00000000-0000-4000-8000-000000000000"            # 1: two real posts and one that doesn't exist
Fetch "/posts/status/?ids=$fact" "not-a-token" @(@{n='count'; e={@($_.results).Count}})  # 2: a garbage token is simply ignored
Fetch "/posts/status/"                                                                   # 3: no ids
Fetch "/posts/status/?ids=nope"                                                          # 4: a malformed id
$many = python -c "import uuid; print(','.join(str(uuid.uuid4()) for _ in range(51)))"
Fetch "/posts/status/?ids=$many"                                                         # 5: 51 ids
```

**You should see:**

```text
200  {"results":[{"id":"fb1fc4a4-232f-4d10-830c-d83b343e5b5a","status":"pending","confidence_score":null,"verdict_source":null},{"id":"d51f9804-6080-4107-bda3-90e1bdd1f27d","status":"published","confidence_score":null,"verdict_source":null}]}
200  {"count":1}
400  {"ids":["Send the ids of the posts to check."]}
400  {"ids":["'nope' isn't a post id."]}
400  {"ids":["Check at most 50 posts at a time."]}
```

- Line 1 leaves out the id that doesn't exist; the order is the order you asked in. `confidence_score` is only
  set for a verdict the pipeline made, and `verdict_source` tells who decided.
- Line 2: this endpoint never checks the login, so an expired token can't turn a public read into a 401.
  (`GET /api/v1/posts/{id}/` does check a token it is given, and the page then refreshes and retries.)

#### Step 6: The author deletes a post

**Where:** Terminal window 2.

**What this does:** Tries to delete the opinion as nobody, as another user and as its author, then looks at the
result everywhere. Deleting only hides the post: the row stays in the database.

```powershell
curl.exe -s -w '  %{http_code}\n' -X DELETE "$api/posts/$op/"                                                  # 1: nobody
curl.exe -s -w '  %{http_code}\n' -X DELETE -H "Authorization: Bearer $bo" "$api/posts/$op/"                    # 2: another user
curl.exe -s -w '  %{http_code}\n' -X DELETE -H "Authorization: Bearer $ada" "$api/posts/$op/"                   # 3: the author
curl.exe -s -w '  %{http_code}\n' -X DELETE -H "Authorization: Bearer $ada" "$api/posts/$op/"                   # 4: the author again
Fetch "/posts/$op/" $ada                                                                                       # 5: its page, even for the author
[array]::IndexOf(@((curl.exe -s "$api/posts/" | ConvertFrom-Json).results.post.id), $op)                       # 6: the feed (-1 = not in it)
python manage.py shell -c "from apps.posts.models import Post; p = Post.objects.get(pk='$op'); print(p.status, p.deleted_at is not None, p.content[:20])" | Select-Object -Last 1   # 7: the database
```

**You should see:**

```text
{"detail":"Authentication credentials were not provided.","code":"not_authenticated"}  401
{"detail":"Only the author can do that.","code":"not_author"}  403
  204
{"detail":"Not found.","code":"not_found"}  404
404  {"detail":"Not found.","code":"not_found"}
-1
published True I think the new tram
```

- 204 means done, with no body. Deleting twice is a 404 (the post is already hidden). `-1` on line 6 means the
  post isn't in the feed any more.
- Line 7 is the audit trail: the post is still there, still `published`, with `deleted_at` set (`True`).
  Django Admin shows it too (step 10). A deleted fact post still counts toward the author's 24-hour fact
  allowance, so deleting and reposting can't get around it.
- Deleting doesn't use up the `post_create` throttle (30 posts an hour).

#### Step 7: A removed post is a tombstone

**Where:** Terminal window 2, in `backend\` with the venv active.

**What this does:** Makes a third post, then sets it to `removed` straight in the database (what a moderator's
Remove will do in Part 10, with a note kept only for staff). A visitor and another user get the same keys with
the text, sources and note blanked; its author still sees everything.

```powershell
$fact2 = Mk $ada '{"content":"Rain is wet, says the weather office.","post_type":"fact","sources":["10.1000/xyz"]}'
python manage.py shell -c "from apps.posts.models import Post; print(Post.objects.filter(pk='$fact2').update(status='removed', verdict_note='internal'), 'post set to removed')" | Select-Object -Last 1
Fetch "/posts/$fact2/" $null @('status', 'content', 'sources', 'verdict_note', @{n='author'; e={$_.author.username}}, 'is_mine', @{n='keys'; e={@($_.PSObject.Properties).Count}})   # 1: the public
Fetch "/posts/$fact2/" $bo @('status', 'content')                                                                             # 2: another user
Fetch "/posts/$fact2/" $ada @('status', 'content', @{n='sources'; e={@($_.sources).Count}}, 'verdict_note', 'is_mine')        # 3: the author
Fetch "/posts/status/?ids=$fact2"                                                                                             # 4: the poll
[array]::IndexOf(@((curl.exe -s "$api/posts/" | ConvertFrom-Json).results.post.id), $fact2)                                  # 5: the feed (-1 = not in it)
```

**You should see** (the name is your `id`):

```text
1 post set to removed
200  {"status":"removed","content":"","sources":[],"verdict_note":"","author":"part5_ada_190845","is_mine":false,"keys":23}
200  {"status":"removed","content":""}
200  {"status":"removed","content":"Rain is wet, says the weather office.","sources":1,"verdict_note":"internal","is_mine":true}
200  {"results":[{"id":"cd39bb38-a178-4122-bc48-80a150bd7210","status":"removed","confidence_score":null,"verdict_source":null}]}
-1
```

- Line 1 is the **tombstone**: still 23 keys, the author's name and the post time stay, but `content`, `sources`,
  `verdict_note` (and the confidence and verdict source) are blank, so nothing of the post leaks.
- Line 3: the author sees their own removed post in full. The removal reason and the appeal button come with
  Parts 10 and 11.
- Line 4: the poll answers `removed` (so an open tab learns it) with nothing else. Line 5 (`-1`): it is not in the feed.

#### Step 8: The status endpoint is rate limited

**Where:** Terminal window 2.

**What this does:** Waits a minute so the allowance starts fresh, then asks for the status 125 times. The
limit is `status_poll`: 120 a minute per client address. It counts only this endpoint, so reading the feed
still works.

```powershell
Start-Sleep 61                                      # let the one-minute allowance start fresh
1..125 | ForEach-Object { curl.exe -s -o NUL -w '%{http_code}\n' "$api/posts/status/?ids=$fact" } | Group-Object | Select-Object Count, Name
curl.exe -s "$api/posts/status/?ids=$fact"
curl.exe -s -D - -o NUL "$api/posts/status/?ids=$fact" | Select-String -Pattern '^(HTTP|retry-after)'
curl.exe -s -o NUL -w 'the feed still answers: %{http_code}\n' "$api/posts/"
```

**You should see** (the seconds differ):

```text

Count Name
----- ----
  120 200
    5 429
{"detail":"Request was throttled. Expected available in 59 seconds.","code":"throttled"}
HTTP/1.1 429 Too Many Requests
Retry-After: 59
the feed still answers: 200
```

- One tab polling at its fastest makes 6 requests a minute, so 120 is room for about 20 tabs behind one address.
- Wait a minute before step 9 if you want to poll again from this terminal.

#### Step 9: What a link preview or a search crawler sees

**Where:** Terminal window 2, with `runserver` (window 1) and `npm run dev` (window 3) running.

**What this does:** Asks the Next.js server for a post's page with no cookies and no JavaScript, the way a crawler
does, and picks out the head tags. The server reads the post from Django itself, so the claim and its status are
in the HTML.

```powershell
$html = (curl.exe -s "http://localhost:3000/p/$fact") -join "`n"
[regex]::Matches($html, '<title>[^<]*</title>|(?:property|name)="(?:og:title|og:description|og:type|og:image|twitter:image|twitter:card)" content="[^"]*"|rel="canonical" href="[^"]*"') | ForEach-Object Value | Sort-Object -Unique
"---"
([regex]::Matches($html, [regex]::Escape('Solar capacity grew by roughly 30% worldwide last year.'))).Count
curl.exe -s -o NUL -w 'deleted post: %{http_code}\n' "http://localhost:3000/p/$op"
curl.exe -s -o NUL -w 'not an id: %{http_code}\n' http://localhost:3000/p/not-a-post-id
$gone = (curl.exe -s -w "`nremoved post: %{http_code}" "http://localhost:3000/p/$fact2") -join "`n"
[regex]::Matches($gone, '<title>[^<]*</title>|name="robots" content="[^"]*"|removed post: [0-9]+|Solar|Rain is wet') | ForEach-Object Value | Sort-Object -Unique
```

**You should see** (the first compile of the page in `next dev` takes a few seconds; the post id and the
count of claim occurrences can differ):

```text
name="twitter:card" content="summary_large_image"
name="twitter:image" content="http://localhost:3000/twitter-image.png"
property="og:description" content="Fact · CHECKING FACTS…"
property="og:image" content="http://localhost:3000/opengraph-image.png"
property="og:title" content="Solar capacity grew by roughly 30% worldwide last year. · Rumor Zero"
property="og:type" content="article"
rel="canonical" href="http://localhost:3000/p/fb1fc4a4-232f-4d10-830c-d83b343e5b5a"
<title>Solar capacity grew by roughly 30% worldwide last year. · Rumor Zero</title>
---
8
deleted post: 404
not an id: 404
name="robots" content="noindex, nofollow"
removed post: 200
<title>Removed post · Rumor Zero</title>
```

- The title is the start of the claim plus ` · Rumor Zero`; the description is the type and the status label.
  The share image is the site's static one (generating one per post would cost too much CPU on the free
  Workers plan).
- The claim appears several times (title, tags and the page itself). A post that was deleted, or an id that
  isn't one, is a real HTTP 404.
- A **removed** post is a 200 with the title "Removed post", `noindex`, and none of its text (the last command
  finds neither "Solar" nor "Rain is wet").

#### Step 10: Django Admin still shows a deleted post

**Where:** Browser, while `runserver` is running in window 1.

**What this does:** Opens the admin list of posts and finds the opinion `ada` deleted in step 6. The admin is
read-only until Part 10.

| URL | Expect |
|---|---|
| http://localhost:8000/admin/ | Sign in with the superuser you made in Part 0A. If it 404s, `ADMIN_URL_PATH` in `backend\.env` isn't `admin/`; use that path. |
| http://localhost:8000/admin/posts/post/ | The posts, newest first, including "I think the new tram line…" with a date in the **Deleted at** column. The filter panel now has **By deleted at** with *All*, *Empty* and *Not empty*. |
| Click **Not empty** under *By deleted at* | Only the deleted posts (the tram opinion). **Empty** shows everything that is still live. |

- The same rules are checked by the automated tests (`test_api_delete.py` finds the row through the admin
  changelist and both filter values).

#### Step 11: The post page in the browser

**Where:** Browser, with `runserver` (window 1) and `npm run dev` (window 3) running. Log in at
http://localhost:3000/login as **`cy`**, with `part5-cy-<your id>@example.test` and `correct-horse-battery-42`
(the id from step 3).

**What this does:** Posts a fact as `cy`, opens its page from the card, and tries Copy link and Delete.

| Do this | Expect |
|---|---|
| Open http://localhost:3000/home, click **New post**, type `Global solar output doubled in six years, the agency says.`, choose **Fact**, put `doi:10.1038/s41558-024-02102` in Source 1, click **Add another source** and put `https://www.iea.org/reports/renewables-2023` in Source 2, click **Post fact, will be checked** | The post is at the top of Recent with **CHECKING FACTS…**. |
| Look at its card's text and sources row | The claim is a link, and so is the whole card (the border darkens on hover). The row under it shows `doi.org/10.1038/s41558-024-02102 ↗` (opens doi.org in a new tab) and a blue `+1 more`. |
| Click the claim (or `+1 more`) | The address becomes `http://localhost:3000/p/<id>` (with `#sources` for `+1 more`, which scrolls to the sources). The page: **← BACK TO HOME**, a white card with a pale grey left edge holding **FACT** and **CHECKING FACTS…**, the claim in large upright serif, `@part5_cy_<id>` with `Oct 9, 2026, 1:10 PM UTC` (a UTC time), then **Copy link** and **Delete** |
| Look under the card | A **Verdict** card saying **Checking facts…** and "We're checking this claim. This page updates on its own when there is a result.", then **Sources (2)**: `01  DOI  10.1038/s41558-024-02102` and `02  LINK  https://www.iea.org/reports/renewables-2023`, each with an open-in-new icon |
| Click an open-in-new icon | The source opens in a new tab (the DOI goes to `https://doi.org/10.1038/…`). |
| Click **Copy link** | A dark toast says **Link copied.** Paste into the address bar: it is `http://localhost:3000/p/<id>`. |
| Click **Delete** | A dialog **Delete this post?**: "It disappears from feeds and from its page right away. This can't be undone." and, because it is a fact, "A deleted fact post still counts toward your fact posts for the last 24 hours." with **Cancel** and a red **Delete post**. Click **Cancel**: nothing changes. |
| Click **Delete**, then **Delete post** | You are back on `/home` with the toast **Post deleted.** and the post is gone from Recent (also after a reload). |
| Open the old `/p/<id>` address | The page "Page not found" (a real 404, for you as well). |
| Open a post you didn't write (any post by `ada`) | Same page, with **Copy link** but **no Delete**. |

- Log out and open any `/p/<id>`: the same page without Delete, no login needed.
- A post removed by a moderator (step 7's `fact2`): as a visitor, `/p/<id>` shows a white card with the author's
  name, the date and "This post was removed by a moderator." and nothing else. Logged in as its author, the page
  shows the text under a pale orange note "This post was removed by a moderator. Only you can see this text.",
  a grey **REMOVED** badge next to **FACT**, and no Verdict card. In the feed, a card that is open when its post
  is removed turns into a grey "Removed by a moderator" card within about 10 seconds.

#### Step 12: Badges update by themselves

**Where:** Browser (logged in as `cy`, with a fresh fact on screen) and Terminal window 2.

**What this does:** Changes a pending post's status in the database while its page and the feed are open, the way
the pipeline (Part 9) and the moderators (Part 10) will, and watches the badge change without a reload. The
status endpoint is polled every 10 seconds at first, then every 15, 22 … up to every 60, only while the tab is
on screen, and it stops after 10 minutes of visible time.

First post another fact as `cy` (step 11's first row) and open its page; keep the feed (`/home`) open in a
second tab. Copy the post's id from the address (`/p/<id>`). In window 2:

```powershell
python manage.py shell -c "from apps.posts.models import Post; print(Post.objects.filter(pk='<id>').update(status='verified_true', verdict_source='pipeline', pipeline_verdict='true', confidence_score=94), 'post updated')" | Select-Object -Last 1
```

Replace `<id>` with the id you copied.

**You should see** `1 post updated`, and in the browser, within about 10 seconds and with no reload:

| Where | Expect |
|---|---|
| The post's page | The chip changes from **CHECKING FACTS…** to a teal **VERIFIED 94%**, the left edge turns teal, and the Verdict card says **Checked automatically · 94% confidence** and "This claim was found to be true." |
| The feed tab (when you switch to it) | The card for that post shows **VERIFIED 94%** too. |

- Watching the polling: open DevTools → Network, filter on `status`. Requests to `/api/v1/posts/status/?ids=…`
  go out about every 10 s, then 15 s, 22 s … while a pending post is on screen, and **stop for good once nothing
  is pending**. Switch to another browser tab: no requests while it is hidden, and one the moment you come back.
  (These timings are covered by the automated tests with fake timers; the "badge changes within about 10 seconds"
  part was also watched in headless Chromium.)
- Try `status='removed'` instead: the feed card turns into a grey "Removed by a moderator" card, and the page
  becomes the tombstone for everyone but the author.

#### Step 13: A phone-sized window

**Where:** Browser, logged in as `cy`.

**What this does:** Checks the post page at phone width. In Firefox or Chrome press `F12`, then the "responsive
design" / device toolbar button, and set the width to 390. Open any `/p/<id>` of a fact.

| Do this | Expect |
|---|---|
| Open the post's page | A top bar with the logo and your avatar, then **← BACK TO HOME**, the card with the claim wrapped over several lines, the author line and a UTC date, and **Copy link** and **Delete** side by side. A bottom bar (Home, Search, New post, Notifications, Profile). **No sideways scrolling.** |
| Scroll down | **Verdict** and **Sources (2)**: a long link wraps inside its row (`https://www.iea.org/reports/r` / `enewables-2023`), and the open-in-new icon stays at the right. |
| Tap **Delete** | The dialog fits the screen, with **Cancel** and **Delete post**. |

#### Step 14: Stop and clean up

**Where:** Every terminal window, plus the browser.

- Stop the servers: `Ctrl+C` in windows 1 and 3 (a leftover `next dev`: step 12 of Part 1).
- Delete the test accounts and their posts (the posts go with them). In window 2, in `backend\` with the
  venv active:

  ```powershell
  python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(email__startswith='part5-').delete())" | Select-Object -Last 1
```

  After one clean run of this guide it prints `(12, {'posts.Post': 6, 'account.EmailAddress': 3, 'accounts.User': 3})`: how many rows went in all, and per
  table (6 posts: the three `ada` made in steps 3 and 7, plus the ones you made as `cy` in steps 11 and 12, so your
  count differs; a deleted post is still a row). Nothing else is touched. (The E2E tests' accounts stay in your local database, as in earlier parts: Django
  Admin → Users deletes them.)
- `docker compose down` (repo root) stops the containers and keeps the data; `docker compose down -v`
  wipes the whole local database, which is destructive.
- No secret was used or printed in this part: the only values in the commands are Cloudflare's public test
  token and the throwaway password of the test accounts.

### Part 6: Profiles, follows, Following feed

Needs Part 0A's containers and virtualenv, Part 0C's frontend, and your own `backend\.env` and
`frontend\.env.local`. Part 6 adds **one migration** (`social.0001_initial`, the follows table), **no dependency**
and **no new variable** (`FEED_CACHE_SECONDS` was already in `.env.example`; the code reads it now). It adds
the endpoints `GET /api/v1/users/{username}/` (and `…/posts/`, `…/followers/`, `…/following/`),
`POST` and `DELETE /api/v1/users/{username}/follow/`, and `GET /api/v1/feed/`.

**Which terminal window for what.** Open the windows once and keep using the same ones:

| Window | What runs in it | Used in steps |
|---|---|---|
| Window 1 (server) | `python manage.py runserver` in `backend\`, venv active. Leave it running. Start it in step 3, **after** step 2 (Playwright starts its own servers and needs ports 3000 and 8000 free). | 3 to 14 |
| Window 2 (commands) | All the `curl.exe` and `python manage.py` commands. **Use the same window for steps 3 to 10**: the variables and functions you set in step 3 (`$id`, `$h`, `$ada`, `$bo`, `$cy`, `$api`, `$boname`, `Signup`, `Mk`, `Fetch`) only live in that one terminal. If you close it, redo step 3. | 1 to 10, 15 |
| Window 3 (frontend) | `npm run dev` in `frontend\`. Leave it running. | 10 to 14 |
| Browser | Steps 11 to 14 | 11 to 14 |

Things to know first:

- Steps 3 to 10 talk to the API directly with `curl.exe` (with `.exe`: in PowerShell 5.1 plain `curl` is a different command). Steps 11 to 14 use the
  browser. Step 3 makes three accounts, all verified: `bo` is the person whose profile we look at, `ada` follows
  `bo`, and `cy` stays for the browser steps. Later steps add `dee` (never verified) and `fay` (for the throttle).
- **The PowerShell blocks below were not run on Windows.** The agent works on the Linux PC; it ran the bash
  twin of every command in the Linux guide on 2026-10-09, and the outputs below are those. The PowerShell
  commands follow the patterns Parts 1 to 5 proved on Windows (JSON written to a file and sent with
  `--data-binary "@file"`, `curl.exe`, no `&&`). If one behaves differently, tell the agent which.
- The API and page outputs below were recorded on Linux on 2026-10-09. The browser steps were checked the same
  day with headless Chromium (screenshots at 1280 and 390 px), not by a person at a keyboard. Ids, numbers in
  names, times and token prefixes differ on every run.
- Nothing here sends an email: step 3 marks the accounts verified with a shell command, which stands in for
  clicking the link (Part 2 shows the real flow). Step 7 sets post statuses the same way, because the pipeline
  and the moderator tools that do it for real arrive in Parts 9 and 10.
- **What Part 6 does and doesn't show:** profiles are public; following needs a verified email; a profile's
  **Verified** and **FALSE** counters also count posts the author deleted, but never removed ones (step 7);
  the Following feed keeps only the *ids* of its first page for 30 seconds (step 8). Likes, comments,
  reposts and the credibility score come in later parts.

#### Step 1: Run the automated backend checks

**Where:** Terminal window 2 (commands), starting in the repo root.

**What this does:** Starts the database containers, activates the Python environment, applies the new migration,
confirms there is no further one, then runs the whole backend test suite, the new social tests, the linter and
the formatter check.

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero
docker compose up -d
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py migrate                            # Applying social.0001_initial... OK
python manage.py makemigrations --check --dry-run   # No changes detected
python manage.py check                              # System check identified no issues (0 silenced).
python -m pytest                                    # 1336 passed
python -m pytest apps/social -q                     # 160 passed
ruff check . ; ruff format --check .                # All checks passed! / 132 files already formatted
```

**You should see:** `Applying social.0001_initial... OK` (nothing to apply the second time), `No changes detected`
and `System check identified no issues (0 silenced).`, then the full run ends with `1336 passed`, the social run
with `160 passed`, and the last line pair is `All checks passed!` and `132 files already formatted`. (Counts may
grow later; what matters is that nothing fails.)

- The 160 new social tests: `test_models.py` (6: the unique pair, nobody follows themselves, both list indexes),
  `test_services.py` (18: follow is idempotent, two simultaneous follows make one row, the cache is cleared),
  `test_api_profile.py` (26), `test_api_follow.py` (23, including the real 100-requests-an-hour throttle),
  `test_api_lists.py` (23: order, cursor walk, crafted cursors, constant query counts), `test_api_user_posts.py`
  (19), `test_api_feed.py` (14), `test_feed_cache.py` (25: what is cached, when it is cleared, what a hit still
  reads fresh), `test_admin.py` (4) and `test_no_network.py` (2).
- Outside `apps/social`: the cursor check moved into a shared `TimestampCursorMixin` (`apps/core/tests/test_pagination.py`
  tests it, with a control showing what the unguarded class does), `FEED_CACHE_SECONDS` has settings tests, and
  `create_post` clears the author's cached feed.

#### Step 2: Run the automated frontend checks

**Where:** Terminal window 2, then `cd ..\frontend`. Playwright (the last two commands) starts Django and
Next itself, so **no servers may be running on ports 3000 and 8000** (it reuses them if they are, with
whatever settings they have).

**What this does:** Runs the linters, the type check, the component tests, the production build and the
end-to-end tests.

```powershell
cd ..\frontend                                      # from backend\
npm run lint ; npm run lint:tokens ; npm run typecheck ; npm run format:check
npm test                                            # 99 files, 1320 tests passed
npm run build
npm run test:e2e                                    # 29 passed
$env:CI = "1" ; npm run test:e2e ; Remove-Item Env:CI   # 29 passed (against the production build)
cd ..\backend                                       # back to backend\ for steps 3 to 10
```

**You should see:** the first line prints nothing from ESLint and TypeScript and ends with
`lint:tokens OK (…)` and `All matched files use Prettier code style!`. `npm test` ends with
`Test Files  99 passed (99)` and `Tests  1320 passed (1320)`. `npm run build` lists the routes as in Part 5, plus
`ƒ /u/[username]`, `ƒ /u/[username]/followers` and `ƒ /u/[username]/following` (dynamic: the profile is read on the
server for each request). Each E2E run ends with `29 passed`: the 24 earlier tests and 5 new ones in
`e2e/social.spec.ts`.

- The new E2E file signs up **two** people once and shares them (allauth limits sign-ups to 20 a minute per
  address and the rest of the suite already uses most of that). Its tests: a crawler gets a profile's `<title>`,
  Open Graph and canonical tags, an upper-case address redirects and an unknown name is a 404; a visitor is sent
  to log in to follow and sees no Following tab; the profile, the followers list and `/home` fit a phone with no
  sideways scroll; A follows B, B posts, A sees it under Following, then unfollows and the tab is empty again;
  your own post is in your Following tab at once and your own profile shows Edit profile and no Follow.
- On Windows `npm run build` can't blank `NEXT_PUBLIC_GOOGLE_CLIENT_ID` (PowerShell's `$env:NAME = ""` *deletes* the
  variable), so a `frontend\.env.local` with your real client ID is baked into that build and the CI-mode run is less
  representative than on Linux. The default run pins an empty client ID for both servers, so it is unaffected.
- Two E2E helpers changed: the sign-up helper now waits up to 30 seconds for `/verify-email` (hashing the password
  takes a while when six workers sign up at once; this flake predates Part 6), and `posts.spec.ts` now expects two
  links on a card (the author and the claim).

#### Step 3: Start the servers and make three accounts and two posts

**Where:** First window 1 (the Django server) and window 3 (the frontend), then window 2 (the commands).
**Keep using window 2 for steps 4 to 10.**

**What this does:** Windows 1 and 3 run the two servers. In window 2 you sign up three accounts through the API
and mark them verified, then `bo` posts an opinion and a fact with a DOI. The helpers `Mk` (make a post, print its id) and `Fetch` (print the status code, then the answer) are used by the next steps.

Window 1 (in `backend\`, venv active):

```powershell
python manage.py runserver                          # leave it running
```

Window 3:

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero\frontend
npm run dev                                         # leave it running
```

Window 2 (in `backend\` with the venv active: steps 1 and 2 leave you there). If you opened a new
terminal, first run `cd C:\Users\Nafis\Downloads\Rumor-Zero\backend` and `.\.venv\Scripts\Activate.ps1`:

```powershell
$id = Get-Date -Format "HHmmss"                     # a unique suffix so the addresses are new each run
$h = '-H', 'Origin: http://localhost:3000', '-H', 'X-Requested-With: rumor-zero'   # headers every auth call needs
function Signup($email, $username) {
@"
{"email": "$email", "username": "$username", "password": "correct-horse-battery-42", "turnstile_token": "XXXX.DUMMY.TOKEN.XXXX"}
"@ | Set-Content -Encoding ascii $env:TEMP\rz-signup.json
  (curl.exe -s @h -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-signup.json" http://localhost:8000/api/auth/app/v1/auth/signup | ConvertFrom-Json).meta.access_token
}
$ada = Signup "part6-ada-$id@example.test" "part6_ada_$id"      # $ada = ada's login token (follows bo)
$bo = Signup "part6-bo-$id@example.test" "part6_bo_$id"         # $bo = bo's login token (the author we look at)
$cy = Signup "part6-cy-$id@example.test" "part6_cy_$id"         # $cy = cy's login token (kept for the browser)
python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(email__startswith='part6-', email__endswith='$id@example.test').update(is_email_verified=True), 'accounts marked verified')" | Select-Object -Last 1
$api = 'http://localhost:8000/api/v1'
$adaname = "part6_ada_$id"; $boname = "part6_bo_$id"; $cyname = "part6_cy_$id"
# Mk <token> <json>: makes a post, prints its id
function Mk($token, $json) {
  $json | Set-Content -Encoding ascii $env:TEMP\rz-post.json
  (curl.exe -s -H "Authorization: Bearer $token" -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-post.json" "$api/posts/" | ConvertFrom-Json).id
}
# Fetch <path> [token] [fields]: prints the HTTP status, then the answer (cut down to `fields` when given)
function Fetch($path, $token, $props) {
  $a = @()
  if ($token) { $a = '-H', "Authorization: Bearer $token" }
  $out = curl.exe -s -w "`n%{http_code}" @a "$api$path"
  $body = $out[0..($out.Count - 2)] -join ''
  if ($props -and $body) { $body = $body | ConvertFrom-Json | Select-Object $props | ConvertTo-Json -Depth 5 -Compress }
  "$($out[-1])  $body"
}
$op1 = Mk $bo '{"content":"I think the new tram line will change how the city moves.","post_type":"opinion"}'
$fact1 = Mk $bo '{"content":"Solar capacity grew by roughly 30% worldwide last year.","post_type":"fact","sources":["doi:10.1038/s41558-024-02102"]}'
"$($ada.Substring(0,10)) $($bo.Substring(0,10)) $($cy.Substring(0,10))"      # three prefixes, not an error
"op1=$op1"; "fact1=$fact1"                                                  # two ids, not empty
```

**You should see** (the number in the names is your `id`, and the ids differ):

```text
3 accounts marked verified
eyJhbGciOi eyJhbGciOi eyJhbGciOi
op1=94dd0202-8d1c-4aca-8c33-8aeee8c7833b
fact1=bb1b71af-8729-4d83-9e4f-26bc1a537d0d
```

- The shell prints a line about auto-imported objects first; `Select-Object -Last 1` keeps only ours.
- Sign-up is limited to 20 a minute per address (Part 1), and still calls Cloudflare's test widget, so it
  needs internet.

**If it differs:** an empty token or an `id` of `null` means the sign-up or the post failed: `runserver` isn't
running, or you signed up more than 20 times in a minute. Fix that and run this step again
from `$id = Get-Date …`.

#### Step 4: Read a profile

**Where:** Terminal window 2 (the same terminal as step 3).

**What this does:** Reads `GET /api/v1/users/{username}/` as nobody and as other people. A profile is public; only
`is_following` and `is_me` depend on who asks. Then four names that don't give a profile.

```powershell
Fetch "/users/$boname/" $null @('username', 'display_name', 'bio', 'avatar_url', 'counts', 'reputation', 'is_following', 'is_me', @{n='keys'; e={@($_.PSObject.Properties).Count}})   # 1: anyone, no login
Fetch "/users/$($boname.ToUpper())/" $null @('username')                                                                  # 2: upper case works
Fetch "/users/$boname/" $ada @('is_following', 'is_me')                                                                   # 3: ada, who doesn't follow bo yet
Fetch "/users/$boname/" $bo @('is_following', 'is_me')                                                                    # 4: bo looking at himself
Fetch "/users/nobody_$id/"                                                                                                # 5: no such user
Fetch "/users/ab/"                                                                                                        # 6: too short to be a username
Fetch "/users/$boname%00x/"                                                                                               # 7: a NUL byte in the name
```

**You should see** (seven commands, seven answers):

```text
200  {"username":"part6_bo_212733","display_name":"","bio":"","avatar_url":null,"counts":{"followers":0,"following":0,"posts":2,"verified":0,"false":0},"reputation":{"score":null,"sample":0},"is_following":false,"is_me":false,"keys":10}
200  {"username":"part6_bo_212733"}
200  {"is_following":false,"is_me":false}
200  {"is_following":false,"is_me":true}
404  {"detail":"Not found.","code":"not_found"}
404  {"detail":"Not found.","code":"not_found"}
404  {"detail":"Not found.","code":"not_found"}
```

- The profile has exactly 10 keys and never an email or role. `posts` is 2: the opinion and the fact. A new
  account has a blank display name, so the page shows `@username` once instead.
- `reputation` is there already (`score` stays `null` until a person has 3 counted events, which Part 11B
  starts counting); the page doesn't show it yet.
- Lookup is case-insensitive (line 2). An unknown name, a name too short to be one and a name with a NUL byte
  all give the same JSON 404, never a server error (the NUL case was a 500 until a test caught it).

#### Step 5: Follow and unfollow

**Where:** Terminal window 2.

**What this does:** Follows and unfollows through `POST` and `DELETE /api/v1/users/{username}/follow/`, with
every refusal. Both are idempotent. Following needs a verified email, unfollowing only a login.

```powershell
function Follow($username, $token) { $a = @(); if ($token) { $a = '-H', "Authorization: Bearer $token" }; curl.exe -s -w "  %{http_code}`n" -X POST @a "$api/users/$username/follow/" }       # Follow <username> [token]
function Unfollow($username, $token) { $a = @(); if ($token) { $a = '-H', "Authorization: Bearer $token" }; curl.exe -s -w "  %{http_code}`n" -X DELETE @a "$api/users/$username/follow/" }   # Unfollow <username> [token]
Follow $boname $ada                                  # 1: the first follow is 201
Follow $boname $ada                                  # 2: again: 200, nothing changes
Follow $boname                                       # 3: nobody logged in
Follow $adaname $ada                                 # 4: following yourself
Follow "nobody_$id" $ada                             # 5: no such user
$dee = Signup "part6-dee-$id@example.test" "part6_dee_$id"    # dee never verifies the email
Follow $boname $dee                                  # 6: an unverified account can't follow
Fetch "/users/$boname/" $ada @(@{n='counts'; e={@{followers = $_.counts.followers}}}, 'is_following')    # 7: the count moved
Unfollow $boname $ada                                # 8: unfollow: 204
Unfollow $boname $ada                                # 9: again: still 204
Unfollow $boname $dee                                # 10: an unverified account may unfollow (nothing to remove here)
Fetch "/users/$boname/" $ada @(@{n='counts'; e={@{followers = $_.counts.followers}}}, 'is_following')    # 11: back to 0
Follow $boname $ada                                  # 12: ada follows again for the next steps
```

**You should see** (twelve commands, twelve answers):

```text
{"is_following":true}  201
{"is_following":true}  200
{"detail":"Authentication credentials were not provided.","code":"not_authenticated"}  401
{"detail":"You can't follow yourself.","code":"cannot_follow_self"}  400
{"detail":"Not found.","code":"not_found"}  404
{"detail":"Verify your email address first. Check your inbox for the link.","code":"email_unverified"}  403
200  {"counts":{"followers":1},"is_following":true}
  204
  204
  204
200  {"counts":{"followers":0},"is_following":false}
{"is_following":true}  201
```

- 201 the first time, 200 when you already followed: the same answer, so a retry is safe. Unfollowing is 204 with
  no body, whether or not you were following. Two simultaneous follows make one row (a test proves it).
- Order of checks: login (401), verified email (403), then the throttle, then the name (404), then the rule
  (400). A 401 or 403 never counts against the 100-an-hour allowance (step 9).

#### Step 6: Followers, following and a person's posts

**Where:** Terminal window 2.

**What this does:** `cy` follows `bo` and `bo` follows `cy`; then reads both lists, one page at a time, and
`bo`'s posts with the Facts / Opinions filter. `is_following` and `is_me` are from the point of view of whoever
asks.

```powershell
$strip = { param($u) $u -replace '^part6_' -replace "_$id$" }    # shows "cy" instead of "part6_cy_123456"
Follow $boname $cy                                   # cy follows bo too
Follow $cyname $bo                                   # and bo follows cy
$names = @{n='names'; e={@($_.results | ForEach-Object { & $strip $_.username })}}
Fetch "/users/$boname/followers/" $cy @($names, @{n='is_following'; e={@($_.results.is_following)}}, @{n='is_me'; e={@($_.results.is_me)}}, @{n='keys'; e={@($_.results[0].PSObject.Properties).Count}}, 'next_cursor')   # 1: bo's followers, as cy
Fetch "/users/$boname/followers/" $null @($names, @{n='is_following'; e={@($_.results.is_following)}})                  # 2: the same list as a visitor
Fetch "/users/$boname/following/" $null @($names)                                                                         # 3: who bo follows
Fetch "/users/$boname/followers/?page_size=1" $null @($names, @{n='more'; e={$null -ne $_.next_cursor}})                  # 4: one per page
Fetch "/users/$boname/followers/?cursor=cD1ub3QtYS1kYXRl"                                                                 # 5: a made-up cursor (it decodes to p=not-a-date)
Fetch "/users/$boname/posts/" $null @('pinned', @{n='kinds'; e={@($_.results.kind)}}, @{n='posts'; e={@($_.results.post | ForEach-Object { [ordered]@{type = $_.post_type; status = $_.status; is_mine = $_.is_mine} })}})   # 6: bo's posts
Fetch "/users/$boname/posts/?post_type=fact" $null @(@{n='types'; e={@($_.results.post.post_type)}})                      # 7: facts only
Fetch "/users/$boname/posts/?post_type=opinion" $null @(@{n='types'; e={@($_.results.post.post_type)}})                   # 8: opinions only
Fetch "/users/$boname/posts/?post_type=both"                                                                              # 9: not a type
```

**You should see:**

```text
{"is_following":true}  201
{"is_following":true}  201
200  {"names":["cy","ada"],"is_following":[false,false],"is_me":[true,false],"keys":8,"next_cursor":null}
200  {"names":["cy","ada"],"is_following":[false,false]}
200  {"names":["cy"]}
200  {"names":["cy"],"more":true}
404  {"detail":"Invalid cursor","code":"not_found"}
200  {"pinned":[],"kinds":["post","post"],"posts":[{"type":"fact","status":"pending","is_mine":false},{"type":"opinion","status":"published","is_mine":false}]}
200  {"types":["fact"]}
200  {"types":["opinion"]}
400  {"post_type":["Choose fact or opinion, or leave it out."]}
```

- Followers come newest follow first (`cy`, then `ada`). A row has 8 keys: the public bits plus `bio`,
  `reputation`, `is_following` and `is_me`; never an email. Line 1 is as `cy`, so `cy`'s own row has `is_me`
  true; `is_following` is false everywhere because `cy` follows only `bo`.
- Pages are 20 long (`?page_size=` up to 50); `next_cursor` is an opaque token. A made-up one is a 404, never a
  server error. The number of database queries doesn't grow with the list (tests pin it).
- `bo`'s posts: the same feed shape as Recent (`pinned` is always `[]` here), newest first, only what the public
  can see; a bad `post_type` is a 400 on that field.

#### Step 7: The Verified and FALSE counters

**Where:** Terminal window 2, in `backend\` with the venv active.

**What this does:** Gives `bo` four more fact posts and sets their status the way the pipeline (Part 9) and the
moderators (Part 10) will: one verified, one FALSE, one verified and then **deleted by `bo`**, one **removed**. Then
reads the counters. A deleted post's verdict still counts (so deleting can't erase a FALSE label); a removed post
is in neither counter.

```powershell
$factA = Mk $bo '{"content":"The river authority says the bridge reopened on Monday.","post_type":"fact"}'
$factB = Mk $bo '{"content":"The harvest was the largest ever recorded.","post_type":"fact"}'
$factC = Mk $bo '{"content":"The ferry now runs every ten minutes.","post_type":"fact"}'
$factD = Mk $bo '{"content":"The museum is free on Sundays.","post_type":"fact"}'
@"
from apps.posts.models import Post
for pk, fields in [('$factA', dict(status='verified_true', verdict_source='pipeline', pipeline_verdict='true', confidence_score=94)),
                   ('$factB', dict(status='verified_false', verdict_source='pipeline', pipeline_verdict='false', confidence_score=90)),
                   ('$factC', dict(status='verified_true', verdict_source='pipeline', pipeline_verdict='true', confidence_score=91)),
                   ('$factD', dict(status='removed'))]:
    Post.objects.filter(pk=pk).update(**fields)
print('4 posts set')
"@ | python manage.py shell | Select-Object -Last 1
Fetch "/users/$boname/" $null @('counts')                                 # 1: two verified so far, one FALSE
curl.exe -s -o NUL -w "delete the verified post: %{http_code}`n" -X DELETE -H "Authorization: Bearer $bo" "$api/posts/$factC/"   # 2: bo deletes factC
Fetch "/users/$boname/" $null @('counts')                                 # 3: it is hidden, but its verdict still counts
Fetch "/users/$boname/posts/" $null @(@{n='statuses'; e={@($_.results.post.status)}})   # 4: the list: no removed, no deleted post
```

**You should see:**

```text
4 posts set
200  {"counts":{"followers":2,"following":1,"posts":5,"verified":2,"false":1}}
delete the verified post: 204
200  {"counts":{"followers":2,"following":1,"posts":4,"verified":2,"false":1}}
200  {"statuses":["verified_false","verified_true","pending","published"]}
```

- Line 1: `posts` is 5 (the opinion, the pending fact and three of the four new ones: the removed one is
  hidden), `verified` 2, `false` 1. After the delete (line 3) `posts` falls to 4 but **`verified` stays 2**: the
  deleted post is hidden from the list and the count of posts, yet its verdict stays on the record.
- The list (line 4) has no removed and no deleted post, even for their author.

#### Step 8: The Following feed and its cache

**Where:** Terminal window 2. Needs `REDIS_URL` set in `backend\.env` (as in `.env.example`): line 3 reads the
cache from a second process, which only works when the cache is the shared Redis, not each process's memory.

**What this does:** Reads `GET /api/v1/feed/` as `ada`, who follows `bo`. Shows what is kept in the cache
(only ids), that your own new post appears at once, that a post by someone you follow can take up to 30 seconds
(`FEED_CACHE_SECONDS`), and that a post deleted by its author vanishes immediately because the posts themselves
are read fresh every time. (This step waits 31 seconds.)

```powershell
$adaid = (curl.exe -s -H "Authorization: Bearer $ada" "$api/me/" | ConvertFrom-Json).id
Fetch "/feed/"                                                            # 1: nobody logged in
Fetch "/feed/" $ada @(@{n='contents'; e={@($_.results.post.content)}})   # 2: ada follows bo: bo's posts, newest first
python manage.py shell -c "from django.core.cache import cache; print(cache.get('social:following-feed:v1:$adaid'))" | Select-Object -Last 1   # 3: what is cached for ada
$mine = Mk $ada '{"content":"I think ada can see her own post at once.","post_type":"opinion"}'
Fetch "/feed/" $ada @(@{n='content'; e={$_.results[0].post.content}}, @{n='is_mine'; e={$_.results[0].post.is_mine}})   # 4: ada's own post is first, despite the cache
Mk $bo '{"content":"Bo posts something new right now.","post_type":"opinion"}' | Out-Null
Fetch "/feed/" $ada @(@{n='seen'; e={@($_.results.post.content) -contains 'Bo posts something new right now.'}})   # 5: ada does not see it yet (the cache lives for 30 s)
Start-Sleep 31
Fetch "/feed/" $ada @(@{n='seen'; e={@($_.results.post.content) -contains 'Bo posts something new right now.'}})   # 6: after 30 seconds she does
curl.exe -s -o NUL -w "bo deletes his tram opinion: %{http_code}`n" -X DELETE -H "Authorization: Bearer $bo" "$api/posts/$op1/"
Fetch "/feed/" $ada @(@{n='tram'; e={@($_.results.post.content | Where-Object { $_ -like 'I think the new tram*' }).Count}})   # 7: gone at once, no waiting
```

**You should see:**

```text
401  {"detail":"Authentication credentials were not provided.","code":"not_authenticated"}
200  {"contents":["The harvest was the largest ever recorded.","The river authority says the bridge reopened on Monday.","Solar capacity grew by roughly 30% worldwide last year.","I think the new tram line will change how the city moves."]}
{'ids': ['f44bbb89-28fc-4482-a788-f84c53c1eb09', '83f46a4f-fbb6-4160-a6ec-ddca8d9ebfd5', 'bb1b71af-8729-4d83-9e4f-26bc1a537d0d', '94dd0202-8d1c-4aca-8c33-8aeee8c7833b'], 'next': None}
200  {"content":"I think ada can see her own post at once.","is_mine":true}
200  {"seen":false}
200  {"seen":true}
bo deletes his tram opinion: 204
200  {"tram":0}
```

- Line 3: what the cache holds for `ada` is only a list of post **ids** and the next-page cursor, never any
  text. The posts are read again on every request, so a deleted or removed post disappears at once (line 7), and
  likes and counts (Part 7) will never be stale.
- The cache is cleared for you when you post (line 4), follow or unfollow. A post by someone you follow
  reaches you after at most `FEED_CACHE_SECONDS` (30 by default; 0 turns the cache off). Only a first page asked
  with the default size is cached.
- The Following feed needs a login (line 1) but not a verified email: reading is allowed.

#### Step 9: Following is rate limited

**Where:** Terminal window 2.

**What this does:** Makes a fresh verified account, `fay`, and sends 101 follow requests as her. The limit is
`follow`: 100 an hour per user, shared by follow and unfollow. Reading profiles is not counted.

```powershell
$fay = Signup "part6-fay-$id@example.test" "part6_fay_$id"
python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(email='part6-fay-$id@example.test').update(is_email_verified=True), 'account marked verified')" | Select-Object -Last 1
1..101 | ForEach-Object { curl.exe -s -o NUL -w "%{http_code}`n" -X POST -H "Authorization: Bearer $fay" "$api/users/$boname/follow/" } | Group-Object | Sort-Object Name | ForEach-Object { "{0,6} {1}" -f $_.Count, $_.Name }
curl.exe -s -X POST -H "Authorization: Bearer $fay" "$api/users/$boname/follow/" | ConvertFrom-Json | ConvertTo-Json -Compress
curl.exe -s -D - -o NUL -X POST -H "Authorization: Bearer $fay" "$api/users/$boname/follow/" | Select-String -Pattern "^(HTTP|retry-after)"
curl.exe -s -o NUL -w "reading profiles still works: %{http_code}`n" "$api/users/$boname/"
```

**You should see** (the seconds differ):

```text
1 account marked verified
     99 200
      1 201
      1 429
{"detail":"Request was throttled. Expected available in 3599 seconds.","code":"throttled"}
HTTP/1.1 429 Too Many Requests
Retry-After: 3599
reading profiles still works: 200
```

- 100 requests went through (the first made the follow, the other 99 were repeats), the 101st was refused with
  `429` and a `Retry-After` in seconds. The same limit applies to unfollowing, so someone can't flip a follow back
  and forth all day.
- A 401 (not logged in) or 403 (email not verified) doesn't use up the allowance.

#### Step 10: What a link preview or a search crawler sees

**Where:** Terminal window 2, with `runserver` (window 1) and `npm run dev` (window 3) running.

**What this does:** Asks the Next.js server for a profile page with no cookies and no JavaScript, the way a
crawler does, and picks out the head tags. The server reads the profile from Django itself.

```powershell
$page = curl.exe -s "http://localhost:3000/u/$boname" | Out-String
[regex]::Matches($page, '<title>[^<]*</title>|(property|name)="(og:title|og:description|og:type|og:image|twitter:image|twitter:card)" content="[^"]*"|rel="canonical" href="[^"]*"') | ForEach-Object { $_.Value } | Sort-Object -Unique
"---"
([regex]::Matches($page, "@$boname")).Count
curl.exe -s -o NUL -w "upper case: %{http_code} -> %{redirect_url}`n" "http://localhost:3000/u/$($boname.ToUpper())"
curl.exe -s -o NUL -w "no such user: %{http_code}`n" "http://localhost:3000/u/nobody_$id"
curl.exe -s -o NUL -w "not a username: %{http_code}`n" "http://localhost:3000/u/ab"
[regex]::Matches((curl.exe -s "http://localhost:3000/u/nobody_$id" | Out-String), 'name="robots" content="[^"]*"') | ForEach-Object { $_.Value } | Sort-Object -Unique
```

**You should see** (the first compile of the page in `next dev` takes a few seconds; the name and the count of
`@name` occurrences differ):

```text
name="twitter:card" content="summary_large_image"
name="twitter:image" content="http://localhost:3000/twitter-image.png"
property="og:description" content="Posts by @part6_bo_212733 on Rumor Zero."
property="og:image" content="http://localhost:3000/opengraph-image.png"
property="og:title" content="@part6_bo_212733 · Rumor Zero"
property="og:type" content="profile"
rel="canonical" href="http://localhost:3000/u/part6_bo_212733"
<title>@part6_bo_212733 · Rumor Zero</title>
---
     13 @part6_bo_212733
upper case: 307 -> http://localhost:3000/u/part6_bo_212733
no such user: 404
not a username: 404
name="robots" content="noindex"
```

- The title is `Display Name (@name)`, or `@name` when there is no display name (a new account has none). The
  description is the bio's first 160 characters, or "Posts by @name on Rumor Zero.". The share image is the
  site's static one, set again on this page because a page's own Open Graph tags replace the site-wide ones.
- `/u/NAME` in capitals answers `307` to the lower-case address, so there is one canonical URL. An unknown name,
  or one that can't be a username, is a real HTTP 404 with `noindex`. (The count of `@name` only has to be
  above zero: Next repeats it in the page and in its payload.)

#### Step 11: Django Admin lists the follows

**Where:** Browser, while `runserver` is running in window 1.

**What this does:** Opens the admin list of follows, which is read-only: changes only go through the follow
service, so the feed cache can't be left out of date.

| URL | Expect |
|---|---|
| http://localhost:8000/admin/ | Sign in with the superuser you made in Part 0A. If it 404s, `ADMIN_URL_PATH` in `backend\.env` isn't `admin/`; use that path. |
| http://localhost:8000/admin/social/follow/ | **Follows**: follower, following and created time, newest first, with a search box on the usernames. There is no **Add follow** button. |
| Click a follow | A page that only shows the values: no Save and no Delete (they answer 403 if you type the address). |

- Covered by `test_admin.py` (the list, the search, and 403 for add, change and delete); not opened by a person.

#### Step 12: A profile in the browser

**Where:** Browser, with `runserver` (window 1) and `npm run dev` (window 3) running. First give `bo` a name and a
bio (the Settings page arrives in Part 14), in window 2:

```powershell
python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(username='$boname').update(display_name='Bo Stone', bio='Climate reporter. I write about energy, rivers and trams.'), 'profile updated')" | Select-Object -Last 1
```

Then log in at http://localhost:3000/login as **`cy`**, with `part6-cy-<your id>@example.test` and
`correct-horse-battery-42` (the id from step 3).

**What this does:** Opens profiles, follows and unfollows, and uses the filter chips.

| Do this | Expect |
|---|---|
| Open `http://localhost:3000/u/part6_bo_<id>` (your id) | One white card: a round avatar with the initials **BS**, **Bo Stone** in large serif, `@part6_bo_<id>` under it in blue, the bio (two lines), `Joined <this month and year> · 4 posts`, and a pale panel with four counters: **3 FOLLOWERS**, **1 FOLLOWING**, **● 2 VERIFIED** (teal dot), **● 1 FALSE** (red dot). Top right of the card a white **Following** button (`cy` follows `bo` since step 6). No "Debunked" anywhere. |
| Below the card | Three chips **All** (dark), **Facts**, **Opinions**, then `bo`'s posts as cards, newest first: the new opinion from step 8, a FALSE 90% card (red edge), a VERIFIED 94% card (teal edge) and a CHECKING FACTS… card with its DOI row. No removed or deleted post, and not the tram opinion `bo` deleted. |
| Click **Facts** | The list reloads with only the three facts (the opinion is gone); **Facts** is dark. Click it again: back to **All**. |
| Hover the **Following** button | The word becomes **Unfollow** (the button keeps its width). Click it: it turns blue **Follow** at once and **3 FOLLOWERS** becomes **2**; click it again: **Following** and **3**. |
| Click **3 FOLLOWERS** | `/u/part6_bo_<id>/followers`: **← Back to Bo Stone (@part6_bo_<id>)**, tabs **FOLLOWERS 3** (underlined) and **FOLLOWING 1**, and three rows (`fay`, `cy`, `ada`): avatar, `@name`, a **Follow** button on `fay` and `ada`, **none on your own row** (`cy`). |
| Click **FOLLOWING 1** | `/u/part6_bo_<id>/following`: one row, `cy`, with no button (it is your own row). |
| Open `/u/part6_ada_<id>` and click **Follow** | **Following** at once, and the **FOLLOWERS** counter goes up by one. Click again: it goes back. |
| Open `/u/part6_cy_<id>` (yourself) | **Edit profile** (a button that goes to `/settings`, a placeholder until Part 14) instead of Follow. |
| Open `/u/PART6_BO_<id>` in capitals | The address changes to the lower-case one. |
| Open `/u/nobody_here` | The "Page not found" page. |
| Log out and open `/u/part6_bo_<id>` | The same profile with a blue **Follow** link; clicking it goes to the log-in page and back to the profile afterwards. |

- Verified and FALSE count `bo`'s deleted post too, so they can be higher than the verified posts listed (step 7).

#### Step 13: The Following tab on /home

**Where:** Browser, logged in as `cy`.

**What this does:** Uses the second tab of the home feed. Recent stays the first tab and the default.

| Do this | Expect |
|---|---|
| Open http://localhost:3000/home | Two tabs, **RECENT** (underlined) and **FOLLOWING**. Logged out there is only **RECENT**. Opening `/home` makes no request for Following yet (DevTools → Network). |
| Click **FOLLOWING** | `bo`'s posts and your own, newest first, with the same cards as Recent; **You're caught up.** at the end. One request, `/api/v1/feed/`. Click **RECENT** and **FOLLOWING** again: no new request. |
| Click **New post** and post an opinion | It appears at the top of the open tab, and in the other tab too, without a reload. |
| Open `/u/part6_bo_<id>`, click **Following** to unfollow `bo`, then open `/home` and **FOLLOWING** | Only your own posts: `bo`'s are gone at once (the cache is cleared when you unfollow). |
| Log in with a brand-new account (no posts, no follows) and open **FOLLOWING** | **Follow people to see their posts here** with a **See Recent** button; the button switches to **RECENT**. |
| On a post card, click the author's name or avatar | Their profile opens. Clicking the claim text or empty space on the card still opens the post. |

#### Step 14: A phone-sized window

**Where:** Browser, logged in as `cy`.

**What this does:** Checks the new pages at phone width. In Firefox or Chrome press `F12`, then the "responsive
design" / device toolbar button, and set the width to 390.

| Do this | Expect |
|---|---|
| Open a profile | A top bar with the logo and your avatar; the profile card with the avatar and name side by side, the **Follow** button **below** them (not squeezed beside), the counters in a 2 by 2 grid; the chips; the posts. A bottom bar (Home, Search, New post, Notifications, Profile). **No sideways scrolling.** |
| Open `/followers` | Rows with the name truncated if long and the **Follow** button at the right. |
| Open `/home` and **FOLLOWING** | The two tabs under the top bar, the cards with the author's name and handle on one line. |

#### Step 15: Stop and clean up

**Where:** Every terminal window, plus the browser.

- Stop the servers: `Ctrl+C` in windows 1 and 3 (a leftover `next dev`: step 12 of Part 1).
- Delete the test accounts, their posts and their follows (all go with the accounts). In window 2, in `backend\` with the
  venv active:

  ```powershell
  python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(email__startswith='part6-').delete())" | Select-Object -Last 1
  ```

  After one clean run of this guide it prints `(22, {'posts.Post': 8, 'social.Follow': 4, 'account.EmailAddress': 5, 'accounts.User': 5})`:
  how many rows went in all, and per table (8 posts: seven by `bo`, six in steps 3 and 7 and one in step 8, and one by `ada` in step 8; a deleted
  post is still a row). Your count differs if you did the browser steps (more posts and follows). Nothing else is touched.
  (The E2E tests' accounts stay in your local database, as in earlier parts: Django Admin → Users deletes them.)
- `docker compose down` (repo root) stops the containers and keeps the data; `docker compose down -v`
  wipes the whole local database, which is destructive.
- No secret was used or printed in this part: the only values in the commands are Cloudflare's public test
  token and the throwaway password of the test accounts.

### Part 7: Likes & comments

Needs Part 0A's containers and virtualenv, Part 0C's frontend, and your own `backend\.env` and
`frontend\.env.local`. Part 7 adds **one migration** (`social.0002_like_comment`: the likes and comments tables), **no
dependency** and **no new variable** (the `like` and `comment` rates were already in the settings). It adds the
endpoints `POST` and `DELETE /api/v1/posts/{id}/like/`, `GET` and `POST /api/v1/posts/{id}/comments/` and
`DELETE /api/v1/comments/{id}/`, and fills `like_count`, `comment_count` and `liked_by_me` in every post.

**Which terminal window for what.** Open the windows once and keep using the same ones:

| Window | What runs in it | Used in steps |
|---|---|---|
| Window 1 (server) | `python manage.py runserver` in `backend\`, venv active. Leave it running. Start it in step 3, **after** step 2 (Playwright starts its own servers and needs ports 3000 and 8000 free). | 3 to 16 |
| Window 2 (commands) | All the `curl.exe` and `python manage.py` commands. **Use the same window for steps 3 to 12**: the variables and functions you set in step 3 (`$id`, `$ada`, `$bo`, `$cy`, `$dee`, `$api`, `$op1`, `$fact1`, `Mk`, `Send`, `Fetch`, and the helpers steps 4 and 7 add) only live in that one terminal. If you close it, redo step 3. | 1 to 12, 17 |
| Window 3 (frontend) | `npm run dev` in `frontend\`. Leave it running. | 13 to 16 |
| Browser | Steps 13 to 16 | 13 to 16 |

Things to know first:

- Steps 3 to 12 talk to the API directly with `curl.exe` (with `.exe`: in PowerShell 5.1 plain `curl` is a different command). Steps 13 to 16 use the
  browser. Step 3 makes four accounts: `ada`, `bo` and `cy` are verified and `dee` never is. `bo` writes the
  posts, `ada` and `cy` like and comment, and `dee` shows what an unverified email may not do. Step 11 adds `eve` and
  `gus` for the two rate limits.
- **The PowerShell blocks below were not run on Windows.** The agent works on the Linux PC; it ran the bash twin of every command in the Linux guide on 2026-10-10, and the outputs below are those. The PowerShell commands follow the patterns Parts 1 to 6 proved on Windows (JSON written to a file and sent with `--data-binary "@file"`, `curl.exe`, no `&&`). Two differences are deliberate: the 500-emoji comment in step 7 is sent as JSON escapes (PowerShell 5.1 turns real emoji in a file into `?`), and step 11's 60 comments all carry the same text. If one behaves differently, tell the agent which.
- The API and page outputs below were recorded on Linux on 2026-10-10. The browser steps were checked the same
  day with headless Chromium (screenshots at 1280 and 390 px) and Django Admin with a scripted browser, not by a
  person at a keyboard. Ids, numbers in names, times and token prefixes differ on every run.
- Nothing here sends an email: step 3 marks the accounts verified with a shell command, which stands in for
  clicking the link (Part 2 shows the real flow). Steps 5, 9 and 10 set a post's status or hide a comment the same
  way, because the pipeline and the moderator tools that do it for real arrive in Parts 9 and 10 (step 16 uses
  the admin's own Hide action).
- **What Part 7 does and doesn't show:** likes and comments are allowed on every post the public can see
  (a fact that is still being checked included), never on a removed or deleted one; liking and commenting need a
  verified email, taking a like back or deleting your own comment only a login; a **hidden** comment (a
  moderator, in Django Admin) is in no list and no count, and deleting your own comment is a **soft delete**, so
  the row stays. Reposts and bookmarks (7B), reports (8) and notifications (13) come later.

#### Step 1: Run the automated backend checks

**Where:** Terminal window 2 (commands), starting in the repo root.

**What this does:** Starts the database containers, activates the Python environment, applies the new migration,
confirms there is no further one, then runs the whole backend test suite, the social tests, the linter and the
formatter check.

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero
docker compose up -d
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py migrate                            # Applying social.0002_like_comment... OK
python manage.py makemigrations --check --dry-run   # No changes detected
python manage.py check                              # System check identified no issues (0 silenced).
python -m pytest                                    # 1485 passed
python -m pytest apps/social -q                     # 305 passed
ruff check . ; ruff format --check .                # All checks passed! / 142 files already formatted
```

**You should see:** `Applying social.0002_like_comment... OK` (nothing to apply the second time), `No changes detected`
and `System check identified no issues (0 silenced).`, then the full run ends with `1485 passed`, the social run
with `305 passed`, and the last line pair is `All checks passed!` and `142 files already formatted`. (Counts may
grow later; what matters is that nothing fails.)

- The 145 new social tests: `test_models_engagement.py` (13: the unique like pair, a comment is 1 to 500 characters
  and an emoji is one, both indexes), `test_services_engagement.py` (26: idempotent like, who can like or comment
  on what, two simultaneous likes make one row, N simultaneous likes are all counted, two simultaneous deletes give
  one success), `test_api_like.py` (21, including the real 300-requests-an-hour limit), `test_api_comments.py` (22:
  oldest first, cursor walk, a comment arriving between pages, crafted cursors, constant query counts),
  `test_api_comment_create.py` (25, including the real 60-an-hour limit and that reading never uses it up),
  `test_api_comment_delete.py` (13), `test_engagement_counts.py` (11: real counts in Recent, the post page, a
  profile and the Following feed, also on a cache hit; constant queries), `test_admin_engagement.py` (13: Hide and
  Unhide, the permission, the admin log) and one more in `test_no_network.py`.
- Outside `apps/social`: the cursor check is tested for an oldest-first list too (`apps/core/tests/test_pagination.py`,
  4 new). `PostQuerySet.for_list(viewer)` now counts likes and comments, and `PostSerializer` refuses a post
  that was not counted (the 201 answer of a new post gets explicit zeros), so no list can show silent zeros.

#### Step 2: Run the automated frontend checks

**Where:** Terminal window 2, then `cd ..\frontend`. Playwright (the last two commands) starts Django and
Next itself, so **no servers may be running on ports 3000 and 8000** (it reuses them if they are, with
whatever settings they have).

**What this does:** Runs the linters, the type check, the component tests, the production build and the
end-to-end tests.

```powershell
cd ..\frontend                                      # from backend\
npm run lint ; npm run lint:tokens ; npm run typecheck ; npm run format:check
npm test                                            # 106 files, 1410 tests passed
npm run build
npm run test:e2e                                    # 32 passed
$env:CI = "1" ; npm run test:e2e ; Remove-Item Env:CI   # 32 passed (against the production build)
cd ..\backend                                       # back to backend\ for steps 3 to 12
```

**You should see:** the first line prints nothing from ESLint and TypeScript and ends with
`lint:tokens OK (…)` and `All matched files use Prettier code style!`. `npm test` ends with
`Test Files  106 passed (106)` and `Tests  1410 passed (1410)`. `npm run build` lists the same routes as in Part 6
(Part 7 adds no page: the discussion is part of `/p/[id]`). Each E2E run ends with `32 passed`: the 29 earlier tests
and 3 new ones in `e2e/social.spec.ts`.

- The new E2E tests reuse the two people that file already signs up (allauth limits sign-ups to 20 a minute per
  address and the rest of the suite already uses most of that), so Part 7 adds **no** sign-up. They are: B likes
  A's post from the feed (the heart fills and the count moves at once, the like survives a reload, A sees one like
  that isn't theirs), B opens the post, comments with Ctrl+Enter, A sees the comment with no Delete button, B
  deletes it after a confirmation and takes the like back; a visitor sees the counts and is sent to log in; and the
  post page with its discussion fits a phone with no sideways scroll.
- `posts.spec.ts` now expects three links on a card (the author, the claim and the comment count).

- On Windows `npm run build` can't blank `NEXT_PUBLIC_GOOGLE_CLIENT_ID` (PowerShell's `$env:NAME = ""` *deletes* the
  variable), so a `frontend\.env.local` with your real client ID is baked into that build and the CI-mode run is less
  representative than on Linux. The default run pins an empty client ID for both servers, so it is unaffected.

#### Step 3: Start the servers and make four accounts and two posts

**Where:** First window 1 (the Django server) and window 3 (the frontend), then window 2 (the commands).
**Keep using window 2 for steps 4 to 12.**

**What this does:** Windows 1 and 3 run the two servers. In window 2 you sign up four accounts through the API and
mark three of them verified (`dee` stays unverified), then `bo` posts an opinion and a fact with a DOI. The helpers
`Mk` (make a post, print its id), `Send` (any request, printing the status code and then the answer) and `Fetch` (the same for a GET) are used by every later step.

Window 1 (in `backend\`, venv active):

```powershell
python manage.py runserver                          # leave it running
```

Window 3:

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero\frontend
npm run dev                                         # leave it running
```

Window 2 (in `backend\` with the venv active: steps 1 and 2 leave you there). If you opened a new
terminal, first run `cd C:\Users\Nafis\Downloads\Rumor-Zero\backend` and `.\.venv\Scripts\Activate.ps1`:

```powershell
$id = Get-Date -Format "HHmmss"                     # a unique suffix so the addresses are new each run
$h = '-H', 'Origin: http://localhost:3000', '-H', 'X-Requested-With: rumor-zero'   # headers every auth call needs
function Signup($email, $username) {
@"
{"email": "$email", "username": "$username", "password": "correct-horse-battery-42", "turnstile_token": "XXXX.DUMMY.TOKEN.XXXX"}
"@ | Set-Content -Encoding ascii $env:TEMP\rz-signup.json
  (curl.exe -s @h -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-signup.json" http://localhost:8000/api/auth/app/v1/auth/signup | ConvertFrom-Json).meta.access_token
}
$ada = Signup "part7-ada-$id@example.test" "part7_ada_$id"      # $ada = ada's login token (likes and comments)
$bo = Signup "part7-bo-$id@example.test" "part7_bo_$id"         # $bo = bo's login token (the author of the posts)
$cy = Signup "part7-cy-$id@example.test" "part7_cy_$id"         # $cy = cy's login token (kept for the browser)
$dee = Signup "part7-dee-$id@example.test" "part7_dee_$id"      # $dee = dee's login token (never verified)
python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(email__startswith='part7-', email__endswith='$id@example.test').exclude(username='part7_dee_$id').update(is_email_verified=True), 'accounts marked verified')" | Select-Object -Last 1
$api = 'http://localhost:8000/api/v1'
$adaname = "part7_ada_$id"; $boname = "part7_bo_$id"; $cyname = "part7_cy_$id"; $deename = "part7_dee_$id"
# Mk <token> <json>: makes a post, prints its id
function Mk($token, $json) {
  $json | Set-Content -Encoding ascii $env:TEMP\rz-post.json
  (curl.exe -s -H "Authorization: Bearer $token" -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-post.json" "$api/posts/" | ConvertFrom-Json).id
}
# Send <METHOD> <path> [token] [json body] [fields]: prints the HTTP status, then the answer. `fields` is a list
# of property names to keep, or a script block `{ param($r) ... }` that picks what to show from the answer.
function Send($method, $path, $token, $json, $show) {
  $a = @()
  if ($token) { $a += '-H', "Authorization: Bearer $token" }
  if ($json) {
    $json | Set-Content -Encoding ascii $env:TEMP\rz-body.json
    $a += '-H', 'Content-Type: application/json', '--data-binary', "@$env:TEMP\rz-body.json"
  }
  $out = curl.exe -s -w "`n%{http_code}" -X $method @a "$api$path"
  $body = if ($out.Count -gt 1) { $out[0..($out.Count - 2)] -join '' } else { '' }
  if ($show -and $body) {
    $r = $body | ConvertFrom-Json
    $shown = if ($show -is [scriptblock]) { & $show $r } else { $r | Select-Object $show }
    $body = ConvertTo-Json -InputObject $shown -Depth 5 -Compress
  }
  "$($out[-1])  $body"
}
function Fetch($path, $token, $show) { Send GET $path $token $null $show }   # Fetch <path> [token] [fields]
$op1 = Mk $bo '{"content":"I think the new tram line will change how the city moves.","post_type":"opinion"}'
$fact1 = Mk $bo '{"content":"Solar capacity grew by roughly 30% worldwide last year.","post_type":"fact","sources":["doi:10.1038/s41558-024-02102"]}'
"$($ada.Substring(0,10)) $($bo.Substring(0,10)) $($cy.Substring(0,10)) $($dee.Substring(0,10))"      # four prefixes, not an error
"op1=$op1"; "fact1=$fact1"                                                  # two ids, not empty
```

**You should see** (the number in the names is your `id`, and the ids differ):

```text
3 accounts marked verified
eyJhbGciOi eyJhbGciOi eyJhbGciOi eyJhbGciOi
op1=c4cd330c-ef91-4ef8-a888-f016ae6e4905
fact1=ba591060-ab33-405d-b077-0ef99a789ebe
```

- The shell prints a line about auto-imported objects first; `Select-Object -Last 1` keeps only ours.
- Sign-up is limited to 20 a minute per address (Part 1), and still calls Cloudflare's test widget, so it
  needs internet.

**If it differs:** an empty token or an `id` of `null` means the sign-up or the post failed: `runserver` isn't
running, or you signed up more than 20 times in a minute. Fix that and run this step again
from `$id = Get-Date …`.

#### Step 4: Like and unlike

**Where:** Terminal window 2 (the same terminal as step 3).

**What this does:** Likes and unlikes through `POST` and `DELETE /api/v1/posts/{id}/like/`, with every refusal.
Both are idempotent. Liking needs a verified email, taking a like back only a login.

```powershell
function Like($post, $token) { Send POST "/posts/$post/like/" $token }          # Like <post id> [token]
function Unlike($post, $token) { Send DELETE "/posts/$post/like/" $token }       # Unlike <post id> [token]
Like $op1 $ada                                      # 1: the first like is 201
Like $op1 $ada                                      # 2: again: 200, nothing changes
Like $op1                                           # 3: nobody logged in
Like $op1 $dee                                      # 4: an unverified email
Like $op1 $bo                                       # 5: your own post is fine
Like $fact1 $ada                                    # 6: a fact that is still "checking" can be liked
Like 00000000-0000-4000-8000-000000000000 $ada      # 7: no such post
Like not-a-uuid $ada                                # 8: not even an id
Unlike $op1 $bo                                     # 9: taking your like back is 204
Unlike $op1 $bo                                     # 10: and again: still 204, no error
Unlike $op1 $dee                                    # 11: an unverified user may also take one back (there is none): 204
```

**You should see** (eleven commands, eleven answers):

```text
201  {"liked":true}
200  {"liked":true}
401  {"detail":"Authentication credentials were not provided.","code":"not_authenticated"}
403  {"detail":"Verify your email address first. Check your inbox for the link.","code":"email_unverified"}
201  {"liked":true}
201  {"liked":true}
404  {"detail":"Not found.","code":"not_found"}
404  {"detail":"Not found.","code":"not_found"}
204
204
204
```

- The first like is `201`, the same request again is `200` and changes nothing; `DELETE` is `204` every
  time, also when there was nothing to take back (10, 11). A user can like their own post (5).
- A fact post still labelled "checking facts" can be liked (6), like an opinion or a post under review: only a
  removed or deleted post can't (step 5). An unknown or malformed id is the same JSON 404 (7, 8), never an HTML page.
- A 401 or 403 doesn't use up the allowance of 300 likes an hour (step 11).

#### Step 5: Removed and deleted posts

**Where:** Terminal window 2.

**What this does:** Makes two more posts, one a moderator removes (set with a shell command: the moderator tools
come in Part 10) and one its author deletes, and shows that neither can be liked.

```powershell
$op2 = Mk $bo '{"content":"This opinion will be removed by a moderator.","post_type":"opinion"}'
python manage.py shell -c "from apps.posts.models import Post; print(Post.objects.filter(pk='$op2').update(status='removed'), 'post removed')" | Select-Object -Last 1
$op3 = Mk $bo '{"content":"This opinion will be deleted by its author.","post_type":"opinion"}'
Send DELETE "/posts/$op3/" $bo                      # bo deletes op3: 204
Like $op2 $ada                                      # 1: a removed post can't be liked
Like $op3 $ada                                      # 2: a deleted post can't either
python manage.py shell -c "from apps.social.models import Like; from apps.accounts.models import User; Like.objects.create(user=User.objects.get(username='$adaname'), post_id='$op2'); print(Like.objects.filter(post_id='$op2').count(), 'like row planted on the removed post')" | Select-Object -Last 1
Unlike $op2 $ada                                    # 3: ...but a like can still be taken back from it: 204
python manage.py shell -c "from apps.social.models import Like; print(Like.objects.filter(post_id='$op2').count(), 'like rows left on it')" | Select-Object -Last 1
Unlike $op3 $ada                                    # 4: a deleted post is 404 even for that
```

**You should see:**

```text
1 post removed
204
404  {"detail":"Not found.","code":"not_found"}
404  {"detail":"Not found.","code":"not_found"}
1 like row planted on the removed post
204
0 like rows left on it
404  {"detail":"Not found.","code":"not_found"}
```

- `post removed` is the shell command; `204` is `bo` deleting `op3`; then the two refusals (1, 2) are plain
  `404`s, the same answer as for a post that never existed, so nothing says whether a post once existed.
- A like that was already on a post can always be taken back, even if the post was removed meanwhile (3 to
  the `0 like rows left` line), but a deleted post is `404` for that too (4).

#### Step 6: The counts on every post

**Where:** Terminal window 2.

**What this does:** Reads `like_count`, `comment_count` and `liked_by_me` as nobody and as other people, on the post
page and in three lists. The counts are counted in the same query as the posts, so a list of 20 posts costs the same
number of queries as a list of 2. The last three commands show the Following feed, whose first page is cached for
30 seconds as a list of ids only: a new like still shows at once.

```powershell
$counts = @('like_count', 'comment_count', 'liked_by_me')
$cards = { param($r) @($r.results | ForEach-Object { $p = if ($_.post) { $_.post } else { $_ }; [pscustomobject]@{ content = $p.content.Substring(0, 24); like_count = $p.like_count; liked_by_me = $p.liked_by_me } }) }
$feedCards = { param($r) @($r.results | Select-Object -First 2 | ForEach-Object { [pscustomobject]@{ content = $_.post.content.Substring(0, 24); like_count = $_.post.like_count } }) }
Fetch "/posts/$op1/" $null $counts                  # 1: a visitor: ada's like counts, "mine" is false
Fetch "/posts/$op1/" $ada $counts                   # 2: ada: she liked it
Fetch "/posts/$op1/" $cy $counts                    # 3: cy: someone else liked it, he didn't
Fetch "/posts/?page_size=2" $ada $cards             # 4: the Recent feed: the same numbers
Fetch "/users/$boname/posts/?page_size=2" $ada $cards   # 5: bo's profile posts
Send POST "/users/$boname/follow/" $ada             # 6: ada follows bo, so the Following feed has bo's posts
Fetch "/feed/" $ada $feedCards                      # 7: the Following feed: page 1 is now cached (ids only)
Like $op1 $cy                                       # 8: one more like arrives
Fetch "/feed/" $ada $feedCards                      # 9: still cached, but the count is fresh
```

**You should see:**

```text
200  {"like_count":1,"comment_count":0,"liked_by_me":false}
200  {"like_count":1,"comment_count":0,"liked_by_me":true}
200  {"like_count":1,"comment_count":0,"liked_by_me":false}
200  [{"content":"Solar capacity grew by r","like_count":1,"liked_by_me":true},{"content":"I think the new tram lin","like_count":1,"liked_by_me":true}]
200  [{"content":"Solar capacity grew by r","like_count":1,"liked_by_me":true},{"content":"I think the new tram lin","like_count":1,"liked_by_me":true}]
201  {"is_following":true}
200  [{"content":"Solar capacity grew by r","like_count":1},{"content":"I think the new tram lin","like_count":1}]
201  {"liked":true}
200  [{"content":"Solar capacity grew by r","like_count":1},{"content":"I think the new tram lin","like_count":2}]
```

- `liked_by_me` is `false` for a visitor and for everyone who didn't like the post (1, 3), `true` for `ada` (2).
  `like_count` is the same for everyone.
- Lines 4 and 5 list the two newest posts, the fact and the opinion `bo` made in step 3 (the removed and the deleted
  one are left out): both show `ada`'s like. Hidden and deleted comments are never counted in `comment_count`
  (step 10).
- Line 7 is the Following feed, now cached for `ada`; line 9 is the same page a moment later: the cache keeps the
  post ids, not the posts, so the count rose from 1 to 2.

#### Step 7: Write comments

**Where:** Terminal window 2.

**What this does:** Writes comments through `POST /api/v1/posts/{id}/comments/` and tries everything that is
refused. A comment is 1 to 500 characters (an emoji counts as one), trimmed, and needs a verified email.

```powershell
# Comment <post id> <token> <text> [fields]: the text goes into the JSON for you
function Comment($post, $token, $text, $show) { Send POST "/posts/$post/comments/" $token (@{ content = $text } | ConvertTo-Json -Compress) $show }
Comment $op1 $ada "  A fair point.  " { param($r) [pscustomobject]@{ content = $r.content; is_mine = $r.is_mine; author = $r.author.username; keys = @($r.PSObject.Properties.Name | Sort-Object) } }   # 1: 201, the text is trimmed
Comment $op1 $bo "Thanks, ada." @('content', 'is_mine')        # 2: the post's own author may comment
Comment $op1 $cy "Third." { param($r) $r.content }              # 3: a third comment
Comment $op1 $null "Hi"                             # 4: nobody logged in
Comment $op1 $dee "Hi"                              # 5: an unverified email
Comment $op1 $ada ""                                # 6: nothing written
Comment $op1 $ada "   "                             # 7: only spaces
Comment $op1 $ada ('x' * 501)                       # 8: 501 characters
# 9: 500 emoji = 500 characters: fine, on a fact still being checked. Sent as JSON escapes (ASCII), because PowerShell 5.1 would turn real emoji in a file into "?".
Send POST "/posts/$fact1/comments/" $ada ('{"content":"' + ('\ud83d\ude00' * 500) + '"}') { param($r) (New-Object System.Globalization.StringInfo $r.content).LengthInTextElements }
Comment $op2 $ada "Hi"                              # 10: a removed post has no discussion
Comment 00000000-0000-4000-8000-000000000000 $ada "Hi"     # 11: no such post
```

**You should see** (eleven commands, eleven answers):

```text
201  {"content":"A fair point.","is_mine":true,"author":"part7_ada_190101","keys":["author","content","created_at","id","is_mine"]}
201  {"content":"Thanks, ada.","is_mine":true}
201  "Third."
401  {"detail":"Authentication credentials were not provided.","code":"not_authenticated"}
403  {"detail":"Verify your email address first. Check your inbox for the link.","code":"email_unverified"}
400  {"content":["Write something first."]}
400  {"content":["Write something first."]}
400  {"content":["Keep it to 500 characters."]}
201  500
404  {"detail":"Not found.","code":"not_found"}
404  {"detail":"Not found.","code":"not_found"}
```

- A comment has exactly five keys: `id`, `author`, `content`, `is_mine` and `created_at`. Nothing about moderation
  ever shows. The spaces around the text are gone (1).
- `400` answers come per field in the same words as a post's: "Write something first." for nothing or only
  spaces (6, 7) and "Keep it to 500 characters." for 501 (8). 500 emoji is 500 characters, not 1000 (9).
- The refusals for nobody logged in, an unverified email, a removed post and no such post are the same as for likes.

#### Step 8: Read the comments

**Where:** Terminal window 2.

**What this does:** Reads `GET /api/v1/posts/{id}/comments/`: public, **oldest first**, 20 to a page (`?page_size=`
up to 50), with a cursor to carry on.

```powershell
$list = { param($r) [pscustomobject]@{ order = @($r.results | ForEach-Object content); keys = @($r.results[0].PSObject.Properties.Name | Sort-Object); next_cursor = $r.next_cursor } }
$mine = { param($r) @($r.results | ForEach-Object { [pscustomobject]@{ content = $_.content; is_mine = $_.is_mine } }) }
Fetch "/posts/$op1/comments/" $null $list                                  # 1: anyone can read; oldest first
Fetch "/posts/$op1/comments/" $ada $mine                                   # 2: ada's own comment says so
$cur = (curl.exe -s "$api/posts/$op1/comments/?page_size=2" | ConvertFrom-Json).next_cursor
Fetch "/posts/$op1/comments/?page_size=2" $null { param($r) @($r.results | ForEach-Object content) + @([bool]$r.next_cursor) }                    # 3: a page of two, and a way on
Fetch "/posts/$op1/comments/?page_size=2&cursor=$cur" $null { param($r) @($r.results | ForEach-Object content) + @($r.next_cursor) }                # 4: the last one, then no cursor
Fetch "/posts/$op1/comments/?cursor=cD1ub3QtYS1kYXRl"                      # 5: a made-up cursor
Fetch "/posts/$op2/comments/"                                              # 6: removed post
Fetch "/posts/$op3/comments/"                                              # 7: deleted post
Fetch "/posts/$op1/" $null @('comment_count', 'like_count')                # 8: the counts on the post
```

**You should see** (eight commands, eight answers):

```text
200  {"order":["A fair point.","Thanks, ada.","Third."],"keys":["author","content","created_at","id","is_mine"],"next_cursor":null}
200  [{"content":"A fair point.","is_mine":true},{"content":"Thanks, ada.","is_mine":false},{"content":"Third.","is_mine":false}]
200  ["A fair point.","Thanks, ada.",true]
200  ["Third.",null]
404  {"detail":"Invalid cursor","code":"not_found"}
404  {"detail":"Not found.","code":"not_found"}
404  {"detail":"Not found.","code":"not_found"}
200  {"comment_count":3,"like_count":2}
```

- Anyone can read (1). The order is the order they were written. Only `ada`'s own comment says `is_mine: true`
  when she asks (2).
- Line 3 is a page of two and `true`: there is more; line 4 follows the cursor and gets the last comment, then
  `null`. A comment that arrives between two pages is neither skipped nor repeated (a test covers it).
- A made-up cursor is a clean `404 "Invalid cursor"`, never a server error. A removed or deleted post has no
  comment list at all (6, 7), not even for its author.

#### Step 9: Delete your own comment

**Where:** Terminal window 2.

**What this does:** Deletes a comment through `DELETE /api/v1/comments/{id}/`. It is a **soft delete**: the comment
leaves every list and count, but the row stays in the database (the last command shows it).

```powershell
$cid = ((curl.exe -s "$api/posts/$op1/comments/") | ConvertFrom-Json).results[1].id    # bo's comment (the second one)
Send DELETE "/comments/$cid/"                       # 1: nobody logged in
Send DELETE "/comments/$cid/" $ada                  # 2: someone else's comment
Send DELETE "/comments/$cid/" $bo                   # 3: its author: 204
Send DELETE "/comments/$cid/" $bo                   # 4: again: it is gone, 404
Fetch "/posts/$op1/" $null @('comment_count')       # 5: the count dropped
Fetch "/posts/$op1/comments/" $null { param($r) @($r.results | ForEach-Object content) }   # 6: and so did the list
python manage.py shell -c "from apps.social.models import Comment; c = Comment.objects.get(pk='$cid'); print(repr(c.content), '| deleted_at set:', c.deleted_at is not None, '| hidden:', c.is_hidden)" | Select-Object -Last 1   # 7: the row is still there
```

**You should see:**

```text
401  {"detail":"Authentication credentials were not provided.","code":"not_authenticated"}
403  {"detail":"Only the author can do that.","code":"not_author"}
204
404  {"detail":"Not found.","code":"not_found"}
200  {"comment_count":2}
200  ["A fair point.","Third."]
'Thanks, ada.' | deleted_at set: True | hidden: False
```

- Only the author can delete: someone else gets `403 not_author` (2), and so does the author of the *post*.
  Deleting needs no verified email. The second delete is `404` (4), as for posts.
- The count and the list lose the comment at once (5, 6), and the row is still there with `deleted_at` set (7),
  like a deleted post.

#### Step 10: What a moderator's Hide does

**Where:** Terminal window 2.

**What this does:** Hides one comment with a shell command, which is what the admin's **Hide** action does (step 16
uses the real one), and shows that a hidden comment is gone for everyone, its author included, and not counted.

```powershell
$aid = ((curl.exe -s "$api/posts/$op1/comments/") | ConvertFrom-Json).results[0].id    # ada's comment (now the first)
$texts = { param($r) @($r.results | ForEach-Object content) }
python manage.py shell -c "from apps.social.models import Comment; print(Comment.objects.filter(pk='$aid').update(is_hidden=True), 'comment hidden')" | Select-Object -Last 1   # what the admin's Hide action does
Fetch "/posts/$op1/comments/" $ada $texts           # 1: gone from the list, even for its own author
Fetch "/posts/$op1/" $null @('comment_count')       # 2: and not counted
Send DELETE "/comments/$aid/" $ada                  # 3: its author can't delete it any more
python manage.py shell -c "from apps.social.models import Comment; print(Comment.objects.filter(pk='$aid').update(is_hidden=False), 'comment unhidden')" | Select-Object -Last 1   # Unhide
Fetch "/posts/$op1/comments/" $null $texts          # 4: back in its place
Fetch "/posts/$op1/" $null @('comment_count')       # 5: and counted again
```

**You should see:**

```text
1 comment hidden
200  ["Third."]
200  {"comment_count":1}
404  {"detail":"Not found.","code":"not_found"}
1 comment unhidden
200  ["A fair point.","Third."]
200  {"comment_count":2}
```

- Hidden means in no list and no count, for everyone (1, 2); staff see it only in Django Admin. Its author
  can't delete it any more (3): to them it no longer exists.
- Unhiding puts it back in its place, and the count goes back up (4, 5).

#### Step 11: Liking and commenting are rate limited

**Where:** Terminal window 2.

**What this does:** Makes two more verified accounts and a post, then uses up their allowances: 300 likes an hour
(`POST` and `DELETE` share it) and 60 comments an hour (only `POST` counts; reading never does).

```powershell
$eve = Signup "part7-eve-$id@example.test" "part7_eve_$id"      # $eve = a fresh account for the like limit
$gus = Signup "part7-gus-$id@example.test" "part7_gus_$id"      # $gus = a fresh account for the comment limit
python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(email__in=['part7-eve-$id@example.test', 'part7-gus-$id@example.test']).update(is_email_verified=True), 'accounts marked verified')" | Select-Object -Last 1
$op4 = Mk $bo '{"content":"A post for the limits to chew on.","post_type":"opinion"}'
1..300 | ForEach-Object { curl.exe -s -o NUL -w "%{http_code}`n" -X POST -H "Authorization: Bearer $eve" "$api/posts/$op4/like/" } | Group-Object | Sort-Object Name | ForEach-Object { "{0,7} {1}" -f $_.Count, $_.Name }   # 300 likes of one post
curl.exe -s -i -X POST -H "Authorization: Bearer $eve" "$api/posts/$op4/like/" | Select-String -Pattern 'HTTP/[0-9.]+ [0-9]+|retry-after: [0-9]+|"code":"[a-z_]+"' -AllMatches | ForEach-Object { $_.Matches.Value }   # the 301st
'{"content":"Limit test"}' | Set-Content -Encoding ascii $env:TEMP\rz-limit.json
1..60 | ForEach-Object { curl.exe -s -o NUL -w "%{http_code}`n" -H "Authorization: Bearer $gus" -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-limit.json" "$api/posts/$op4/comments/" } | Group-Object | Sort-Object Name | ForEach-Object { "{0,7} {1}" -f $_.Count, $_.Name }   # 60 comments
curl.exe -s -i -H "Authorization: Bearer $gus" -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-limit.json" "$api/posts/$op4/comments/" | Select-String -Pattern 'HTTP/[0-9.]+ [0-9]+|retry-after: [0-9]+|"code":"[a-z_]+"' -AllMatches | ForEach-Object { $_.Matches.Value }   # the 61st
Fetch "/posts/$op4/comments/" $gus { param($r) [pscustomobject]@{ n = @($r.results).Count } }   # reading is never throttled
```

**You should see** (the seconds differ):

```text
2 accounts marked verified
    299 200
      1 201
HTTP/1.1 429
Retry-After: 3597
"code":"throttled"
     60 201
HTTP/1.1 429
Retry-After: 3600
"code":"throttled"
200  {"n":20}
```

- 300 requests went through (the first made the like, the other 299 were repeats), the 301st was refused with `429`,
  `"code":"throttled"` and a `Retry-After` in seconds. Likewise 60 comments, then the 61st.
- A 401 or 403 doesn't use up an allowance, but a `400` for a bad comment does (tests cover both).
- Reading the comments still works while the comment allowance is spent: the last answer shows the page of 20.

#### Step 12: The indexes are used

**Where:** Terminal window 2.

**What this does:** In a transaction that is thrown away at the end, makes 300 users, 2,000 posts, 40,000 comments and
30,000 likes, asks the database how it would run the three queries behind every card and prints the plan lines. Nothing is
saved.

```powershell
@'
from datetime import timedelta
from django.db import connection, transaction
from django.utils import timezone
from apps.accounts.models import User
from apps.posts.models import Post
from apps.social.models import Comment, Like

class Rollback(Exception):
    pass

try:
    with transaction.atomic():   # everything below is thrown away at the end
        users = User.objects.bulk_create([User(username=f"xp_{i:03d}", email=f"xp{i}@example.test") for i in range(300)])
        now = timezone.now()
        posts = Post.objects.bulk_create([Post(author=users[i % 300], content=f"p{i}", post_type="opinion", status="published", created_at=now - timedelta(seconds=i)) for i in range(2000)])
        Comment.objects.bulk_create([Comment(post=posts[n % 200], author=users[n % 300], content="c", created_at=now - timedelta(seconds=n), is_hidden=(n % 50 == 0), deleted_at=(now if n % 70 == 0 else None)) for n in range(40000)])
        Like.objects.bulk_create([Like(user=users[n % 300], post=posts[(n // 300) % 2000]) for n in range(30000)], ignore_conflicts=True)
        with connection.cursor() as c:
            for table in ("social_comment", "social_like", "posts_post"):
                c.execute(f"ANALYZE {table}")
            target = str(posts[7].pk)
            for label, sql in {
                "--- comment list, first page": "SELECT id FROM social_comment WHERE post_id = %s AND NOT is_hidden AND deleted_at IS NULL ORDER BY created_at, id LIMIT 21",
                "--- comment count": "SELECT COUNT(*) FROM social_comment WHERE post_id = %s AND NOT is_hidden AND deleted_at IS NULL",
                "--- like count": "SELECT COUNT(*) FROM social_like WHERE post_id = %s",
            }.items():
                c.execute("EXPLAIN " + sql, [target])
                print(label)
                for row in c.fetchall():
                    print(row[0])
        raise Rollback
except Rollback:
    print("rolled back: nothing was saved")
'@ | python manage.py shell 2>&1 | Select-String -Pattern '^---|Scan|rolled back' | ForEach-Object { $_.Line }
```

**You should see** (the cost numbers differ a little):

```text
--- comment list, first page
  ->  Index Only Scan using comments_post_visible_idx on social_comment  (cost=0.41..595.39 rows=170 width=24)
--- comment count
  ->  Bitmap Heap Scan on social_comment  (cost=17.73..353.09 rows=170 width=0)
        ->  Bitmap Index Scan on comments_post_visible_idx  (cost=0.00..17.69 rows=170 width=0)
--- like count
  ->  Bitmap Heap Scan on social_like  (cost=22.61..319.28 rows=300 width=0)
        ->  Bitmap Index Scan on likes_post_created_idx  (cost=0.00..22.54 rows=300 width=0)
rolled back: nothing was saved
```

- The comment list reads `comments_post_visible_idx` straight in order (an index-only scan): that index only holds
  comments that are shown (not hidden, not deleted), and the count uses it too. The like count uses
  `likes_post_created_idx`.
- Each post card counts its own likes and comments with these two queries; a count costs about as many index entries
  as the post has comments, which is fine for now. (A post with many thousands of likes would want a stored counter:
  recorded for Part 16.)

#### Step 13: Likes on the cards

**Where:** Browser, with `runserver` (window 1) and `npm run dev` (window 3) running. Log in at
http://localhost:3000/login as `part7-cy-<id>@example.test` (use the `$id` from step 3) with the password `correct-horse-battery-42` (`cy` was verified in step 3).

**What this does:** Looks at the like and comment buttons on the Recent feed, as three kinds of visitor.

| Do this | Expect |
|---|---|
| Open http://localhost:3000/home and look at the posts `bo` made | Every card ends with a hairline and two small buttons: a **heart** with the like count and a **speech bubble** with the comment count. The solar fact card shows `1` and `1`; "A post for the limits to chew on." shows `1` and `60` (step 11); the tram opinion shows a **filled blue heart** and `2` (`cy` liked it in step 6) and `2` comments. Counts of 1,000 and more print as `1.4K`. |
| Click the filled heart on the tram card | It turns into an outline heart and the count goes `2` to `1` **at once**, before the server answers. Click again: filled, `2`. |
| Press `Tab` until a heart has the focus, then `Enter` or `Space` | The same toggle. A focused button has a thin blue ring. |
| Reload the page | The heart and the numbers are what the server says: the state survived. |
| Click the speech bubble | The post's own page opens, scrolled to the **Comments** section (`/p/<id>#comments`). Clicking the claim text opens the same page from the top. |
| Open a private window and go to /home (a visitor) | The same cards with the same counts. The hearts are **links**: they point to `/login?next=%2Fp%2F<id>`, and after you log in you land on that post's page. |
| In another window log in as `dee` (`part7-dee-<id>@example.test`, same password: never verified) and click a heart | The heart looks dimmed and nothing is sent; a toast says "Verify your email to like posts. Check your inbox for the link." |

- Covered by `LikeButton.test.tsx` (flip before the answer, rollback and toast on every kind of failure, one
  request for two clicks in one tick, all four visitor states) and the new E2E tests.
- The heart on a card is always above the card's big invisible link, so it never opens the post by accident.

#### Step 14: The discussion on a post's page

**Where:** Browser, logged in as `cy`, with both servers running.

**What this does:** Opens the tram post and uses the Comments section.

| Do this | Expect |
|---|---|
| Open the tram post (click its text on /home) and scroll below the verdict | The heading **Comments (2)** with OLDEST FIRST at the right, a box "Add a comment…" with `0 / 500 characters`, the hint "Ctrl + Enter to post" and a blue **Comment** button; below it `ada`'s "A fair point." and then `cy`'s "Third.". Only `cy`'s own comment has a small **DELETE**. (`bo`'s was deleted in step 9.) |
| Look at the row next to **Copy link** | The heart and the speech bubble with the words "Like" and "Comments" beside their counts (the words show from 640 px up). Clicking "Comments" jumps down to the section. |
| Type a line (the counter moves), then press `Ctrl+Enter` (`Cmd+Enter` on a Mac) | Your comment appears at the **end** of the list with "now", the heading says **Comments (3)**, the box is empty and keeps the focus, and a toast says "Comment posted." |
| Click **Comment** with the box empty, or only spaces | "Write something first." under the box; nothing is sent. |
| Paste a text of 501 characters, then click **Comment** | The counter turns red (`501 / 500 characters`) and the message is "Keep it to 500 characters."; nothing is sent. |
| Click **DELETE** under your own comment | A dialog "Delete this comment?" says "It disappears from the discussion right away. This can't be undone." **Cancel** closes it and nothing happens. **Delete comment** removes the row, the heading goes back to **Comments (2)** and a toast says "Comment deleted." |
| Open the same page in a private window (a visitor) | The comments are readable, there is no box, and a link says "Log in to comment" (to join the discussion). |
| Log in as `dee` (unverified) and open the page | The box is greyed out and locked, with the note "Verify your email to comment." |
| Open a removed post's page (not available from the UI: try `/p/<op2>`) | The tombstone with no discussion at all, for anyone, its author too. |

- Covered by `CommentComposer.test.tsx`, `CommentSection.test.tsx` (including the StrictMode case that once hid
  the author's Delete button on posts), `CommentList.test.tsx`, `DeleteCommentModal.test.tsx` and the E2E tests.
- The comments are fetched by the page after it loads (not server-rendered): `curl` of `/p/<id>` still gets the
  claim, the tags and the counts, but not the comment texts.

#### Step 15: A phone-sized window

**Where:** Browser, logged in as `cy`.

**What this does:** Checks the new parts at phone width. In Firefox or Chrome press `F12`, then the "responsive
design" / device toolbar button, and set the width to 390.

| Do this | Expect |
|---|---|
| Open /home | Each card's bar (heart, count, bubble, count) fits on one line under the claim. **No sideways scrolling.** |
| Open a post's page | The claim card's action row holds the heart and the speech bubble with their counts only (the words are hidden below 640 px) and **Copy link** beside them; the comment box is full width with the counter under it and the **Comment** button at the right; each comment is a card with the name, the time, the text and **DELETE**. |
| Type 300 characters into the box | Still **no sideways scrolling.** |

- Measured with headless Chromium at 390 px: 0 px of horizontal overflow on `/home`, on a post's page and with 300
  characters typed.

#### Step 16: Django Admin hides and unhides comments

**Where:** Browser, while `runserver` is running in window 1.

**What this does:** Opens the admin list of comments and uses the two new actions, the way a moderator will.

| URL / action | Expect |
|---|---|
| http://localhost:8000/admin/ | Sign in with the superuser you made in Part 0A. If it 404s, `ADMIN_URL_PATH` in `backend\.env` isn't `admin/`; use that path. |
| http://localhost:8000/admin/social/comment/ | **Comments**: the text (shortened), author, post, **Is hidden**, **Deleted at** and **Created at**, newest first, with a search box (text and username), the filters **By is hidden**, **By deleted at** and **By created at**, and the **Action** menu with "Hide selected comments" and "Unhide selected comments". There is no **Add comment** button. The comments you deleted in the browser are there with a date in **Deleted at**: the rows survived. |
| Click a comment | A page that only shows the values: no Save and no Delete (they answer 403 if you type the address). |
| Tick one comment of the tram post, choose **Hide selected comments**, click **Go** | A banner says "Hidden: 1 comment." Reload the tram post's page: the comment is gone from the list and the heading is one lower; the public list from step 8 no longer has it either. |
| Open the filter **By is hidden → Yes**, tick it, choose **Unhide selected comments**, click **Go** | "Unhidden: 1 comment." The comment is back in the discussion. Ticking one that is already in that state changes nothing ("Hidden: 0 comments."). |
| http://localhost:8000/admin/social/like/ | **Likes**: user, post and time, read-only like the follows. |

- Both actions need the `social.change_comment` permission. Today only a superuser has it; Part 10 gives it to the
  Moderators group. A staff member without it sees the list but is not offered the actions (a test covers that).
- Each change is written to Django's own admin log (the comment, who and "Hidden" or "Unhidden"): the moderation
  actions table arrives in Part 10 and has no comment kind. **Unhide** doesn't undelete a comment its author deleted.
- Covered by `test_admin_engagement.py` and, for these clicks, a scripted browser run; not clicked by a person.

#### Step 17: Stop and clean up

**Where:** Every terminal window, plus the browser.

- Stop the servers: `Ctrl+C` in windows 1 and 3 (a leftover `next dev`: step 12 of Part 1).
- Delete the test accounts, their posts, follows, likes and comments (all go with the accounts). In window 2, in `backend\` with the
  venv active:

  ```powershell
  python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(email__startswith='part7-').delete())" | Select-Object -Last 1
  ```

  After one clean run of steps 3 to 12 of this guide it prints `(86, {'social.Like': 4, 'social.Comment': 64, 'social.Follow': 1, 'account.EmailAddress': 6, 'posts.Post': 5, 'accounts.User': 6})`:
  how many rows went in all, and per table (5 posts by `bo`: the tram opinion, the fact, the removed one, the
  deleted one and the limits post, and a deleted post is still a row; 64 comments: 3 on the tram post, 1 on the fact
  and 60 on the limits post, the deleted and the hidden-then-unhidden one included; 4 likes: `ada` and `cy` on
  the tram post, `ada` on the fact and `eve` on the limits post, `bo`'s was taken back). Your count differs if you did the browser steps
  (more comments and likes). Nothing else is touched.
  (The E2E tests' accounts stay in your local database, as in earlier parts: Django Admin → Users deletes them.)
  If you made a throwaway superuser for step 16, delete that too.
- `docker compose down` (repo root) stops the containers and keeps the data; `docker compose down -v`
  wipes the whole local database, which is destructive.
- No secret was used or printed in this part: the only values in the commands are Cloudflare's public test
  token and the throwaway password of the test accounts.

### Part 7B: Bookmarks & reposts

Needs Part 0A's containers and virtualenv, Part 0C's frontend, and your own `backend\.env` and
`frontend\.env.local`. Part 7B adds **one migration** (`social.0003_repost_bookmark`: the reposts and bookmarks tables),
**no dependency** and **no new variable** (the `repost` and `bookmark` rates were already in the settings). It adds the
endpoints `POST` and `DELETE /api/v1/posts/{id}/repost/` and `…/bookmark/` and `GET /api/v1/me/bookmarks/`, fills
`repost_count`, `reposted_by_me` and `bookmarked_by_me` in every post, and turns the Following feed and the profile
lists into **mixed lists of posts and reposts**.

**Which terminal window for what.** Open the windows once and keep using the same ones:

| Window | What runs in it | Used in steps |
|---|---|---|
| Window 1 (server) | `python manage.py runserver` in `backend\`, venv active. Leave it running. Start it in step 3, **after** step 2 (Playwright starts its own servers and needs ports 3000 and 8000 free). | 3 to 18 |
| Window 2 (commands) | All the `curl.exe` and `python manage.py` commands. **Use the same window for steps 3 to 13**: the variables and functions you set in step 3 (`$id`, `$ada`, `$bo`, `$cy`, `$dee`, `$api`, `$op1`, `$fact1`, `$adapost`, `Mk`, `Send`, `Fetch`, `Cut`, and the helpers later steps add) only live in that one terminal. If you close it, redo step 3. | 1 to 13, 19 |
| Window 3 (frontend) | `npm run dev` in `frontend\`. Leave it running. | 14 to 18 |
| Browser | Steps 14 to 18 | 14 to 18 |

Things to know first:

- Steps 3 to 13 talk to the API directly with `curl.exe` (with `.exe`: in PowerShell 5.1 plain `curl` is a different command). Steps 14 to 18 use the
  browser. Step 3 makes four accounts: `ada`, `bo` and `cy` are verified and `dee` never is. `bo` writes the
  posts, `ada` reposts and bookmarks them, `cy` follows `ada` (and later `bo`) and reads the Following feed, and
  `dee` shows what an unverified email may not do. Step 12 adds `eve` and `gus` for the two rate limits.
- **The PowerShell blocks below were not run on Windows.** The agent works on the Linux PC; it ran the bash twin of every command in the Linux guide on 2026-10-10, and the outputs below are those. The PowerShell commands follow the patterns Parts 1 to 7 proved on Windows (JSON written to a file and sent with `--data-binary "@file"`, `curl.exe`, no `&&`). If one behaves differently, tell the agent which.
- The API and page outputs below were recorded on Linux on 2026-10-10. The browser steps were checked the same
  day with headless Chromium (screenshots at 1280 and 390 px) and Django Admin with a scripted browser, not by a
  person at a keyboard. Ids, numbers in names, times and token prefixes differ on every run.
- Nothing here sends an email: step 3 marks the accounts verified with a shell command, which stands in for
  clicking the link (Part 2 shows the real flow). Steps 5, 8 and 10 set a post's status (or plant a row) the same way,
  because the pipeline and the moderator tools that do it for real arrive in Parts 9 and 10.
- **What Part 7B does and doesn't show:** a repost is a plain pointer to the original, never a copy: it has no text
  and no status of its own and always shows the original's **live** label (nothing is checked again). You can't
  repost your own post, a post labelled FALSE or a removed or deleted one; you can always take a repost back,
  even when the original is gone. Reposting needs a verified email; bookmarks are **private**, need only a login
  and are never counted or shown to anyone else. Recent still lists only originals; the Following feed and a
  profile list posts **and** reposts, newest activity first. Score effects of reposts (11B), reports (8) and
  notifications (13) come later.

#### Step 1: Run the automated backend checks

**Where:** Terminal window 2 (commands), starting in the repo root.

**What this does:** Starts the database containers, activates the Python environment, applies the new migration,
confirms there is no further one, then runs the whole backend test suite, the social tests, the linter and the
formatter check.

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero
docker compose up -d
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py migrate                            # Applying social.0003_repost_bookmark... OK
python manage.py makemigrations --check --dry-run   # No changes detected
python manage.py check                              # System check identified no issues (0 silenced).
python -m pytest                                    # 1875 passed
python -m pytest apps/social -q                     # 695 passed
ruff check . ; ruff format --check .                # All checks passed! / 154 files already formatted
```

**You should see:** `Applying social.0003_repost_bookmark... OK` (nothing to apply the second time), `No changes
detected` and `System check identified no issues (0 silenced).`, then the full run ends with `1875 passed`, the
social run with `695 passed`, and the last line pair is `All checks passed!` and `154 files already formatted`.
(Counts may grow later; what matters is that nothing fails.)

- The 390 new social tests: `test_models_repost_bookmark.py` (16: the unique pairs, only the four statuses a post
  can be reposted in, cascades, the indexes), `test_services_repost_bookmark.py` (37: every refusal and their
  order, `status_at_repost`, undoing on a gone post, the cache bust, and real races: two simultaneous reposts make
  one row, six users are all counted, a repost waits for a concurrent status change and records the status at
  commit), `test_api_repost.py` (26, including the real 100-an-hour limit), `test_api_bookmark.py` (17,
  including the real 300-an-hour limit and that bookmarks don't use the like allowance),
  `test_api_bookmark_list.py` (16: only your own, newest first, deleted and removed dropped, a cursor walk, 3
  queries whatever the size), `test_api_feed_reposts.py` (32: mixed items, "no longer available" stubs, once per
  page, the cache, 4 / 3 queries), `test_api_user_posts_reposts.py` (17: reposts on a profile, the Facts and
  Opinions chips by the original's type), `test_timeline.py` (63: the page rule as a table, the cursor token and
  every way to forge one), `test_timeline_db.py` (140: ties, the cursor filters, the per-side slice, items
  arriving or changing during a walk, and 50 + 50 + 30 seeded random walks compared with a reference written
  separately), `test_admin_repost_bookmark.py` (6) and more in `test_engagement_counts.py` and
  `test_no_network.py`.
- `PostQuerySet.for_list(viewer)` now also counts reposts and tells you whether you reposted and bookmarked each
  post, in the same query; `PostSerializer` still refuses a post that wasn't counted.

#### Step 2: Run the automated frontend checks

**Where:** Terminal window 2, then `cd ..\frontend`. Playwright (the last two commands) starts Django and
Next itself, so **no servers may be running on ports 3000 and 8000** (it reuses them if they are, with
whatever settings they have).

**What this does:** Runs the linters, the type check, the component tests, the production build and the
end-to-end tests.

```powershell
cd ..\frontend                                      # from backend\
npm run lint ; npm run lint:tokens ; npm run typecheck ; npm run format:check
npm test                                            # 113 files, 1510 tests passed
npm run build
npm run test:e2e                                    # 36 passed
$env:CI = "1" ; npm run test:e2e ; Remove-Item Env:CI   # 36 passed (against the production build)
cd ..\backend                                       # back to backend\ for steps 3 to 13
```

**You should see:** the first line prints nothing from ESLint and TypeScript and ends with
`lint:tokens OK (…)` and `All matched files use Prettier code style!`. `npm test` ends with
`Test Files  113 passed (113)` and `Tests  1510 passed (1510)`. `npm run build` lists the same routes as in Part 7
(`/bookmarks` was a placeholder before and is now the real page; it is still static). Each E2E run ends with `36 passed`:
the 32 earlier tests and 4 new ones in `e2e/social.spec.ts`.

- On Windows `npm run build` can't blank `NEXT_PUBLIC_GOOGLE_CLIENT_ID` (PowerShell's `$env:NAME = ""` *deletes* the
  variable), so a `frontend\.env.local` with your real client ID is baked into that build and the CI-mode run is less
  representative than on Linux. The default run pins an empty client ID for both servers, so it is unaffected.
- The new E2E tests reuse the two people that file already signs up (allauth limits sign-ups to 20 a minute per
  address and the rest of the suite already uses most of that), so Part 7B adds **no** sign-up. A third person's
  post is made straight in the database. They are: B reposts that post, A (who follows B) sees "Reposted by B" with
  the post's live label, then "This post is no longer available" once it is removed, and B undoes the repost; a
  bookmark is private (it shows on A's `/bookmarks` and is empty for everyone else); Repost is disabled with its
  reason on your own post and on a FALSE one, and a visitor is sent to log in; and a card with four actions and the
  Bookmarks page fit a phone.

#### Step 3: Start the servers and make four accounts and three posts

**Where:** First window 1 (the Django server) and window 3 (the frontend), then window 2 (the commands).
**Keep using window 2 for steps 4 to 13.**

**What this does:** Windows 1 and 3 run the two servers. In window 2 you sign up four accounts through the API and
mark three of them verified (`dee` stays unverified), then `bo` posts an opinion and a fact with a DOI and `ada`
posts an opinion. The helpers `Mk` (make a post, print its id), `Send` (any request, printing the status code and
then the answer), `Fetch` (the same for a GET) and `Cut` (the first characters of a text) are used by every later step.

Window 1 (in `backend\`, venv active):

```powershell
python manage.py runserver                          # leave it running
```

Window 3:

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero\frontend
npm run dev                                         # leave it running
```

Window 2 (in `backend\` with the venv active: steps 1 and 2 leave you there). If you opened a new
terminal, first run `cd C:\Users\Nafis\Downloads\Rumor-Zero\backend` and `.\.venv\Scripts\Activate.ps1`:

```powershell
$id = Get-Date -Format "HHmmss"                     # a unique suffix so the addresses are new each run
$h = '-H', 'Origin: http://localhost:3000', '-H', 'X-Requested-With: rumor-zero'   # headers every auth call needs
function Signup($email, $username) {
@"
{"email": "$email", "username": "$username", "password": "correct-horse-battery-42", "turnstile_token": "XXXX.DUMMY.TOKEN.XXXX"}
"@ | Set-Content -Encoding ascii $env:TEMP\rz-signup.json
  (curl.exe -s @h -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-signup.json" http://localhost:8000/api/auth/app/v1/auth/signup | ConvertFrom-Json).meta.access_token
}
$ada = Signup "part7b-ada-$id@example.test" "part7b_ada_$id"    # $ada = ada's login token (reposts and bookmarks)
$bo = Signup "part7b-bo-$id@example.test" "part7b_bo_$id"       # $bo = bo's login token (the author of the posts)
$cy = Signup "part7b-cy-$id@example.test" "part7b_cy_$id"       # $cy = cy's login token (follows ada)
$dee = Signup "part7b-dee-$id@example.test" "part7b_dee_$id"    # $dee = dee's login token (never verified)
python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(email__startswith='part7b-', email__endswith='$id@example.test').exclude(username='part7b_dee_$id').update(is_email_verified=True), 'accounts marked verified')" | Select-Object -Last 1
$api = 'http://localhost:8000/api/v1'
$adaname = "part7b_ada_$id"; $boname = "part7b_bo_$id"; $cyname = "part7b_cy_$id"; $deename = "part7b_dee_$id"
# Mk <token> <json>: makes a post, prints its id
function Mk($token, $json) {
  $json | Set-Content -Encoding ascii $env:TEMP\rz-post.json
  (curl.exe -s -H "Authorization: Bearer $token" -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-post.json" "$api/posts/" | ConvertFrom-Json).id
}
# Send <METHOD> <path> [token] [json body] [fields]: prints the HTTP status, then the answer. `fields` is a list
# of property names to keep, or a script block `{ param($r) ... }` that picks what to show from the answer.
function Send($method, $path, $token, $json, $show) {
  $a = @()
  if ($token) { $a += '-H', "Authorization: Bearer $token" }
  if ($json) {
    $json | Set-Content -Encoding ascii $env:TEMP\rz-body.json
    $a += '-H', 'Content-Type: application/json', '--data-binary', "@$env:TEMP\rz-body.json"
  }
  $out = curl.exe -s -w "`n%{http_code}" -X $method @a "$api$path"
  $body = if ($out.Count -gt 1) { $out[0..($out.Count - 2)] -join '' } else { '' }
  if ($show -and $body) {
    $r = $body | ConvertFrom-Json
    $shown = if ($show -is [scriptblock]) { & $show $r } else { $r | Select-Object $show }
    $body = ConvertTo-Json -InputObject $shown -Depth 5 -Compress
  }
  "$($out[-1])  $body"
}
function Fetch($path, $token, $show) { Send GET $path $token $null $show }   # Fetch <path> [token] [fields]
# Cut <text> <n>: the first n characters, or "-" when there is no text (a "no longer available" stub has none)
function Cut($s, $n) { if ($s) { $s.Substring(0, [Math]::Min($n, $s.Length)) } else { '-' } }
$op1 = Mk $bo '{"content":"I think the new tram line will change how the city moves.","post_type":"opinion"}'
$fact1 = Mk $bo '{"content":"Solar capacity grew by roughly 30% worldwide last year.","post_type":"fact","sources":["doi:10.1038/s41558-024-02102"]}'
$adapost = Mk $ada '{"content":"Ada thinks trams beat buses.","post_type":"opinion"}'
"$($ada.Substring(0,10)) $($bo.Substring(0,10)) $($cy.Substring(0,10)) $($dee.Substring(0,10))"      # four prefixes, not an error
"op1=$op1"; "fact1=$fact1"; "adapost=$adapost"                              # three ids, not empty
```

**You should see** (the number in the names is your `id`, and the ids differ):

```text
3 accounts marked verified
eyJhbGciOi eyJhbGciOi eyJhbGciOi eyJhbGciOi
op1=29da0351-d108-4b08-9965-626e7a05e8c9
fact1=3c2b6ef4-bc02-4076-8ec0-8f650613e851
adapost=ee6ff30b-0ac9-4578-a848-dd31c6019ca5
```

- The shell prints a line about auto-imported objects first; `Select-Object -Last 1` keeps only ours.
- Sign-up is limited to 20 a minute per address (Part 1), and still calls Cloudflare's test widget, so it
  needs internet.

**If it differs:** an empty token or an `id` of `null` means the sign-up or the post failed: `runserver` isn't
running, or you signed up more than 20 times in a minute. Fix that and run this step again
from `$id = Get-Date …`.

#### Step 4: Repost and undo

**Where:** Terminal window 2 (the same terminal as step 3).

**What this does:** Reposts and un-reposts through `POST` and `DELETE /api/v1/posts/{id}/repost/`, with the
refusals every toggle has. Both are idempotent. Reposting needs a verified email, taking a repost back only a login.

```powershell
function Repost($post, $token) { Send POST "/posts/$post/repost/" $token }          # Repost <post id> [token]
function Unrepost($post, $token) { Send DELETE "/posts/$post/repost/" $token }       # Unrepost <post id> [token]
Repost $op1 $ada                                    # 1: the first repost is 201
Repost $op1 $ada                                    # 2: again: 200, nothing changes
Repost $op1                                         # 3: nobody logged in
Repost $op1 $dee                                    # 4: an unverified email
Repost $fact1 $ada                                  # 5: a fact that is still "checking" can be reposted
Repost 00000000-0000-4000-8000-000000000000 $ada    # 6: no such post
Repost not-a-uuid $ada                              # 7: not even an id
Unrepost $fact1 $ada                                # 8: taking a repost back is 204
Unrepost $fact1 $ada                                # 9: and again: still 204, no error
Unrepost $fact1 $dee                                # 10: an unverified user may also take one back (there is none): 204
```

**You should see** (ten commands, ten answers):

```text
201  {"reposted":true}
200  {"reposted":true}
401  {"detail":"Authentication credentials were not provided.","code":"not_authenticated"}
403  {"detail":"Verify your email address first. Check your inbox for the link.","code":"email_unverified"}
201  {"reposted":true}
404  {"detail":"Not found.","code":"not_found"}
404  {"detail":"Not found.","code":"not_found"}
204
204
204
```

- The first repost is `201`, the same request again is `200` and changes nothing; `DELETE` is `204` every
  time, also when there was nothing to take back (9, 10).
- A repost has no id of its own: `POST` and `DELETE` always name the **original** post. So "reposting a repost"
  can only mean reposting the original, and a second repost of the same post by the same person can't exist.
- A 401 or 403 doesn't use up the allowance of 100 reposts an hour (step 12).

#### Step 5: What can't be reposted

**Where:** Terminal window 2.

**What this does:** Tries the three refusals of ARCHITECTURE §4d (your own post, a post labelled FALSE, a removed
or deleted post), and shows two subtle rules: a repost you already made survives the original turning FALSE, and
you can always take a repost back, even when the original is gone. The statuses are set with shell commands; the
tools that do it for real come in Parts 9 and 10.

```powershell
Repost $adapost $ada                                # 1: your own post is refused
$false1 = Mk $bo '{"content":"The moon is made of green cheese.","post_type":"fact"}'
python manage.py shell -c "from apps.posts.models import Post; print(Post.objects.filter(pk='$false1').update(status='verified_false', verdict_source='moderator'), 'post marked FALSE')" | Select-Object -Last 1
Repost $false1 $ada                                 # 2: a post labelled FALSE is refused
$op2 = Mk $bo '{"content":"This opinion will be removed by a moderator.","post_type":"opinion"}'
python manage.py shell -c "from apps.posts.models import Post; print(Post.objects.filter(pk='$op2').update(status='removed'), 'post removed')" | Select-Object -Last 1
$op3 = Mk $bo '{"content":"This opinion will be deleted by its author.","post_type":"opinion"}'
Send DELETE "/posts/$op3/" $bo                      # bo deletes op3: 204
Repost $op2 $ada                                    # 3: a removed post: 404
Repost $op3 $ada                                    # 4: a deleted post: 404
$fact2 = Mk $bo '{"content":"The harbour bridge is 1,149 metres long.","post_type":"fact"}'
Repost $fact2 $ada                                  # 5: a fact still being checked: 201
python manage.py shell -c "from apps.social.models import Repost; print(list(Repost.objects.filter(post_id='$fact2').values_list('status_at_repost', flat=True)), 'status recorded at the time')" | Select-Object -Last 1
python manage.py shell -c "from apps.posts.models import Post; print(Post.objects.filter(pk='$fact2').update(status='verified_false', verdict_source='moderator'), 'post marked FALSE')" | Select-Object -Last 1
Repost $fact2 $ada                                  # 6: it turned FALSE after ada reposted it: still a quiet 200
Repost $fact2 $cy                                   # 7: but cy can't repost it now: 409
python manage.py shell -c "from apps.social.models import Repost; from apps.accounts.models import User; u = User.objects.get(username='$adaname'); [Repost.objects.create(user=u, post_id=p, status_at_repost='published') for p in ('$op2', '$op3')]; print(Repost.objects.filter(post_id__in=['$op2', '$op3']).count(), 'reposts planted on the removed and the deleted post')" | Select-Object -Last 1
Unrepost $op2 $ada                                  # 8: a repost of a removed post can be taken back: 204
Unrepost $op3 $ada                                  # 9: and one of a deleted post too: 204
python manage.py shell -c "from apps.social.models import Repost; print(Repost.objects.filter(post_id__in=['$op2', '$op3']).count(), 'reposts left on them')" | Select-Object -Last 1
Unrepost 00000000-0000-4000-8000-000000000000 $ada  # 10: an unknown post is 404
```

**You should see:**

```text
409  {"detail":"You can't repost your own post.","code":"cannot_repost_own"}
1 post marked FALSE
409  {"detail":"Posts labelled FALSE can't be reposted.","code":"cannot_repost_false"}
1 post removed
204
404  {"detail":"Not found.","code":"not_found"}
404  {"detail":"Not found.","code":"not_found"}
201  {"reposted":true}
['pending'] status recorded at the time
1 post marked FALSE
200  {"reposted":true}
409  {"detail":"Posts labelled FALSE can't be reposted.","code":"cannot_repost_false"}
2 reposts planted on the removed and the deleted post
204
204
0 reposts left on them
404  {"detail":"Not found.","code":"not_found"}
```

- Your own post and a FALSE post are `409` with their own codes, which the button uses to explain itself (step 14).
  A removed or deleted post is the same plain `404` as for a post that never existed (3, 4).
- `status_at_repost` is the status the post had **when** it was reposted (`pending` here): Part 11B reads it to
  decide what a verdict is worth to the reposter. The post turning FALSE later doesn't touch it (6), and doesn't
  refuse a repost that already exists, but a new reposter is refused (7).
- The removed and the deleted post never take a new repost, but the two reposts planted on them (a shell command
  stands in for reposts made before the original went away) are taken back with a plain `204` (8, 9): the card
  that says "This post is no longer available" must always have its **Undo repost** (step 15).

#### Step 6: Bookmarks

**Where:** Terminal window 2.

**What this does:** Saves and un-saves posts through `POST` and `DELETE /api/v1/posts/{id}/bookmark/`. Bookmarks are
private, so there is no verified-email rule and no restriction on whose or which post: only a post the public can't
see is refused.

```powershell
function Bookmark($post, $token) { Send POST "/posts/$post/bookmark/" $token }       # Bookmark <post id> [token]
function Unbookmark($post, $token) { Send DELETE "/posts/$post/bookmark/" $token }    # Unbookmark <post id> [token]
Bookmark $op1 $ada                                  # 1: the first bookmark is 201
Bookmark $op1 $ada                                  # 2: again: 200
Bookmark $op1                                       # 3: nobody logged in
Bookmark $op1 $dee                                  # 4: an unverified email is fine: bookmarks are private
Bookmark $adapost $ada                              # 5: your own post is fine
Bookmark $false1 $ada                               # 6: so is a post labelled FALSE
Bookmark $op2 $ada                                  # 7: a removed post: 404
Bookmark $op3 $ada                                  # 8: a deleted post: 404
Bookmark not-a-uuid $ada                            # 9: not even an id
Unbookmark $op1 $dee                                # 10: taking one back is 204
Unbookmark $op1 $dee                                # 11: and again: 204
Unbookmark $op3 $ada                                # 12: a deleted post is 404 even for that
python manage.py shell -c "from apps.social.models import Bookmark; from apps.accounts.models import User; Bookmark.objects.create(user=User.objects.get(username='$adaname'), post_id='$op2'); print(Bookmark.objects.filter(post_id='$op2').count(), 'bookmark planted on the removed post')" | Select-Object -Last 1
Unbookmark $op2 $ada                                # 13: ...but a bookmark can be taken back from a removed post: 204
python manage.py shell -c "from apps.social.models import Bookmark; print(Bookmark.objects.filter(post_id='$op2').count(), 'bookmarks left on it')" | Select-Object -Last 1
```

**You should see:**

```text
201  {"bookmarked":true}
200  {"bookmarked":true}
401  {"detail":"Authentication credentials were not provided.","code":"not_authenticated"}
201  {"bookmarked":true}
201  {"bookmarked":true}
201  {"bookmarked":true}
404  {"detail":"Not found.","code":"not_found"}
404  {"detail":"Not found.","code":"not_found"}
404  {"detail":"Not found.","code":"not_found"}
204
204
404  {"detail":"Not found.","code":"not_found"}
1 bookmark planted on the removed post
204
0 bookmarks left on it
```

- Like a repost, a bookmark is `201` then `200`, and `DELETE` is `204` every time (10, 11). `dee`, who may not
  like, comment or repost, can bookmark (4).
- Every visible post can be bookmarked, including your own (5) and a FALSE one (6). A removed or deleted post can't
  (7, 8), and a bookmark that was already there can be taken back from a removed post (13) but not a deleted one
  (12), exactly as with likes.

#### Step 7: The counts and flags on every post

**Where:** Terminal window 2.

**What this does:** Reads `repost_count`, `reposted_by_me` and `bookmarked_by_me` as nobody and as other people.
The count is public and the same for everyone; the two flags are yours alone. **There is no bookmark count anywhere**:
not on the post, not on a profile.

```powershell
Repost $op1 $cy                                     # cy reposts the tram post too: 201 (ada's repost is from step 4)
$f = { param($r) [pscustomobject]@{ reposts = $r.repost_count; reposted_by_me = $r.reposted_by_me; bookmarked_by_me = $r.bookmarked_by_me } }
Fetch "/posts/$op1/" $null $f                       # 1: nobody logged in
Fetch "/posts/$op1/" $ada $f                        # 2: ada reposted and bookmarked it
Fetch "/posts/$op1/" $cy $f                         # 3: cy reposted it, did not bookmark it
Fetch "/posts/$op1/" $bo $f                         # 4: bo wrote it: sees the count, nothing of his own
Fetch "/users/$boname/posts/" $ada { param($r) @($r.results | ForEach-Object { [pscustomobject]@{ text = (Cut $_.post.content 26); reposts = $_.post.repost_count; reposted = $_.post.reposted_by_me; saved = $_.post.bookmarked_by_me } }) }
Fetch "/users/$adaname/" $bo { param($r) $r.counts }    # 5: a profile has no bookmark count, and no repost count either
```

**You should see:**

```text
201  {"reposted":true}
200  {"reposts":2,"reposted_by_me":false,"bookmarked_by_me":false}
200  {"reposts":2,"reposted_by_me":true,"bookmarked_by_me":true}
200  {"reposts":2,"reposted_by_me":true,"bookmarked_by_me":false}
200  {"reposts":2,"reposted_by_me":false,"bookmarked_by_me":false}
200  [{"text":"The harbour bridge is 1,14","reposts":1,"reposted":true,"saved":false},{"text":"The moon is made of green ","reposts":0,"reposted":false,"saved":true},{"text":"Solar capacity grew by rou","reposts":0,"reposted":false,"saved":false},{"text":"I think the new tram line ","reposts":2,"reposted":true,"saved":true}]
200  {"followers":0,"following":0,"posts":1,"verified":0,"false":0}
```

- `reposts` is 2 for everyone (`ada` and `cy`); `reposted_by_me` and `bookmarked_by_me` are `false` for a visitor and
  for anyone who didn't do it (1, 4). `bo`, the author, sees nobody's bookmark, not even that someone saved his post (4).
- The list is `bo`'s four visible posts (the removed and the deleted one are left out), counted in the same query as
  the posts: a list of 20 posts costs the same number of queries as a list of 2 (tests pin it).
- The profile's counters (5) are the ones from Part 6: still no repost count and no bookmark count.

#### Step 8: The Following feed with reposts

**Where:** Terminal window 2.

**What this does:** Makes `cy` follow `ada`, lets `ada` repost two facts, and reads `cy`'s Following feed. It shows
that a repost carries the original's **live** label (a verdict changes it at once, even though the first page is
cached), that a repost whose original was removed becomes a stub, that an undone repost leaves the page at once, that
a **new** repost reaches a follower after at most 30 seconds (the cache), and that a post shows **once per page**.

```powershell
function Feed($token, $query) {                 # Feed <token> [query]: cy's Following feed, one line per item
  $path = if ($query) { "/feed/?$query" } else { '/feed/' }
  Fetch $path $token { param($r) @($r.results | ForEach-Object { [pscustomobject]@{ kind = $_.kind; by = $(if ($_.reposted_by) { $_.reposted_by.username } else { $null }); text = (Cut $_.post.content 24); status = $_.post.status; gone = $_.post.unavailable } }) }
}
$fact3 = Mk $bo '{"content":"Rail ridership doubled in ten years.","post_type":"fact"}'
Send POST "/users/$adaname/follow/" $cy             # cy follows ada: 201 (this also clears cy's cached feed)
Repost $fact1 $ada                                  # ada reposts the solar fact (still "checking")
Repost $fact3 $ada                                  # ...and a third fact
Feed $cy                                            # 1: cy's Following feed: ada's post and reposts, and cy's own repost
python manage.py shell -c "from apps.posts.models import Post; print(Post.objects.filter(pk='$fact1').update(status='verified_true', verdict_source='pipeline', pipeline_verdict='true', confidence_score=94), 'post verified')" | Select-Object -Last 1
python manage.py shell -c "from apps.posts.models import Post; print(Post.objects.filter(pk='$fact3').update(status='removed'), 'post removed')" | Select-Object -Last 1
Feed $cy                                            # 2: the label changed, the removed one is a stub: the cached page keeps only keys
Unrepost $fact1 $ada                                # ada takes her solar repost back: 204
Feed $cy                                            # 3: it is gone at once, though the page is still cached
$op5 = Mk $bo '{"content":"A late post from bo.","post_type":"opinion"}'
Repost $op5 $ada                                    # ada reposts a brand-new post
Feed $cy                                            # 4: cy's cached page doesn't have it yet (at most 30 s)
Start-Sleep -Seconds 31
Feed $cy                                            # 5: 31 seconds later it is on top
Send POST "/users/$boname/follow/" $cy              # cy follows bo too (this clears the cache)
Fetch "/feed/" $cy { param($r) @($r.results | Where-Object { $_.post.id -eq $op1 } | ForEach-Object { [pscustomobject]@{ kind = $_.kind; by = $_.reposted_by.username } }) }   # 6: the tram post, by bo and reposted twice: shown once
```

**You should see** (the number in the names is your `id`):

```text
201  {"is_following":true}
201  {"reposted":true}
201  {"reposted":true}
200  [{"kind":"repost","by":"part7b_ada_203850","text":"Rail ridership doubled i","status":"pending","gone":null},{"kind":"repost","by":"part7b_ada_203850","text":"Solar capacity grew by r","status":"pending","gone":null},{"kind":"repost","by":"part7b_cy_203850","text":"I think the new tram lin","status":"published","gone":null},{"kind":"repost","by":"part7b_ada_203850","text":"The harbour bridge is 1,","status":"verified_false","gone":null},{"kind":"post","by":null,"text":"Ada thinks trams beat bu","status":"published","gone":null}]
1 post verified
1 post removed
200  [{"kind":"repost","by":"part7b_ada_203850","text":"-","status":null,"gone":true},{"kind":"repost","by":"part7b_ada_203850","text":"Solar capacity grew by r","status":"verified_true","gone":null},{"kind":"repost","by":"part7b_cy_203850","text":"I think the new tram lin","status":"published","gone":null},{"kind":"repost","by":"part7b_ada_203850","text":"The harbour bridge is 1,","status":"verified_false","gone":null},{"kind":"post","by":null,"text":"Ada thinks trams beat bu","status":"published","gone":null}]
204
200  [{"kind":"repost","by":"part7b_ada_203850","text":"-","status":null,"gone":true},{"kind":"repost","by":"part7b_cy_203850","text":"I think the new tram lin","status":"published","gone":null},{"kind":"repost","by":"part7b_ada_203850","text":"The harbour bridge is 1,","status":"verified_false","gone":null},{"kind":"post","by":null,"text":"Ada thinks trams beat bu","status":"published","gone":null}]
201  {"reposted":true}
200  [{"kind":"repost","by":"part7b_ada_203850","text":"-","status":null,"gone":true},{"kind":"repost","by":"part7b_cy_203850","text":"I think the new tram lin","status":"published","gone":null},{"kind":"repost","by":"part7b_ada_203850","text":"The harbour bridge is 1,","status":"verified_false","gone":null},{"kind":"post","by":null,"text":"Ada thinks trams beat bu","status":"published","gone":null}]
200  [{"kind":"repost","by":"part7b_ada_203850","text":"A late post from bo.","status":"published","gone":null},{"kind":"repost","by":"part7b_ada_203850","text":"-","status":null,"gone":true},{"kind":"repost","by":"part7b_cy_203850","text":"I think the new tram lin","status":"published","gone":null},{"kind":"repost","by":"part7b_ada_203850","text":"The harbour bridge is 1,","status":"verified_false","gone":null},{"kind":"post","by":null,"text":"Ada thinks trams beat bu","status":"published","gone":null}]
201  {"is_following":true}
200  [{"kind":"repost","by":"part7b_cy_203850"}]
```

- Each item has `kind` (`post` or `repost`), `by` (who reposted it) and the original's content and status. A repost
  has no text of its own. Newest **activity** first: a repost sorts by when it was made, a post by when it was posted.
- Line 1 is cy's page: `ada`'s own post (the last item), her reposts of the two facts and of the harbour fact (from
  step 5, labelled `verified_false`: a repost shows the original's label whatever it was when reposted), and `cy`'s
  own repost of the tram post (step 7). **`ada`'s older repost of the same tram post is not there**: a post shows
  once per page, the most recent activity wins.
- Line 2: the solar repost says `verified_true` and the third fact's repost is a **stub** (`"gone": true`, no text,
  no status) although the page was read from the cache a moment ago: the cache holds only the keys of the page, and the
  posts and reposts are read fresh every time. A stub shows as "This post is no longer available" (step 15).
- Line 3: an undone repost leaves the page at once. Line 4: a **new** repost made by someone you follow isn't there
  yet, the same rule as a new post (Part 6): the first page is cached for 30 seconds. Line 5, 31 seconds later, it is.
  Your **own** reposts and follows clear your own cache, so they show at once.
- Line 6: after `cy` also follows `bo`, the tram post could show up three times (`bo`'s own post, `ada`'s repost and
  `cy`'s repost), but only the most recent of them, `cy`'s repost, is shown.

#### Step 9: Profiles with reposts, and the Facts and Opinions chips

**Where:** Terminal window 2.

**What this does:** Reads `ada`'s profile list, which now holds her own posts **and** her reposts, and the two filter
chips: a repost is filtered by the **original's** type, so a repost of a fact shows under Facts even when the fact is
gone.

```powershell
$prof = { param($r) @($r.results | ForEach-Object { [pscustomobject]@{ kind = $_.kind; by = $(if ($_.reposted_by) { $_.reposted_by.username } else { $null }); text = (Cut $_.post.content 24); gone = $_.post.unavailable } }) }
Fetch "/users/$adaname/posts/" $null $prof          # 1: ada's profile: her own post and her reposts (the removed fact is a stub)
Fetch "/users/$adaname/posts/?post_type=fact" $null $prof       # 2: Facts: her facts, and reposts of facts (also the one that is gone)
Fetch "/users/$adaname/posts/?post_type=opinion" $null $prof    # 3: Opinions: her opinions, and reposts of opinions
Fetch "/users/$adaname/posts/?post_type=gossip"     # 4: anything else is a 400
```

**You should see** (the number in the names is your `id`):

```text
200  [{"kind":"repost","by":"part7b_ada_203850","text":"A late post from bo.","gone":null},{"kind":"repost","by":"part7b_ada_203850","text":"-","gone":true},{"kind":"repost","by":"part7b_ada_203850","text":"The harbour bridge is 1,","gone":null},{"kind":"repost","by":"part7b_ada_203850","text":"I think the new tram lin","gone":null},{"kind":"post","by":null,"text":"Ada thinks trams beat bu","gone":null}]
200  [{"kind":"repost","by":"part7b_ada_203850","text":"-","gone":true},{"kind":"repost","by":"part7b_ada_203850","text":"The harbour bridge is 1,","gone":null}]
200  [{"kind":"repost","by":"part7b_ada_203850","text":"A late post from bo.","gone":null},{"kind":"repost","by":"part7b_ada_203850","text":"I think the new tram lin","gone":null},{"kind":"post","by":null,"text":"Ada thinks trams beat bu","gone":null}]
400  {"post_type":["Choose fact or opinion, or leave it out."]}
```

- The profile list is public and never cached. You can't repost your own post, so a profile never shows the same
  post twice and its pages are always full. The stub (`gone`) is `ada`'s repost of the removed fact, kept until she
  undoes it.
- The filter is applied to the original (2, 3): the stub is under Facts because the post it pointed at was a fact.

#### Step 10: Your bookmarks list

**Where:** Terminal window 2.

**What this does:** Reads `GET /api/v1/me/bookmarks/`: **only your own**, newest bookmark first, in the same
envelope as the feeds. Deleted and removed posts are left out (the bookmark rows stay, so a post that comes back
reappears).

```powershell
python manage.py shell -c "from apps.social.models import Bookmark; from apps.accounts.models import User; u = User.objects.get(username='$adaname'); [Bookmark.objects.create(user=u, post_id=p) for p in ('$op2', '$op3')]; print(Bookmark.objects.filter(user=u).count(), 'bookmarks of ada in the table, including one on a removed and one on a deleted post')" | Select-Object -Last 1
$saved = { param($r) @($r.results | ForEach-Object { [pscustomobject]@{ kind = $_.kind; text = (Cut $_.post.content 26); saved = $_.post.bookmarked_by_me } }) }
Fetch "/me/bookmarks/" $ada $saved                  # 1: ada's list: newest bookmark first; the removed and the deleted post are dropped
Fetch "/me/bookmarks/" $bo $saved                   # 2: bo saved nothing: an empty list, not ada's
Fetch "/me/bookmarks/" $null { param($r) $r.code }  # 3: nobody logged in: 401
curl.exe -s -o NUL -w "%{http_code}`n" -H "Authorization: Bearer $bo" "$api/users/$adaname/bookmarks/"   # 4: there is no address for someone else's list: 404
$c = (curl.exe -s -H "Authorization: Bearer $ada" "$api/me/bookmarks/?page_size=2" | ConvertFrom-Json).next_cursor
$paging = { param($r) [pscustomobject]@{ n = @($r.results).Count; more = ($null -ne $r.next_cursor) } }
Fetch "/me/bookmarks/?page_size=2" $ada $paging     # 5: two to a page, and a cursor
Fetch "/me/bookmarks/?page_size=2&cursor=$c" $ada $paging   # 6: the rest
Fetch "/me/bookmarks/?cursor=cD1ub3QtYS1kYXRl" $ada { param($r) $r.code }   # 7: a made-up cursor is a 404
Fetch "/me/bookmarks/" $ada { param($r) @($r.results[0].PSObject.Properties.Name | Sort-Object) }   # 8: the items have the feed's four keys (activity_at is when you saved it)
```

**You should see:**

```text
5 bookmarks of ada in the table, including one on a removed and one on a deleted post
200  [{"kind":"post","text":"The moon is made of green ","saved":true},{"kind":"post","text":"Ada thinks trams beat buse","saved":true},{"kind":"post","text":"I think the new tram line ","saved":true}]
200  []
401  "not_authenticated"
404
200  {"n":2,"more":true}
200  {"n":1,"more":false}
404  "not_found"
200  ["activity_at","kind","post","reposted_by"]
```

- The order is the order she saved them in, newest first (the FALSE post, her own post, the tram post), not the order
  of the posts. Five rows are in the table, three are shown (1).
- `bo` gets an empty list, never `ada`'s (2), and there is no way to ask for another user's (4): the route doesn't
  exist. Nothing counts bookmarks anywhere (step 7).
- Every item is `kind: "post"` with `reposted_by: null`; its `activity_at` is the time of the bookmark.

#### Step 11: Paging the feed while posts arrive

**Where:** Terminal window 2.

**What this does:** Walks `cy`'s Following feed two items at a time while a new post and a new repost arrive between
the two pages. The mixed feed pages by a cursor over (activity time, kind, post, reposter), so nothing new can push an
item onto the next page or pull one off it; a cursor that isn't ours is a clean `404`.

```powershell
$cards = { param($r) @($r.results | ForEach-Object { [pscustomobject]@{ kind = $_.kind; by = $(if ($_.reposted_by) { $_.reposted_by.username } else { $null }); text = (Cut $_.post.content 24) } }) }
$p1 = curl.exe -s -H "Authorization: Bearer $cy" "$api/feed/?page_size=2" | ConvertFrom-Json
ConvertTo-Json -InputObject (& $cards $p1) -Compress    # 1: the first two items
$c = $p1.next_cursor
$null = Mk $bo '{"content":"Posted while cy was reading.","post_type":"opinion"}'
Repost (Mk $bo '{"content":"Reposted while cy was reading.","post_type":"opinion"}') $ada
Fetch "/feed/?page_size=2&cursor=$c" $cy $cards    # 2: the next two: neither new item gets in
Fetch "/feed/?cursor=cD1ub3QtYS1kYXRl" $cy { param($r) $r.code }   # 3: a made-up cursor is a 404
Fetch "/feed/?cursor=junk" $cy { param($r) $r.code }               # 4: so is any other cursor that isn't ours
```

**You should see** (the number in the names is your `id`):

```text
[{"kind":"repost","by":"part7b_ada_203850","text":"A late post from bo."},{"kind":"repost","by":"part7b_ada_203850","text":"-"}]
201  {"reposted":true}
200  [{"kind":"repost","by":"part7b_cy_203850","text":"I think the new tram lin"},{"kind":"repost","by":"part7b_ada_203850","text":"The harbour bridge is 1,"}]
404  "not_found"
404  "not_found"
```

- Line 1 is the two newest items. The two new ones (made after it) are newer than anything on the first page, so
  they only appear at the top of a **fresh** first page; the second page (line 3) carries on exactly where the first
  stopped: no repeat and no gap. A page can hold fewer items than its size when some rows repeat a post that is
  already on it; the cursor still moves past them.
- The cursor is a bare token (never an absolute URL, which would point past the relay). The one from Part 6's feed is not
  valid any more: the client simply starts from the top again (a test covers it).

#### Step 12: Reposting and bookmarking are rate limited

**Where:** Terminal window 2.

**What this does:** Makes two more verified accounts, then uses up their allowances: 100 reposts an hour (`POST` and
`DELETE` share it) and 300 bookmarks an hour (likewise). The two buckets are separate from each other and from
likes.

```powershell
$eve = Signup "part7b-eve-$id@example.test" "part7b_eve_$id"    # $eve = a fresh account for the repost limit
$gus = Signup "part7b-gus-$id@example.test" "part7b_gus_$id"    # $gus = a fresh account for the bookmark limit
python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(email__in=['part7b-eve-$id@example.test', 'part7b-gus-$id@example.test']).update(is_email_verified=True), 'accounts marked verified')" | Select-Object -Last 1
1..100 | ForEach-Object { curl.exe -s -o NUL -w "%{http_code}`n" -X POST -H "Authorization: Bearer $eve" "$api/posts/$op1/repost/" } | Group-Object | Sort-Object Name | ForEach-Object { "{0,7} {1}" -f $_.Count, $_.Name }   # 100 reposts of one post
curl.exe -s -i -X POST -H "Authorization: Bearer $eve" "$api/posts/$op1/repost/" | Select-String -Pattern 'HTTP/[0-9.]+ [0-9]+|retry-after: [0-9]+|"code":"[a-z_]+"' -AllMatches | ForEach-Object { $_.Matches.Value }   # the 101st
1..300 | ForEach-Object { curl.exe -s -o NUL -w "%{http_code}`n" -X POST -H "Authorization: Bearer $gus" "$api/posts/$op1/bookmark/" } | Group-Object | Sort-Object Name | ForEach-Object { "{0,7} {1}" -f $_.Count, $_.Name }   # 300 bookmarks of one post
curl.exe -s -i -X POST -H "Authorization: Bearer $gus" "$api/posts/$op1/bookmark/" | Select-String -Pattern 'HTTP/[0-9.]+ [0-9]+|retry-after: [0-9]+|"code":"[a-z_]+"' -AllMatches | ForEach-Object { $_.Matches.Value }   # the 301st
Send POST "/posts/$op1/like/" $gus                  # bookmarks have their own allowance: a like still works
Fetch "/me/bookmarks/" $gus { param($r) [pscustomobject]@{ n = @($r.results).Count } }   # reading is never throttled
```

**You should see** (the seconds differ):

```text
2 accounts marked verified
     99 200
      1 201
HTTP/1.1 429
Retry-After: 3599
"code":"throttled"
    299 200
      1 201
HTTP/1.1 429
Retry-After: 3597
"code":"throttled"
201  {"liked":true}
200  {"n":1}
```

- 100 requests went through (the first made the repost, the other 99 were repeats), the 101st was refused with `429`,
  `"code":"throttled"` and a `Retry-After` in seconds. Likewise 300 bookmarks, then the 301st.
- A 401 or 403 doesn't use up an allowance (tests cover it, and that a refusal like `409` does count). Using up the
  bookmark allowance leaves a like working (201), so the buckets really are separate.

#### Step 13: The indexes are used

**Where:** Terminal window 2.

**What this does:** In a transaction that is thrown away at the end, makes 300 users, 20,000 posts, 3,000 reposts, 50
follows and 2,000 bookmarks, then asks the database how it would run the Following feed's query (a first page and a deep
page) and the bookmark page, and prints the plan lines. Nothing is saved.

```powershell
@'
import random
from datetime import timedelta
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from apps.accounts.models import User
from apps.posts.models import Post, PostStatus
from apps.social import feed, timeline
from apps.social.models import Bookmark, Follow, Repost

class Rollback(Exception):
    pass

rng = random.Random(1)
try:
    with transaction.atomic():   # everything below is thrown away at the end
        users = User.objects.bulk_create([User(username=f"xq_{i:03d}", email=f"xq{i}@example.test") for i in range(301)])
        me, others = users[0], users[1:]
        now = timezone.now()
        Follow.objects.bulk_create([Follow(follower=me, following=u) for u in others[:50]])
        posts = Post.objects.bulk_create([Post(author=others[i % 300], content=f"p{i}", post_type="opinion", status="published", created_at=now - timedelta(seconds=3 * i)) for i in range(20000)])
        pairs = {}
        while len(pairs) < 3000:
            u, p = rng.choice(others), rng.choice(posts)
            if p.author_id != u.pk:
                pairs[(u.pk, p.pk)] = Repost(user=u, post=p, status_at_repost="published", created_at=now - timedelta(seconds=rng.randint(0, 60000)))
        Repost.objects.bulk_create(list(pairs.values()))
        Bookmark.objects.bulk_create([Bookmark(user=me, post=p, created_at=now - timedelta(seconds=i)) for i, p in enumerate(posts[:2000])])
        with connection.cursor() as c:
            for table in ("posts_post", "social_repost", "social_follow", "social_bookmark"):
                c.execute(f"ANALYZE {table}")
        deep = timeline.Key(now - timedelta(seconds=30000), 0, timeline.ZERO_UUID, timeline.ZERO_UUID)
        for label, cursor in (("--- Following feed, first page", None), ("--- Following feed, a deep page", deep)):
            with CaptureQueriesContext(connection) as q:
                timeline.page(feed.following_posts(me), feed.following_reposts(me), size=20, cursor=cursor, dedupe=True)
            print(label)
            with connection.cursor() as c:
                c.execute("EXPLAIN (COSTS OFF) " + q.captured_queries[-1]["sql"])
                for row in c.fetchall():
                    print(row[0])
        rows = Bookmark.objects.filter(user=me, post__deleted_at__isnull=True).exclude(post__status=PostStatus.REMOVED).order_by("-created_at", "-id").values("id", "created_at", "post_id")[:21]
        sql, params = rows.query.sql_with_params()
        print("--- bookmark page")
        with connection.cursor() as c:
            c.execute("EXPLAIN (COSTS OFF) " + sql, params)
            for row in c.fetchall():
                print(row[0])
        raise Rollback
except Rollback:
    print("rolled back: nothing was saved")
'@ | python manage.py shell 2>&1 | Select-String -Pattern '^---|Scan|Sort|rolled back' | ForEach-Object { $_.Line }
```

**You should see:**

```text
--- Following feed, first page
  ->  Incremental Sort
        Sort Key: posts_post.created_at DESC, (0) DESC, posts_post.id DESC, ('00000000-0000-0000-0000-000000000000'::uuid) DESC
              Sort Key: posts_post.created_at DESC, posts_post.id DESC
                    ->  Index Scan using posts_recent_idx on posts_post
                            ->  Seq Scan on social_follow u0
                    ->  Sort
                          Sort Key: social_repost.created_at DESC, social_repost.post_id DESC, social_repost.user_id DESC
                          ->  Seq Scan on social_repost
                                  ->  Seq Scan on social_follow u0_1
--- Following feed, a deep page
  ->  Incremental Sort
        Sort Key: posts_post.created_at DESC, (0) DESC, posts_post.id DESC, ('00000000-0000-0000-0000-000000000000'::uuid) DESC
              Sort Key: posts_post.created_at DESC, posts_post.id DESC
                    ->  Index Scan using posts_recent_idx on posts_post
                            ->  Seq Scan on social_follow u0
                    ->  Sort
                          Sort Key: social_repost.created_at DESC, social_repost.post_id DESC, social_repost.user_id DESC
                          ->  Seq Scan on social_repost
                                  ->  Seq Scan on social_follow u0_1
--- bookmark page
        ->  Index Scan using bookmarks_user_created_idx on social_bookmark
        ->  Index Scan using posts_post_pkey on posts_post
rolled back: nothing was saved
```

- The Following feed is one query: the posts side walks `posts_recent_idx` newest first and stops after enough rows (the
  same plan at the first page and at a deep one: that is what the plain `created_at <=` in the filter is for), the
  reposts side takes the reposts of the people you follow, sorts them and keeps the newest few, and the two are merged.
  Each side is cut to at most 41 rows (twice the page plus one).
- The reposts side is a sequential scan and a sort. At 3,000 reposts that is nothing; measured separately with
  300,000 reposts and 200 follows it took about 11 to 18 ms. Splitting it into a separate query per group of
  people (a variant that was tried) took about the same time, so it is recorded for Part 16 rather than built now.
- The bookmark page walks `bookmarks_user_created_idx` in order and looks each post up by its primary key: 21 rows, no sort.

#### Step 14: Reposts and bookmarks on the cards

**Where:** Browser, with `runserver` (window 1) and `npm run dev` (window 3) running. Log in at
http://localhost:3000/login as `part7b-cy-<id>@example.test` (use the `id` from step 3: `echo $id`) with the password `correct-horse-battery-42` (`cy` was verified in step 3).

**What this does:** Looks at the two new buttons and the "Reposted by" line, as four kinds of visitor.

| Do this | Expect |
|---|---|
| Open http://localhost:3000/home and click the **Following** tab | Cards from `bo` and `ada`. A repost has a small line **"↻ Reposted by @part7b_ada_<id>"** above the author row, in the same grey small type as a timestamp; the card itself is the original's, with the original's author. Every card ends with a hairline, then (left) a **heart**, a **speech bubble** and a **two-arrow repost glyph**, each with its count, and (right, alone) a small **bookmark** glyph. |
| Click the repost glyph on a card that isn't yours and isn't FALSE | The glyph turns **blue** and the count goes up by one **at once**, before the server answers. Click again: back to grey and the old count. |
| Click the bookmark glyph | It turns into a filled **blue** bookmark at once; click again to take it back. There is no number beside it, ever. |
| Log in as `ada` in a second window. On her own post ("Ada thinks trams beat buses.") look at its repost glyph | It is dimmed. Hover it: the tooltip says "You can't repost your own post." A click shows the same words as a toast and sends nothing. |
| As `ada`, on "The moon is made of green cheese." (FALSE) look at the repost glyph | Dimmed, with the tooltip and toast "Posts labelled FALSE can't be reposted." Its bookmark still works. |
| Reload the page | The glyphs and counts are what the server says: the state survived. |
| Open a private window and go to /home (a visitor) | The same cards and counts. The repost and bookmark glyphs are **links**: they point to `/login?next=%2Fp%2F<id>`. |
| In another window log in as `dee` (`part7b-dee-<id>@example.test`, same password: never verified) and click a repost glyph | It looks dimmed and nothing is sent; a toast says "Verify your email to repost posts. Check your inbox for the link." The bookmark glyph **works**: bookmarks are private. |

- Covered by `RepostButton.test.tsx` (flip before the answer, rollback and a toast per kind of failure, one request for
  two clicks in one tick, the disabled reasons, enabled to undo, the visitor and unverified states, a unique hint per
  button), `BookmarkButton.test.tsx`, `RepostHeader.test.tsx`, `PostActions.test.tsx`, `FeedList.test.tsx` and the new E2E tests.
- Every button sits above the card's big invisible link, so it never opens the post by accident. A repost's buttons
  act on the **original** (a repost has no id of its own), so reposting a card that already says "Reposted by" reposts
  the original post.

#### Step 15: "This post is no longer available", and Undo repost

**Where:** Browser, logged in as `ada` (`part7b-ada-<id>@example.test`) in one window and as `cy` in another.

**What this does:** Looks at what a repost becomes when its original disappears (the stub from step 8) and removes it.

| Do this | Expect |
|---|---|
| As `cy`: open /home, click **Following** | One card has the line "↻ Reposted by @part7b_ada_<id>" and, below it, a shorter card body with a **no-entry glyph** and **"This post is no longer available"**: no text, no buttons. It is the third fact's repost, whose original was removed in step 8. There is no **Undo repost** button for `cy`. |
| As `ada`: open http://localhost:3000/u/part7b_ada_`<id>` (Profile in the rail) | The same card in her list, **with a ghost "Undo repost" button** at its right. Her other reposts have "Reposted by" lines and the normal buttons, and her repost glyphs are blue. |
| Still as `ada`, click the **Facts** chip, then **Opinions** | The stub is listed under **Facts** (its original was a fact) and not under **Opinions**. |
| Click **Undo repost** | The card disappears and a toast says "Repost removed." Reload: it is still gone, and `cy`'s Following tab no longer shows it. |

- The server answers `204` to an undo whatever became of the original (step 5), so a stub can always be removed.
- Covered by `UnavailablePostCard.test.tsx`, the Undo cases in `FeedList.test.tsx` and the E2E test.

#### Step 16: The Bookmarks page and the post page

**Where:** Browser, logged in as `ada`, with both servers running.

**What this does:** Opens the page that lists your bookmarks and the post page's action row.

| Do this | Expect |
|---|---|
| Click **Bookmarks** in the left rail (http://localhost:3000/bookmarks) | A heading **Bookmarks** and your saved posts, newest bookmark first: the FALSE moon post, `ada`'s own post, the tram post. Each card has its bookmark **filled and blue**; the moon post's and her own post's repost glyphs are dimmed, the tram post's is blue. The list ends with "You're caught up." |
| Click a filled bookmark | It turns outline at once (the card stays until the next load, as an unfollowed row does). Reload: it is gone from the list. |
| Log in as `bo` (never saved anything) and open /bookmarks | An empty state with a bookmark glyph: **"No bookmarks yet"** and "Posts you bookmark appear here. Only you can see them." |
| Log out and open /bookmarks | You are sent to `/login?next=%2Fbookmarks` and come back here after logging in. |
| Open a post's own page (click its text) | The claim card's action row reads **Like, Comments, Repost** with words beside the glyphs (from 640 px up), then the **bookmark** glyph and **Copy link**. The repost and bookmark work as on a card. |

- The list is fetched by the page after it loads (not server-rendered, never indexed), and only after the session is
  known, so the first request carries your token. A pending fact in the list still changes its badge by itself.
- Covered by `BookmarkList.test.tsx` (including the StrictMode case), `BookmarkButton.test.tsx` and the E2E test.

#### Step 17: A phone-sized window

**Where:** Browser, logged in as `cy`.

**What this does:** Checks the new parts at phone width. In Firefox or Chrome press `F12`, then the "responsive
design" / device toolbar button, and set the width to 390.

| Do this | Expect |
|---|---|
| Open /home and click **Following** | Each card's bar (heart, count, bubble, count, repost, count, and the bookmark at the right) fits on one line under the claim; a repost's "Reposted by" line fits above the author row. **No sideways scrolling.** |
| Open /bookmarks | The heading and the cards fit; **no sideways scrolling.** |
| Open a post's page | The action row holds the glyphs with their counts only (the words are hidden below 640 px), the bookmark and **Copy link**, wrapping to a second line if needed. |

- Measured with headless Chromium at 390 px: 0 px of horizontal overflow on `/home`, on the Following tab and on
  `/bookmarks`.

#### Step 18: Django Admin: reposts, and bookmarks for superusers only

**Where:** Browser, while `runserver` is running in window 1. For the moderator check, first make one in window 2:

```powershell
python manage.py shell -c "from django.contrib.auth.models import Permission; from apps.accounts.models import User, Role; mod = User.objects.create_user(email='part7b-mod-$id@example.test', username='part7b_mod_$id', password='correct-horse-battery-42', role=Role.MODERATOR, is_email_verified=True); mod.user_permissions.set(Permission.objects.filter(codename__in=['view_repost', 'view_bookmark', 'change_bookmark', 'delete_bookmark', 'add_bookmark'])); print('moderator made')" | Select-Object -Last 1
```

**What this does:** Opens the two new admin lists as a superuser, then as a moderator who holds **every bookmark
permission** (a moderator gets no permissions at all until Part 10; this one is given them by hand to prove they don't
matter).

| URL / action | Expect |
|---|---|
| http://localhost:8000/admin/ (superuser from Part 0A; if it 404s, `ADMIN_URL_PATH` in `backend\.env` isn't `admin/`: use that path) | **Bookmarks** and **Reposts** are listed under Social. |
| http://localhost:8000/admin/social/repost/ | **Reposts**: user, post, **Status at repost** and **Created at**, newest first, a search box (username) and a **By status at repost** filter. No **Add repost** button; a repost's page only shows the values (no Save, no Delete: they answer 403 if you type the address). |
| http://localhost:8000/admin/social/bookmark/ | **Bookmarks**: user, post and **Created at**, read-only like the follows. This list exists for the superuser's own housekeeping; nothing else in the product ever shows it. |
| Log out, log in as `part7b-mod-<id>@example.test` (password above) and open http://localhost:8000/admin/ | **Reposts** is listed (read-only). **Bookmarks is not listed at all.** |
| As the moderator open http://localhost:8000/admin/social/bookmark/ and `…/bookmark/add/` | **403** for both, although this account has `view`, `add`, `change` and `delete` for bookmarks: nobody but a superuser can open the list (user decision 2026-10-10). |

- Reposts are read-only because a repost changes only through the service (it must clear the reposter's cached feed
  and respect the rules). Bookmarks are private by design (ARCHITECTURE §4d): no moderator permission, now or after Part
  10, opens them.
- Covered by `test_admin_repost_bookmark.py` (including a moderator holding all five bookmark permissions) and, for these
  clicks, a scripted browser run; not clicked by a person.

#### Step 19: Stop and clean up

**Where:** Every terminal window, plus the browser.

- Stop the servers: `Ctrl+C` in windows 1 and 3 (a leftover `next dev`: step 12 of Part 1).
- Delete the test accounts, their posts, follows, likes, reposts and bookmarks (all go with the accounts). In window 2, in `backend\` with the
  venv active:

  ```powershell
python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(email__startswith='part7b-').delete())" | Select-Object -Last 1
```

  After one clean run of steps 3 to 13 of this guide it prints `(39, {'social.Like': 1, 'social.Repost': 7, 'social.Bookmark': 6, 'social.Follow': 2, 'account.EmailAddress': 6, 'posts.Post': 11, 'accounts.User': 6})`:
  how many rows went in all, and per table (11 posts: ten by `bo`, among them the removed one, the deleted one (still a
  row) and the two made while `cy` was reading, and `ada`'s own; 7 reposts: `ada` still holds the tram post, the
  harbour fact, the third fact, the late post and the one made while `cy` was reading, `cy` the tram post and `eve` the
  same one (the solar repost was undone and the two planted ones were taken back); 6 bookmarks: `ada`'s five (the tram
  post, her own, the FALSE one and the two planted on the removed and the deleted post) and `gus`'s; 1 like, `gus`'s; 2
  follows, `cy` of `ada` and of `bo`). Your count differs if you did the browser steps (more reposts, bookmarks and
  likes) or step 18 (one more account, with its permissions). Nothing else is touched.
  (The E2E tests' accounts stay in your local database, as in earlier parts: Django Admin → Users deletes them.)
  If you made a throwaway moderator for step 18, that goes too (same prefix).
- `docker compose down` (repo root) stops the containers and keeps the data; `docker compose down -v`
  wipes the whole local database, which is destructive.
- No secret was used or printed in this part: the only values in the commands are Cloudflare's public test
  token and the throwaway password of the test accounts.

### Part 8: Reporting & threshold

Needs Part 0A's containers and virtualenv, Part 0C's frontend, and your own `backend\.env` and
`frontend\.env.local`. Part 8 adds **one migration** (`reports.0001_initial`: the reports table), **two new Django
apps** (`apps/reports` and `apps/pipeline`, which holds only `routing.py` so far), **no dependency** and **no new
variable** (the `report` rate of 10 an hour and the four report settings were already there). It adds the endpoint
`POST /api/v1/posts/{id}/report/`, fills `reported_by_me` in every post, adds the **flag button** and the **report
dialog**, and closes one gap in Part 7B: a post under review that was FALSE before the review can't be reposted.

**Which terminal window for what.** Open the windows once and keep using the same ones:

| Window | What runs in it | Used in steps |
|---|---|---|
| Window 1 (server) | `python manage.py runserver` in `backend\`, venv active. Leave it running. Start it in step 3, **after** step 2 (Playwright starts its own servers and needs ports 3000 and 8000 free). | 3 to 13 |
| Window 2 (commands) | All the `curl.exe` and `python manage.py` commands. **Use the same window for steps 3 to 9**: the variables and functions you set in step 3 (`$id`, `$ada`, `$bo`, `$cy`, `$dee`, `$ed`, `$fay`, `$gus`, `$hal`, `$ivy`, `$api`, `$op1`, `$fact1`, `Mk`, `Send`, `Fetch`, and the helpers later steps add) only live in that one terminal. If you close it, redo step 3. | 1 to 9, 14 |
| Window 3 (frontend) | `npm run dev` in `frontend\`. Leave it running. | 10 to 13 |
| Browser | Steps 10 to 13 | 10 to 13 |

Things to know first:

- Steps 3 to 9 talk to the API directly with `curl.exe` (with `.exe`: in PowerShell 5.1 plain `curl` is a different command). Steps 10 to 13 use the
  browser. Step 3 makes nine accounts: `bo` writes the posts, five people (`ada`, `cy`, `ed`, `fay`, `gus`) each post
  once and then report, `hal` is verified but has **never posted or commented**, `dee` is never verified, and `ivy`
  is only there for the rate limit in step 9.
- **The PowerShell blocks below were not run on Windows.** The agent works on the Linux PC; it ran the bash twin of every command in the Linux guide on 2026-10-10, and the outputs below are those. The PowerShell commands follow the patterns Parts 1 to 7B proved on Windows (JSON written to a file and sent with `--data-binary "@file"`, `curl.exe`, no `&&`). If one behaves differently, tell the agent which.
- The API and page outputs below were recorded on Linux on 2026-10-10. The browser steps were checked the same
  day with headless Chromium (screenshots at 1280 and 390 px) and Django Admin with a scripted browser, not by a
  person at a keyboard. Ids, numbers in names, times and seconds differ on every run.
- Nothing here sends an email: step 3 marks the accounts verified with a shell command, which stands in for
  clicking the link (Part 2 shows the real flow). Steps 7 and 8 set a post's status or move a report's time the same
  way, because the pipeline and the moderator tools that do it for real arrive in Parts 9 and 10.
- **The numbers assume the default settings** (5 counting reports inside 24 hours, an account at least 24 hours old).
  The backend seeds them from your own `backend\.env` the first time, so check yours before step 6:

  ```powershell
  python manage.py shell -c "from apps.core.services import get_platform_settings as g; c = g(); print(c.report_threshold, c.report_window_hours, c.report_min_account_age_hours)" | Select-Object -Last 1
  ```

  It should print `5 24 24`. If not, the counts in steps 6 and 7 shift by the difference.
- **What Part 8 does and doesn't show:** a report is private and final (one per person and post, for life). It
  **counts toward the threshold** only if the account is at least 24 hours old, or the person has already taken part
  (a post that isn't removed or a comment that isn't hidden; posts and comments they deleted themselves still count).
  When 5 counting reports arrive inside 24 hours the post goes to **UNDER REVIEW** but stays visible; nothing is
  removed automatically. What moderators then do (Mark FALSE, Dismiss, Remove) is Part 10, the fact-check that gives
  a post a label is Part 9, the credibility credit for a good report is 11B and the notification to the author is 13.

#### Step 1: Run the automated backend checks

**Where:** Terminal window 2 (commands), starting in the repo root.

**What this does:** Starts the database containers, activates the Python environment, applies the new migration,
confirms there is no further one, then runs the whole backend test suite, the new tests, the linter and the
formatter check.

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero
docker compose up -d
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py migrate                            # Applying reports.0001_initial... OK
python manage.py makemigrations --check --dry-run   # No changes detected
python manage.py check                              # System check identified no issues (0 silenced).
python -m pytest                                    # 2066 passed
python -m pytest apps/reports apps/pipeline -q      # 182 passed
ruff check . ; ruff format --check .                # All checks passed! / 181 files already formatted
```

**You should see:** `Applying reports.0001_initial... OK` (nothing to apply the second time), `No changes detected` and
`System check identified no issues (0 silenced).`, then the full run ends with `2066 passed`, the new apps' run with
`182 passed`, and the last line pair is `All checks passed!` and `181 files already formatted`. (Counts may grow
later; what matters is that nothing fails.)

- The 182 new tests: `apps/pipeline/tests/test_routing.py` (45: every `merge_flag` pair, `enter_review` from every
  status, `apply_report_threshold` below, at and above the threshold, a removed post, an appeal), and in
  `apps/reports/tests/`: `test_models.py` (12: the unique pair, the five named checks, cascades),
  `test_counting.py` (23: the age rule at its exact edge, a young account with each kind of post and comment, deleted
  ones counting and moderated ones not), `test_threshold.py` (36: the report that reaches the threshold, every
  status it starts from, the window at its exact edge, dismissed and non-counting reports, every refusal),
  `test_races.py` (6: real threads: two simultaneous reports by one person make one, six people are all counted, a report
  waits for a concurrent delete or removal and is then a 404, and two reports waiting behind a held row lock still reach
  the threshold), `test_api_report.py` (44, including the real 10-an-hour limit), `test_reported_by_me.py` (8),
  `test_admin.py` (6) and `test_no_network.py` (2).
- Some more in `apps/social/tests/` (the new repost refusal) and `test_engagement_counts.py` (`reported_by_me` is
  read strictly like the other counts).
- `PostQuerySet.for_list(viewer)` now also tells you whether you reported each post, in the same query; every list
  keeps its query count.

#### Step 2: Run the automated frontend checks

**Where:** Terminal window 2, then `cd ..\frontend`. Playwright (the last two commands) starts Django and
Next itself, so **no servers may be running on ports 3000 and 8000** (it reuses them if they are, with
whatever settings they have).

**What this does:** Runs the linters, the type check, the component tests, the production build and the
end-to-end tests.

```powershell
cd ..\frontend                                      # from backend\
npm run lint ; npm run lint:tokens ; npm run typecheck ; npm run format:check
npm test                                            # 117 files, 1580 tests passed
npm run build
npm run test:e2e                                    # 38 passed
$env:CI = "1" ; npm run test:e2e ; Remove-Item Env:CI   # 38 passed (against the production build)
cd ..\backend                                       # back to backend\ for steps 3 to 9
```

**You should see:** the first line prints nothing from ESLint and TypeScript and ends with
`lint:tokens OK (…)` and `All matched files use Prettier code style!`. `npm test` ends with
`Test Files  117 passed (117)` and `Tests  1580 passed (1580)`. `npm run build` lists the same routes as in Part 7B
(Part 8 adds no route). Each E2E run ends with `38 passed`: the 36 earlier tests and 2 new ones in
`e2e/social.spec.ts` (one earlier phone test now checks five actions).

- On Windows `npm run build` can't blank `NEXT_PUBLIC_GOOGLE_CLIENT_ID` (PowerShell's `$env:NAME = ""` *deletes* the
  variable), so a `frontend\.env.local` with your real client ID is baked into that build and the CI-mode run is less
  representative than on Linux. The default run pins an empty client ID for both servers, so it is unaffected.
- The new E2E tests reuse the two people that file already signs up (allauth limits sign-ups to 20 a minute per
  address and the rest of the suite already uses most of that), so Part 8 adds **no** sign-up. A third person's post and
  the reports that bring it one short of the threshold are made straight in the database (`seedReports()` in
  `e2e/helpers.ts`, through the backend's own report service). The tests are: the form checks itself ("Choose a
  reason.", then "Tell us what's wrong." for "Something else"), the report is sent, the flag turns into "You reported
  this" and keeps focus, a reload shows the post UNDER REVIEW with its text still there, and the post page agrees; and
  no Report on your own post, with a visitor's flag a link to log in.

#### Step 3: Start the servers and make nine accounts and posts

**Where:** First window 1 (the Django server) and window 3 (the frontend), then window 2 (the commands).
**Keep using window 2 for steps 4 to 9.**

**What this does:** Windows 1 and 3 run the two servers. In window 2 you sign up nine accounts through the API and
mark eight of them verified (`dee` stays unverified), then `bo` posts an opinion and a fact with a DOI, and five
people each post an opinion (so their later reports count: a brand-new account with no activity doesn't count, step 7).
The helpers `mk` (make a post, print its id), `send` (any request, printing the status code and then the answer) and
`get` (the same for a GET) are used by every later step.

Window 1 (in `backend\`, venv active):

```powershell
python manage.py runserver                          # leave it running
```

Window 3:

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero\frontend
npm run dev                                         # leave it running
```

Window 2 (in `backend\` with the venv active: steps 1 and 2 leave you there). If you opened a new
terminal, first run `cd C:\Users\Nafis\Downloads\Rumor-Zero\backend` and `.\.venv\Scripts\Activate.ps1`:

```powershell
$id = Get-Date -Format "HHmmss"                     # a unique suffix so the addresses are new each run
$h = '-H', 'Origin: http://localhost:3000', '-H', 'X-Requested-With: rumor-zero'   # headers every auth call needs
function Signup($email, $username) {
@"
{"email": "$email", "username": "$username", "password": "correct-horse-battery-42", "turnstile_token": "XXXX.DUMMY.TOKEN.XXXX"}
"@ | Set-Content -Encoding ascii $env:TEMP\rz-signup.json
  (curl.exe -s @h -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-signup.json" http://localhost:8000/api/auth/app/v1/auth/signup | ConvertFrom-Json).meta.access_token
}
$ada = Signup "part8-ada-$id@example.test" "part8_ada_$id"      # $ada = ada's login token (reports, and the first reporter)
$bo = Signup "part8-bo-$id@example.test" "part8_bo_$id"         # $bo = bo's login token (the author of the posts)
$cy = Signup "part8-cy-$id@example.test" "part8_cy_$id"         # $cy .. $gus = four more people who report
$dee = Signup "part8-dee-$id@example.test" "part8_dee_$id"      # $dee = never verified
$ed = Signup "part8-ed-$id@example.test" "part8_ed_$id"
$fay = Signup "part8-fay-$id@example.test" "part8_fay_$id"
$gus = Signup "part8-gus-$id@example.test" "part8_gus_$id"
$hal = Signup "part8-hal-$id@example.test" "part8_hal_$id"      # $hal = verified, but has never posted or commented
$ivy = Signup "part8-ivy-$id@example.test" "part8_ivy_$id"      # $ivy = only used for the rate limit in step 9
python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(email__startswith='part8-', email__endswith='$id@example.test').exclude(username='part8_dee_$id').update(is_email_verified=True), 'accounts marked verified')" | Select-Object -Last 1
$api = 'http://localhost:8000/api/v1'
# Mk <token> <json>: makes a post, prints its id
function Mk($token, $json) {
  $json | Set-Content -Encoding ascii $env:TEMP\rz-post.json
  (curl.exe -s -H "Authorization: Bearer $token" -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-post.json" "$api/posts/" | ConvertFrom-Json).id
}
# Send <METHOD> <path> [token] [json body] [fields]: prints the HTTP status, then the answer. `fields` is a list
# of property names to keep, or a script block `{ param($r) ... }` that picks what to show from the answer.
function Send($method, $path, $token, $json, $show) {
  $a = @()
  if ($token) { $a += '-H', "Authorization: Bearer $token" }
  if ($json) {
    $json | Set-Content -Encoding ascii $env:TEMP\rz-body.json
    $a += '-H', 'Content-Type: application/json', '--data-binary', "@$env:TEMP\rz-body.json"
  }
  $out = curl.exe -s -w "`n%{http_code}" -X $method @a "$api$path"
  $body = if ($out.Count -gt 1) { $out[0..($out.Count - 2)] -join '' } else { '' }
  if ($show -and $body) {
    $r = $body | ConvertFrom-Json
    $shown = if ($show -is [scriptblock]) { & $show $r } else { $r | Select-Object $show }
    $body = ConvertTo-Json -InputObject $shown -Depth 5 -Compress
  }
  "$($out[-1])  $body"
}
function Fetch($path, $token, $show) { Send GET $path $token $null $show }   # Fetch <path> [token] [fields]
$op1 = Mk $bo '{"content":"I think the new tram line will change how the city moves.","post_type":"opinion"}'
$fact1 = Mk $bo '{"content":"Solar capacity grew by roughly 30% worldwide last year.","post_type":"fact","sources":["doi:10.1038/s41558-024-02102"]}'
foreach ($t in $ada, $cy, $ed, $fay, $gus) { Mk $t '{"content":"I enjoy the rain.","post_type":"opinion"}' | Out-Null }   # five people who have taken part
"$($ada.Substring(0,10)) $($bo.Substring(0,10)) $($hal.Substring(0,10))"      # three prefixes, not an error
"op1=$op1"; "fact1=$fact1"                                                    # two ids, not empty
```

**You should see** (the number in the names is your `id`, and the ids differ):

```text
8 accounts marked verified
eyJhbGciOi eyJhbGciOi eyJhbGciOi
op1=1b699450-7e9d-44ea-a24c-6a991dbb282a
fact1=9ed9ca08-f00a-416b-bee5-856a3bfd45d6
```

- The shell prints a line about auto-imported objects first; `Select-Object -Last 1` keeps only ours.
- Sign-up is limited to 20 a minute per address (Part 1), and still calls Cloudflare's test widget, so it
  needs internet. Nine sign-ups fit.

**If it differs:** an empty token or an `id` of `null` means the sign-up or the post failed: `runserver` isn't
running, or you signed up more than 20 times in a minute. Fix that and run this step again
from `$id = Get-Date …`.

#### Step 4: Report a post, and everything that is refused

**Where:** Terminal window 2 (the same terminal as step 3).

**What this does:** Reports a post through `POST /api/v1/posts/{id}/report/` and tries every refusal: one report per
person, a login, a verified email, your own post, a post that isn't there, and the three ways the body can be wrong.

```powershell
function Report($post, $token, $json) { Send POST "/posts/$post/report/" $token $json }   # Report <post id> <token> <json body>
Report $op1 $ada '{"reason":"inaccurate"}'                    # 1: ada's first report is 201
Report $op1 $ada '{"reason":"spam"}'                          # 2: the same person again: 409, for life
Report $op1 $null '{"reason":"spam"}'                         # 3: nobody logged in
Report $op1 $dee '{"reason":"spam"}'                          # 4: an unverified email
Report $op1 $bo '{"reason":"spam"}'                           # 5: bo can't report his own post
Report 00000000-0000-4000-8000-000000000000 $hal '{"reason":"spam"}'   # 6: no such post
Report not-a-uuid $hal '{"reason":"spam"}'                    # 7: not even an id
Report $op1 $hal '{}'                                         # 8: no reason
Report $op1 $hal '{"reason":"nonsense"}'                      # 9: not one of the five
Report $op1 $hal '{"reason":"other"}'                         # 10: "something else" needs words
Report $op1 $hal '{"reason":"other","details":"   "}'         # 11: and spaces are not words
Report $op1 $hal ('{"reason":"other","details":"' + ('x' * 501) + '"}')   # 12: 501 characters
Report $op1 $cy '{"reason":"other","details":"  It makes a claim about me that is not true.  "}'      # 13: cy's report, with details: 201
```

**You should see** (thirteen commands, thirteen answers):

```text
201  {"reported":true}
409  {"detail":"You already reported this post.","code":"already_reported"}
401  {"detail":"Authentication credentials were not provided.","code":"not_authenticated"}
403  {"detail":"Verify your email address first. Check your inbox for the link.","code":"email_unverified"}
403  {"detail":"You can't report your own post.","code":"cannot_report_own"}
404  {"detail":"Not found.","code":"not_found"}
404  {"detail":"Not found.","code":"not_found"}
400  {"reason":["Choose a reason."]}
400  {"reason":["Choose a reason."]}
400  {"details":["Tell us what's wrong."]}
400  {"details":["Tell us what's wrong."]}
400  {"details":["Keep it to 500 characters."]}
201  {"reported":true}
```

- A report is always the same `201 {"reported":true}`: the answer never says whether it sent the post to review.
- The second report by `ada` is `409`, and would be even if a moderator had dismissed her first one: one report
  per person and post, **for life**.
- Your own post is `403` (`cannot_report_own`); a removed or deleted post is the plain `404` of a post that never
  existed, **its author included**.
- Missing, `null` or unknown reasons all say "Choose a reason."; "Something else" needs words (`null`, empty and
  spaces don't count); details are trimmed and counted in characters, so an emoji is one.
- A 401 or an unverified email doesn't use up the allowance of 10 reports an hour (step 9); every other answer does,
  a 400 or a 409 included.

#### Step 5: `reported_by_me`, and what stays private

**Where:** Terminal window 2.

**What this does:** Reads the post as the person who reported it, as its author, as another person and as a
visitor, then checks that nothing else about reports shows in the post.

```powershell
Fetch "/posts/$op1/" $ada 'reported_by_me'            # 1: ada reported it: true
Fetch "/posts/$op1/" $bo 'reported_by_me'             # 2: the author: false
Fetch "/posts/$op1/" $null 'reported_by_me'           # 3: a visitor: false
Fetch "/posts/" $cy { param($r) @($r.results | Where-Object { $_.post.id -eq $op1 } | ForEach-Object { $_.post.reported_by_me }) }   # 4: in the Recent list, for cy: true
Fetch "/posts/" $ed { param($r) @($r.results | Where-Object { $_.post.id -eq $op1 } | ForEach-Object { $_.post.reported_by_me }) }   # 5: in the same list, for ed (who has not reported): false
Fetch "/posts/$op1/" $bo { param($r) @($r.PSObject.Properties.Name | Where-Object { $_ -match 'report|flag' }) }                      # 6: nothing about reports leaks except your own flag
```

**You should see:**

```text
200  {"reported_by_me":true}
200  {"reported_by_me":false}
200  {"reported_by_me":false}
200  [true]
200  [false]
200  ["reported_by_me"]
```

- Only the person who reported sees `true` (1, 4); the author, someone else and a visitor see `false`. It is the
  same flag in Recent, the Following feed, a profile's posts, your bookmarks and the post page.
- The post has no report count, no reasons and no reporter: the only key that mentions reports is your own flag (6).

#### Step 6: Five counting reports send a post to review, and it stays visible

**Where:** Terminal window 2.

**What this does:** Adds three more reports to the tram post (it has two from step 4) and watches its status after
each stage. The `state` helper prints the post's status, why it is under review, what it was before, and the lifetime
report counter.

```powershell
function State($post) { python manage.py shell -c "from apps.posts.models import Post; p = Post.objects.get(pk='$post'); print(p.status, p.flagged_reason, p.pre_review_status, 'report_count=%d' % p.report_count)" | Select-Object -Last 1 }   # State <post id>
State $op1                                            # 1: two reports so far (ada and cy)
Report $op1 $ed '{"reason":"misleading"}'             # 2: the third
Report $op1 $fay '{"reason":"spam"}'                  # 3: the fourth
State $op1                                            # 4: still published
Report $op1 $gus '{"reason":"harassment"}'            # 5: the fifth: the same answer as any other report
State $op1                                            # 6: now under review
Fetch "/posts/$op1/" $null 'status', 'content'        # 7: but it is still visible, with its text, to a visitor
Fetch "/posts/" $null { param($r) @($r.results | Where-Object { $_.post.id -eq $op1 } | ForEach-Object { $_.post.status }) }   # 8: and still in Recent
```

**You should see:**

```text
published None None report_count=2
201  {"reported":true}
201  {"reported":true}
published None None report_count=4
201  {"reported":true}
under_review reports published report_count=5
200  {"status":"under_review","content":"I think the new tram line will change how the city moves."}
200  ["under_review"]
```

- Four counting reports leave the post as it was; the fifth moves it to `under_review` with `flagged_reason` `reports`
  and remembers it was `published`, so a moderator's **Dismiss** (Part 10) can put it back.
- The post **stays visible**: a visitor still reads its text (7) and it is still in Recent (8). Reports never hide
  a post; a moderator decides.
- `report_count` is the lifetime counter of every report, counting or not.

#### Step 7: What counts

**Where:** Terminal window 2.

**What this does:** Shows the two rules that decide whether a report counts: a brand-new account with no activity
doesn't, and a report older than the window stops counting. The `flags` helper lists each reporter and whether their
report counts; `counting` counts the open, counting reports inside the window.

```powershell
function Flags($post) { python manage.py shell -c "from apps.reports.models import Report; print(sorted((r.reporter.username.rsplit('_', 2)[1], r.counts_toward_threshold) for r in Report.objects.filter(post_id='$post')))" | Select-Object -Last 1 }   # Flags <post id>
function Counting($post) { python manage.py shell -c "import datetime; from django.utils import timezone; from apps.core.services import get_platform_settings; from apps.reports.models import Report; c = get_platform_settings(); n = Report.objects.filter(post_id='$post', status='open', counts_toward_threshold=True, created_at__gte=timezone.now() - datetime.timedelta(hours=c.report_window_hours)).count(); print('counting reports in the window:', n, 'of', Report.objects.filter(post_id='$post').count())" | Select-Object -Last 1 }   # Counting <post id>
Report $fact1 $hal '{"reason":"inaccurate"}'          # 1: hal has never posted or commented, and the account is new
Flags $fact1                                          # 2: stored as "does not count"
Fetch "/posts/$fact1/" $null 'status'                 # 3: so it does not move the post
$hal1 = Mk $hal '{"content":"My first post.","post_type":"opinion"}'   # 4: hal takes part
Report $op1 $hal '{"reason":"spam"}'                  # 5: now a report by hal counts
Flags $op1                                            # 6: six reports, all counting
Counting $op1                                         # 7: inside the 24-hour window
python manage.py shell -c "import datetime; from django.utils import timezone; from apps.reports.models import Report; r = Report.objects.filter(post_id='$op1', reporter__username='part8_ada_$id').get(); r.created_at = timezone.now() - datetime.timedelta(hours=25); r.save(); print('one report moved 25 hours back')" | Select-Object -Last 1
Counting $op1                                         # 8: it fell out of the window
```

**You should see** (the order of the list is by name):

```text
201  {"reported":true}
[('hal', False)]
200  {"status":"pending"}
201  {"reported":true}
[('ada', True), ('cy', True), ('ed', True), ('fay', True), ('gus', True), ('hal', True)]
counting reports in the window: 6 of 6
one report moved 25 hours back
counting reports in the window: 5 of 6
```

- `hal`'s first report is stored as "does not count" (2): the account is under 24 hours old and has no post or
  comment, which is how a crowd of fresh sign-ups is kept from sending a post to review. It still adds to the
  lifetime counter, but the post doesn't move (3).
- After `hal` posts something (4) a report from `hal` counts (6). A post or comment the person **deleted** still counts;
  one a moderator removed or hid doesn't.
- A report older than 24 hours (the window, from the settings) stops counting toward the threshold (8). It stays on
  record. Once a post is under review it stays there; only a moderator moves it back.

#### Step 8: A FALSE post goes to review too, and can't be reposted meanwhile

**Where:** Terminal window 2.

**What this does:** Labels a fact FALSE (a shell command stands in for the moderator tools of Part 10), has five people
report it, and then tries to repost it. Reports can move a post that is labelled FALSE to review, which shows
UNDER REVIEW instead of FALSE; the page remembers what it was.

```powershell
$false1 = Mk $bo '{"content":"The moon is made of green cheese.","post_type":"fact"}'
python manage.py shell -c "from apps.posts.models import Post; print(Post.objects.filter(pk='$false1').update(status='verified_false', verdict_source='moderator'), 'post marked FALSE')" | Select-Object -Last 1
Fetch "/posts/$false1/" $null 'status'                # 1: labelled FALSE
foreach ($t in $ada, $cy, $ed, $fay, $gus) { Report $false1 $t '{"reason":"inaccurate"}' }   # 2: five people report it
Fetch "/posts/$false1/" $null 'status'                # 3: now UNDER REVIEW (it was FALSE until the reports)
State $false1                                         # 4: and it remembers it was FALSE
Send POST "/posts/$false1/repost/" $hal               # 5: it can't be reposted meanwhile, as before
Send POST "/posts/$op1/repost/" $hal                  # 6: a post that was never FALSE can be reposted while under review
```

**You should see:**

```text
1 post marked FALSE
200  {"status":"verified_false"}
201  {"reported":true}
201  {"reported":true}
201  {"reported":true}
201  {"reported":true}
201  {"reported":true}
200  {"status":"under_review"}
under_review reports verified_false report_count=5
409  {"detail":"Posts labelled FALSE can't be reposted.","code":"cannot_repost_false"}
201  {"reposted":true}
```

- After the fifth report the post shows UNDER REVIEW (3), with `pre_review_status` `verified_false` (4): a moderator's
  **Dismiss** puts the FALSE label back (Part 10).
- It can't be reposted meanwhile (5): otherwise a group could report a FALSE post to reopen it to reposts. The check
  is the same `409` `cannot_repost_false` as for a FALSE post. The page can't know this in advance (the earlier status
  is never public), so the repost button answers with the toast "Posts labelled FALSE can't be reposted."
- A post that was never FALSE can be reposted while it is under review (6), as in Part 7B.

#### Step 9: Reporting is rate limited

**Where:** Terminal window 2.

**What this does:** Uses up `ivy`'s allowance of 10 reports an hour. `bo` makes 11 posts for her to report; the
eleventh request is refused.

```powershell
$ids = 1..11 | ForEach-Object { Mk $bo "{`"content`":`"Post number $_ for the limit.`",`"post_type`":`"opinion`"}" }   # bo makes 11 posts
1..10 | ForEach-Object { Report $ids[$_ - 1] $ivy '{"reason":"spam"}' } | Group-Object | ForEach-Object { "$($_.Count) $($_.Name)" }   # 1: ivy reports ten of them
Report $ids[10] $ivy '{"reason":"spam"}'              # 2: the eleventh in an hour
'{"reason":"spam"}' | Set-Content -Encoding ascii $env:TEMP\rz-report.json
curl.exe -s -i -X POST -H "Authorization: Bearer $ivy" -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-report.json" "$api/posts/$($ids[10])/report/" | Select-String -Pattern '^Retry-After'   # 3: how long to wait
Send POST "/posts/$($ids[10])/like/" $ivy             # 4: likes have their own allowance
```

**You should see** (the seconds differ):

```text
     10 201  {"reported":true}
429  {"detail":"Request was throttled. Expected available in 3600 seconds.","code":"throttled"}
Retry-After: 3600
201  {"liked":true}
```

- Ten reports went through, the eleventh was refused with `429`, `"code":"throttled"` and a `Retry-After` in seconds.
- Likes have their own allowance (4), so a like still works. A 401 or an unverified email never counts; a 400 does
  (the tests cover both, with the real 10 requests).

#### Step 10: The flag and the report dialog

**Where:** Browser, with `runserver` (window 1) and `npm run dev` (window 3) running. Log in at
http://localhost:3000/login as `part8-cy-<id>@example.test` (use the `id` from step 3: type `$id`) with the password
`correct-horse-battery-42` (`cy` was verified in step 3).

**What this does:** Looks at the flag on the cards and walks through the dialog, as a signed-in reader.

| Do this | Expect |
|---|---|
| Open http://localhost:3000/home | Every card ends with a hairline, then (left) a **heart**, a **speech bubble** and a **two-arrow repost glyph** with counts, and (right) a small **bookmark** glyph and a small **flag**. `cy`'s own post ("I enjoy the rain.") has **no flag**. The tram post (`cy` reported it in step 4) has a **filled blue flag**, and shows **UNDER REVIEW** with its text. |
| Click the flag on "Solar capacity grew by roughly 30% worldwide last year." | A dialog **"Report this post"** with a small label "REPORT" above its title and a flag glyph beside it. It quotes the post in a grey card (author, handle, the claim in serif). Below: **"Why are you reporting this post?"** with five cards: **False or inaccurate**, **Missing context or misleading**, **Harassment or defamation**, **Spam or fake accounts**, **Something else**, each with one plain line. **None is chosen.** The first radio has the focus ring. Under them a **Details** box with "0 / 500 characters" and "Optional.". At the bottom a light-blue note **"What happens next"** (scroll the dialog if you can't see it), and in the footer a fingerprint and "Reports are private. The author is never told who reported.", **Cancel** and **Submit report**. |
| Click **Submit report** with nothing chosen | A red **"Choose a reason."** under the five cards; the focus goes to the first one; nothing is sent. |
| Choose **Something else** (the Details hint becomes "Required for “Something else”."), click **Submit report** | A red **"Tell us what's wrong."** under the box, and the focus goes to the box. Typing clears it. |
| Type a sentence in Details and click **Submit report** | The button shows a spinner for a moment, then the dialog closes and a toast says **"Report sent. Thank you."** The flag is now **filled and blue**, and **keyboard focus is on it**. |
| Click the filled flag | Nothing opens; a toast says "You already reported this post." Hover it: the tooltip says "You reported this". |
| Reload the page | The flag is still filled. The post is **not** under review: it has two reports (`hal`'s and `cy`'s) and only one of them counts. |
| Open a private window and go to /home (a visitor) | The same cards. The flag is a **link**: it points to `/login?next=%2Fp%2F<id>` and its tooltip says "Log in to report". |
| In another window log in as `dee` (`part8-dee-<id>@example.test`, same password: never verified) and click a flag | It looks dimmed and no dialog opens; a toast says "Verify your email to report posts. Check your inbox for the link." |

- Choosing a reason clears its error; the dialog can't be closed (Esc, ×, Cancel) while a report is being sent, and its
  fields are locked meanwhile.
- If the server refuses after the request (a 429 after ten reports, a network error), the dialog stays open with your
  choices and says so, for example "You're reporting too fast. Try again in about 60 minutes." (the unit tests cover every
  answer; step 9 shows the 429 itself).
- Covered by `ReportModal.test.tsx` (every state above, each server answer, the locked form, the focus after a server error),
  `ReportButton.test.tsx` (visitor, loading, own post, unverified, reported, resync from the server, the same button
  keeping focus), `PostActions.test.tsx`, `FeedList.test.tsx` and the new E2E tests.
- No dialog exists until a flag is clicked: a feed of 20 cards carries 20 flags and no dialog.

#### Step 11: The post page, your own posts and the under-review badge

**Where:** Browser, logged in as `cy`, with both servers running.

**What this does:** Opens the post page, where the flag has a word, and checks the places where there must be no flag.

| Do this | Expect |
|---|---|
| Click the tram post's text on /home | The post page. The claim card shows **UNDER REVIEW** and the full text. The action row reads **Like, Comments, Repost** with words (from 640 px up), the **bookmark** glyph, then a **filled blue flag with the word "Reported"**, and **Copy link**. |
| Open the page of "Solar capacity grew …" (the post you reported in step 10) | The same row with **"Reported"**. |
| Open a post that `cy` has not reported (for example the first "Post number 1 for the limit.") | The row ends with an outline flag and **"Report"**. Click it: the same dialog opens. Press **Esc**: it closes and focus returns to the flag. |
| Open the page of `cy`'s own post (click "I enjoy the rain." on /home, the one by `cy`) | The row has **no flag and no Report**, only the other buttons and a **Delete** button. |

- A removed post can't be made here (moderator removal arrives with Part 10); its page has no Report, covered by
  `PostDetail.test.tsx` along with a Report for a reader, a log-in link for a visitor, "You reported this" from the
  signed-in view and none on your own post. The E2E tests cover the rest.

#### Step 12: A phone-sized window

**Where:** Browser, logged in as `cy`.

**What this does:** Checks the new parts at phone width. In Firefox or Chrome press `F12`, then the "responsive
design" / device toolbar button, and set the width to 390.

| Do this | Expect |
|---|---|
| Open /home | Each card's bar (heart, count, bubble, count, repost, count, and the bookmark and flag at the right) fits on one line under the claim. **No sideways scrolling.** |
| Click a flag | The dialog fits the screen: its body scrolls, the footer (the privacy line, then **Cancel** and **Submit report**) stays at the bottom, and there is **no sideways scrolling**. A long claim in the quote is cut after three lines. |
| Open a post's page | The action row holds the glyphs with their counts only (the words are hidden below 640 px), the bookmark, the flag and **Copy link**, wrapping to a second line if needed. |

- Measured with headless Chromium at 390 px: 0 px of horizontal overflow on `/home`, in the open dialog and on a post's
  page.

#### Step 13: Django Admin: reports

**Where:** Browser, while `runserver` is running in window 1.

**What this does:** Opens the new admin list as a superuser. Reports are read-only: they are written only by the
report service (it holds the row lock and works out whether the report counts); resolving them is Part 10.

| URL / action | Expect |
|---|---|
| http://localhost:8000/admin/ (superuser from Part 0A; if it 404s, `ADMIN_URL_PATH` in `backend\.env` isn't `admin/`: use that path) | **Reports** is listed in the sidebar. |
| http://localhost:8000/admin/reports/report/ | **Select report to view**: post, reporter, **Reason**, status, whether it counts toward the threshold and the time, newest first; a search box (reporter username) and filters **By status**, **By reason**, **By counts toward threshold** and **By created at**. The list **never shows the details text**. No **Add report** button. |
| Click a report whose reason is **Something else** | Its page shows the details you typed, read-only: no **Save**, no **Delete**. http://localhost:8000/admin/reports/report/add/ answers **403**. |

- A moderator gets no permissions at all until Part 10 (it also adds the review queue and **Dismiss**), so a moderator who opens
  the list is refused (403) today; with only `view_report` they could read it but not change anything. Covered by
  `test_admin.py`; the superuser clicks above were run with a scripted browser, not by a person.

#### Step 14: Stop and clean up

**Where:** Every terminal window, plus the browser.

- Stop the servers: `Ctrl+C` in windows 1 and 3 (a leftover `next dev`: step 12 of Part 1).
- Delete the test accounts, their posts, reposts, likes and reports (all go with the accounts). In window 2, in `backend\` with
  the venv active:

  ```powershell
  python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(email__startswith='part8-').delete())" | Select-Object -Last 1
  ```

  After one clean run of steps 3 to 9 of this guide it prints `(62, {'social.Like': 1, 'social.Repost': 1, 'reports.Report': 22, 'account.EmailAddress': 9, 'posts.Post': 20, 'accounts.User': 9})`:
  how many rows went in all, and per table (22 reports: 2 and then 3 on the tram post, 2 by `hal`, 5 on the FALSE post and
  10 by `ivy`; 20 posts: 14 by `bo` (the tram post, the solar fact, the FALSE one and the 11 for the limit), `hal`'s one and
  the five opinions; 1 repost, `hal`'s of the tram post; 1 like, `ivy`'s). Your count differs if you did the browser steps
  (more reports) or made other accounts. Nothing else is touched.
  (The E2E tests' accounts stay in your local database, as in earlier parts: Django Admin → Users deletes them.)
- `docker compose down` (repo root) stops the containers and keeps the data; `docker compose down -v`
  wipes the whole local database, which is destructive.
- No secret was used or printed in this part: the only values in the commands are Cloudflare's public test
  token and the throwaway password of the test accounts.

### Part 9: Fact-check pipeline stub + routing

Needs Part 0A's containers and virtualenv, Part 0C's frontend, and your own `backend\.env` and
`frontend\.env.local`. Part 9 adds **no migration**, **no dependency** and **no new variable** (`PIPELINE_BACKEND`,
`PIPELINE_INLINE_KICK`, `PIPELINE_URL`, `PIPELINE_API_KEY` and `INTERNAL_CRON_SECRET` were already in
`backend\.env.example`; Django now reads them). It makes fact posts get a verdict: the built-in **stub pipeline**, the
rules that turn its answer into VERIFIED, FALSE or UNDER REVIEW, and three ways to run it: the **inline kick** (a
background thread right after a fact is saved), the hourly **tick** `POST /api/internal/tick/` (cron-job.org, Part
17) and `python manage.py process_pending` for local dev.

**Which terminal window for what.** Open the windows once and keep using the same ones:

| Window | What runs in it | Used in steps |
|---|---|---|
| Window 1 (server) | `python manage.py runserver` in `backend\`, venv active. Leave it running. Start it in step 3, **after** step 2 (Playwright starts its own servers and needs ports 3000 and 8000 free). Step 7 restarts it with the kick off and step 12 restarts it normally. | 3 to 14 |
| Window 2 (commands) | All the `curl.exe` and `python manage.py` commands. **Use the same window for steps 3 to 11**: the variables and functions you set in step 3 (`$id`, `$ada`, `$bo`, `$cy`, `$dee`, `$api`, `Mk`, `Send`, `Fetch`) and later (`$t1` … `$o1`, `$src`, `$k1` … `$k3`, `$secret`, `Tick`, `$l1`, `$r1`, `$f1`) only live in that one terminal. If you close it, redo step 3. | 1 to 11, 15 |
| Window 3 (frontend) | `npm run dev` in `frontend\`. Leave it running. | 12 to 14 |
| Window 4 (sweeper) | `python manage.py process_pending --loop` in `backend\`, venv active, for one step | 9 |
| Browser | Steps 12 to 14 | 12 to 14 |

Things to know first:

- **The stub's rules** (ARCHITECTURE §6): a fact whose text contains `#true` gets VERIFIED 95%, `#false` gets FALSE
  92%, `#unsure` goes to UNDER REVIEW (confidence 40). The first of these tags in the text wins, in any case, and only
  as a whole tag (`#trueish` is not one). Any other text gets a confidence of 50 to 99 and "true" or "false" from a
  hash of the text, so the same text always gets the same answer; below the threshold (85) it goes to UNDER REVIEW.
  Opinions are never checked. The stub ignores sources (a real pipeline would read them).
- **Not for production as it is** (user decision 2026-10-11, a launch blocker for Part 17): with the stub any
  author can write `#true` to get VERIFIED 95%.
- Steps 3 to 11 talk to the API with `curl.exe` (with `.exe`: in PowerShell 5.1 plain `curl` is a different command)
  and to Django with `python manage.py shell`. Steps 12 to 14 use the browser. Step 3 makes four verified accounts:
  `ada` posts the facts of steps 4 to 6, `bo` and `cy` those of steps 7 to 10, `dee` reposts in step 10 and posts in
  step 11 and in the browser.
- **The PowerShell blocks below were not run on Windows.** The agent works on the Linux PC; it ran the bash twin of every command in the Linux guide on 2026-10-11, and the outputs below are those. The PowerShell commands follow the patterns Parts 1 to 8 proved on Windows (JSON written to a file and sent with `--data-binary "@file"`, `curl.exe`, no `&&`; a multi-line Python snippet is piped into `python manage.py shell` as a here-string). If one behaves differently, tell the agent which.
- The API and command outputs below were recorded on Linux on 2026-10-11. The browser steps were checked the same day
  with headless Chromium (screenshots at 1280 and 390 px) and Django Admin with a scripted browser, not by a person at
  a keyboard. Ids, numbers in names, times and seconds differ on every run.
- Nothing here sends an email: step 3 marks the accounts verified with a shell command, which stands in for clicking
  the link (Part 2 shows the real flow). Step 10 puts a post under review the same way, standing in for five reports
  (Part 8 shows real ones), and step 11 stands in a pipeline that never answers for the stub.
- **The numbers assume the default settings** (confidence threshold 85, 10 fact posts per person per 24 hours). The
  backend seeds them from your own `backend\.env` the first time; step 3 prints yours.
- Every check is logged in window 1 (or in window 2 when a `python manage.py` command runs it), one line per post:
  `… INFO apps.pipeline.processor: Pipeline: post <id> -> labelled` (or `entered_review`, `updated_review`, `retry`).
- The texts of the posts are plain ASCII on purpose: `Set-Content -Encoding ascii` would turn a `°` into `?`.

#### Step 1: Run the automated backend checks

**Where:** Terminal window 2 (commands), starting in the repo root.

**What this does:** Starts the database containers, activates the Python environment, confirms there is no migration
to apply or make, then runs the whole backend test suite, Part 9's tests, the linter and the formatter check.

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero
docker compose up -d
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py migrate                            # No migrations to apply.
python manage.py makemigrations --check --dry-run   # No changes detected
python manage.py check                              # System check identified no issues (0 silenced).
python -m pytest                                    # 2359 passed
python -m pytest apps/pipeline apps/core/tests/test_tick.py apps/posts/tests/test_services_pipeline.py -q   # 312 passed
ruff check . ; ruff format --check .                # All checks passed! / 200 files already formatted
```

**You should see:** `No migrations to apply.`, `No changes detected` and `System check identified no issues (0
silenced).`, then the full run ends with `2359 passed`, the pipeline run with `312 passed`, and the last line pair is
`All checks passed!` and `200 files already formatted`. (Counts may grow later; what matters is that nothing fails.)

- The pipeline run holds Part 8's 45 routing tests and 267 new ones: `test_contract.py` (61), `test_stub_client.py`
  (29), `test_http_client.py` (35), `test_routing_pipeline.py` (55: every pipeline row of the ARCHITECTURE §4 table),
  `test_queue.py` (8), `test_processor.py` (32), `test_races.py` (5, real threads), `test_kick.py` (10),
  `test_command.py` (7), `test_no_network.py` (1), plus `apps\core\tests\test_tick.py` (11) and
  `apps\posts\tests\test_services_pipeline.py` (13). The Linux guide's step 1 says what each covers.
- Some more in `apps\core\tests\test_settings.py` (the four `PIPELINE_*` variables are checked at startup) and in
  `apps\posts\tests\` (who decided a label is public only with the label).

#### Step 2: Run the automated frontend checks

**Where:** Terminal window 2, then `cd ..\frontend`. Playwright (the last two commands) starts Django and
Next itself, so **no servers may be running on ports 3000 and 8000** (it reuses them if they are, with
whatever settings they have; a reused Django must also run with `PIPELINE_INLINE_KICK=False`).

**What this does:** Runs the linters, the type check, the component tests, the production build and the
end-to-end tests.

```powershell
cd ..\frontend                                      # from backend\
npm run lint ; npm run lint:tokens ; npm run typecheck ; npm run format:check
npm test                                            # 117 files, 1587 tests passed
npm run build
npm run test:e2e                                    # 38 passed
$env:CI = "1" ; npm run test:e2e ; Remove-Item Env:CI   # 38 passed (against the production build)
cd ..\backend                                       # back to backend\ for steps 3 to 11
```

**You should see:** the first line prints nothing from ESLint and TypeScript and ends with
`lint:tokens OK (…)` and `All matched files use Prettier code style!`. `npm test` ends with
`Test Files  117 passed (117)` and `Tests  1587 passed (1587)`. `npm run build` lists the same routes as in Part 8
(Part 9 adds no page). Each E2E run ends with `38 passed`.

- On Windows `npm run build` can't blank `NEXT_PUBLIC_GOOGLE_CLIENT_ID` (PowerShell's `$env:NAME = ""` *deletes* the
  variable), so a `frontend\.env.local` with your real client ID is baked into that build and the CI-mode run is less
  representative than on Linux. The default run pins an empty client ID for both servers, so it is unaffected.
- Part 9 changes no page: the verdict copy ("Checked automatically · 95% confidence", "Reviewed by a moderator") and
  the badge polling came with Part 5. Seven new component tests pin the badges and the copy for the stub's real
  answers.
- The E2E backend runs with the stub and **without the kick** (`playwright.config.ts`): several tests need a new fact
  to stay CHECKING FACTS…. The test "a #true fact is checked by the pipeline and its badge turns VERIFIED by itself"
  (in `e2e\post-detail.spec.ts`, which used to flip the status by hand) now runs the real pipeline for its own post
  only (`processPost()` in `e2e\helpers.ts`) and waits for VERIFIED 95% on the card and the post page. No new sign-up.

#### Step 3: Start the servers and make four accounts

**Where:** First window 1 (the Django server) and window 3 (the frontend), then window 2 (the commands).
**Keep using window 2 for steps 4 to 11.**

**What this does:** Windows 1 and 3 run the two servers, with your own settings (the kick is on). In window 2 you sign
up four accounts through the API, mark them verified, and print the pipeline settings the backend uses. The helpers
`Mk` (make a post, print its id), `Send` (any request, printing the status code and then the answer) and `Fetch` (the
same for a GET) are used by every later step.

Window 1 (in `backend\`, venv active):

```powershell
python manage.py runserver                          # leave it running
```

Window 3:

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero\frontend
npm run dev                                         # leave it running
```

Window 2 (in `backend\` with the venv active: steps 1 and 2 leave you there). If you opened a new
terminal, first run `cd C:\Users\Nafis\Downloads\Rumor-Zero\backend` and `.\.venv\Scripts\Activate.ps1`:

```powershell
$id = Get-Date -Format "HHmmss"                     # a unique suffix so the addresses are new each run
$h = '-H', 'Origin: http://localhost:3000', '-H', 'X-Requested-With: rumor-zero'   # headers every auth call needs
function Signup($email, $username) {
@"
{"email": "$email", "username": "$username", "password": "correct-horse-battery-42", "turnstile_token": "XXXX.DUMMY.TOKEN.XXXX"}
"@ | Set-Content -Encoding ascii $env:TEMP\rz-signup.json
  (curl.exe -s @h -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-signup.json" http://localhost:8000/api/auth/app/v1/auth/signup | ConvertFrom-Json).meta.access_token
}
$ada = Signup "part9-ada-$id@example.test" "part9_ada_$id"      # $ada = ada's login token (the facts of steps 4 to 6)
$bo = Signup "part9-bo-$id@example.test" "part9_bo_$id"         # $bo, $cy = the facts of steps 7 to 10
$cy = Signup "part9-cy-$id@example.test" "part9_cy_$id"
$dee = Signup "part9-dee-$id@example.test" "part9_dee_$id"      # $dee = reposts in step 10, posts in step 11 and the browser
python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(email__startswith='part9-', email__endswith='$id@example.test').update(is_email_verified=True), 'accounts marked verified')" | Select-Object -Last 1
$api = 'http://localhost:8000/api/v1'
# Mk <token> <json>: makes a post, prints its id
function Mk($token, $json) {
  $json | Set-Content -Encoding ascii $env:TEMP\rz-post.json
  (curl.exe -s -H "Authorization: Bearer $token" -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-post.json" "$api/posts/" | ConvertFrom-Json).id
}
# Send <METHOD> <path> [token] [json body] [fields]: prints the HTTP status, then the answer. `fields` is a list
# of property names to keep, or a script block `{ param($r) ... }` that picks what to show from the answer.
function Send($method, $path, $token, $json, $show) {
  $a = @()
  if ($token) { $a += '-H', "Authorization: Bearer $token" }
  if ($json) {
    $json | Set-Content -Encoding ascii $env:TEMP\rz-body.json
    $a += '-H', 'Content-Type: application/json', '--data-binary', "@$env:TEMP\rz-body.json"
  }
  $out = curl.exe -s -w "`n%{http_code}" -X $method @a "$api$path"
  $body = if ($out.Count -gt 1) { $out[0..($out.Count - 2)] -join '' } else { '' }
  if ($show -and $body) {
    $r = $body | ConvertFrom-Json
    $shown = if ($show -is [scriptblock]) { & $show $r } else { $r | Select-Object $show }
    $body = ConvertTo-Json -InputObject $shown -Depth 5 -Compress
  }
  "$($out[-1])  $body"
}
function Fetch($path, $token, $show) { Send GET $path $token $null $show }   # Fetch <path> [token] [fields]
python manage.py shell -c "from django.conf import settings; from apps.core.services import get_platform_settings as g; c = g(); print(settings.PIPELINE_BACKEND, settings.PIPELINE_INLINE_KICK, c.confidence_threshold, c.fact_posts_per_day)" | Select-Object -Last 1
"$($ada.Substring(0,10)) $($bo.Substring(0,10)) $($cy.Substring(0,10)) $($dee.Substring(0,10))"   # four prefixes, not an error
```

**You should see:**

```text
4 accounts marked verified
stub True 85 10
eyJhbGciOi eyJhbGciOi eyJhbGciOi eyJhbGciOi
```

- The second line is the pipeline (`stub`), the kick (`True`), the confidence threshold (`85`) and the fact posts each
  person may make in 24 hours (`10`; steps 4 to 11 need at most 9 per account). If your threshold isn't 85, the
  untagged facts in step 4 may land differently; if your allowance is lower, some posts are refused (empty ids).
- The shell prints a line about auto-imported objects first; `Select-Object -Last 1` keeps only ours.
- Sign-up is limited to 20 a minute per address (Part 1), and still calls Cloudflare's test widget, so it
  needs internet.

**If it differs:** an empty token means the sign-up failed: `runserver` isn't running, or you signed up more than 20
times in a minute. Fix that and run this step again from `$id = Get-Date …`.

#### Step 4: The inline kick checks each fact right after it is saved

**Where:** Terminal window 2 (the same terminal as step 3). Window 1 must be running `runserver` with your normal
settings (the kick on).

**What this does:** `ada` posts three facts with the stub's tags, three without, and an opinion. The answer to the
post itself still says `pending` (the check runs after the post is saved); a second later every fact has its verdict.

```powershell
'{"content":"Water boils at 100 degrees Celsius at sea level. #true","post_type":"fact"}' | Set-Content -Encoding ascii $env:TEMP\rz-post.json
$r = curl.exe -s -H "Authorization: Bearer $ada" -H "Content-Type: application/json" --data-binary "@$env:TEMP\rz-post.json" "$api/posts/" | ConvertFrom-Json
$r | Select-Object status, confidence_score, verdict_source | ConvertTo-Json -Compress   # 1: the 201 answer
$t1 = $r.id
$t2 = Mk $ada '{"content":"The Great Wall of China is visible from the Moon. #false","post_type":"fact"}'
$t3 = Mk $ada '{"content":"Coffee stunts your growth. #unsure","post_type":"fact"}'
$h1 = Mk $ada '{"content":"Honey never spoils.","post_type":"fact"}'
$h2 = Mk $ada '{"content":"Sharks are older than trees.","post_type":"fact"}'
$h3 = Mk $ada '{"content":"The Moon orbits the Earth.","post_type":"fact"}'
$o1 = Mk $ada '{"content":"I think tea beats coffee.","post_type":"opinion"}'
Start-Sleep 1                                       # the checks take a few milliseconds
foreach ($p in $t1, $t2, $t3, $h1, $h2, $h3, $o1) { Fetch "/posts/$p/" $null @('content', 'status', 'confidence_score', 'verdict_source') }   # 2 to 8
```

**You should see:**

```text
{"status":"pending","confidence_score":null,"verdict_source":null}
200  {"content":"Water boils at 100 degrees Celsius at sea level. #true","status":"verified_true","confidence_score":"95.00","verdict_source":"pipeline"}
200  {"content":"The Great Wall of China is visible from the Moon. #false","status":"verified_false","confidence_score":"92.00","verdict_source":"pipeline"}
200  {"content":"Coffee stunts your growth. #unsure","status":"under_review","confidence_score":null,"verdict_source":null}
200  {"content":"Honey never spoils.","status":"verified_true","confidence_score":"88.00","verdict_source":"pipeline"}
200  {"content":"Sharks are older than trees.","status":"verified_false","confidence_score":"95.00","verdict_source":"pipeline"}
200  {"content":"The Moon orbits the Earth.","status":"under_review","confidence_score":null,"verdict_source":null}
200  {"content":"I think tea beats coffee.","status":"published","confidence_score":null,"verdict_source":null}
```

- 1: a new fact is always `pending` in its own answer; the browser shows "Checking facts…" and its polling (Part 5)
  picks up the verdict (step 12).
- 2 to 4: the three tags. 5 to 7: no tag, so the hash of the text decides: "Honey never spoils." gets true at 88 and
  "Sharks are older than trees." false at 95 (both at or above 85, so labelled), "The Moon orbits the Earth." true at
  65, below the threshold, so a moderator decides (UNDER REVIEW). The same text always gets the same answer.
- Under review, the post shows no confidence and no "who decided": only a label shows them.
- 8: the opinion is `published` and never checked.
- Window 1 printed one `Pipeline: post … -> labelled` (or `-> entered_review`) line per fact, a few milliseconds
  after each post.

#### Step 5: What the pipeline stored, and what stays private

**Where:** Terminal window 2.

**What this does:** Reads three of the posts straight from the database, then checks that none of the pipeline's
own fields shows in the API.

```powershell
@"
from apps.posts.models import Post
for pk in '$t1 $t3 $h3'.split():
    p = Post.objects.get(pk=pk)
    print(p.status, p.flagged_reason, p.pre_review_status, p.pipeline_verdict, p.confidence_score, p.pipeline_result, p.pipeline_attempts, p.pipeline_next_attempt_at, round((p.pipeline_checked_at - p.created_at).total_seconds(), 2))
"@ | python manage.py shell | Select-Object -Last 3     # 1 to 3
Fetch "/posts/$t3/" $null { param($r) @($r.PSObject.Properties.Name | Where-Object { $_ -match 'pipeline|flag|attempt|review' }) }   # 4: none of it is public
Fetch "/posts/status/?ids=$t1,$t3" $null { param($r) @($r.results | Select-Object status, confidence_score, verdict_source) }   # 5: what the badge poller sees
```

**You should see** (the last number on lines 1 to 3, the seconds between posting and the verdict, differs):

```text
verified_true None None true 95.00 {'rule': '#true', 'stub': True} 1 None 0.03
under_review pipeline pending inconclusive 40.00 {'rule': '#unsure', 'stub': True} 1 None 0.01
under_review pipeline pending true 65.00 {'rule': 'hash', 'stub': True} 1 None 0.01
200  []
200  [{"status":"verified_true","confidence_score":"95.00","verdict_source":"pipeline"},{"status":"under_review","confidence_score":null,"verdict_source":null}]
```

- Each line: the status, why it is under review (`pipeline`: the check couldn't decide) and what it was before, then
  the pipeline's verdict, confidence and raw answer, the number of tries, when to try again (`None`: done), and how
  long after the post the verdict came.
- The verdict and confidence are kept even for a post under review: a moderator sees them in Django Admin (step 14),
  the public doesn't.

#### Step 6: The sources go to the pipeline in the author's order

**Where:** Terminal window 2.

**What this does:** `ada` posts a fact with two sources (a URL, then a DOI). The stub ignores them, but the request a
real pipeline would get (`{post_id, content, sources}`) carries them, in order; a fact without sources sends an empty
list. Nothing ever opens the links.

```powershell
$src = Mk $ada '{"content":"Solar capacity grew by roughly 30% worldwide last year. #true","post_type":"fact","sources":["https://www.iea.org/reports/renewables-2023","doi:10.1038/s41558-024-02102"]}'
foreach ($p in $src, $t1) { python manage.py shell -c "import json; from apps.pipeline.contract import PipelineRequest; from apps.posts.models import Post; print(json.dumps(PipelineRequest.for_post(Post.objects.get(pk='$p')).to_json()['sources']))" | Select-Object -Last 1 }   # 1 and 2
```

**You should see:**

```text
["https://www.iea.org/reports/renewables-2023", "10.1038/s41558-024-02102"]
[]
```

- 1: the URL first, then the DOI (stored bare, without `doi:`), as the author entered them. 2: the fact from step 4,
  which has none.
- The tests also check the body the HTTP client would send to a real pipeline, and that the only address it ever
  opens is `PIPELINE_URL` (`test_http_client.py`).

#### Step 7: With the kick off, facts wait until `process_pending` checks them

**Where:** First window 1, then window 2.

**What this does:** Restarts the server **without** the inline kick, the way it runs when the kick is missed (a worker
restart, a sleeping server). New facts then stay pending until something checks them: here the management command.

Window 1: press `Ctrl+C`, then:

```powershell
$env:PIPELINE_INLINE_KICK = "False" ; python manage.py runserver   # the kick off in this window (step 12 removes it); leave it running
```

Window 2:

```powershell
python manage.py process_pending | Select-Object -Last 1   # 1: first clears whatever was already waiting
$k1 = Mk $bo '{"content":"Mount Everest is the tallest mountain above sea level. #true","post_type":"fact"}'
$k2 = Mk $bo '{"content":"Lightning never strikes the same place twice. #false","post_type":"fact"}'
$k3 = Mk $bo '{"content":"Cracking your knuckles causes arthritis. #unsure","post_type":"fact"}'
Start-Sleep 1
foreach ($p in $k1, $k2, $k3) { Fetch "/posts/$p/" $null @('status') }                  # 2 to 4: nothing checked them
python manage.py process_pending                    # 5: checks the three
foreach ($p in $k1, $k2, $k3) { Fetch "/posts/$p/" $null @('status', 'confidence_score', 'verdict_source') }   # 6 to 8
python manage.py process_pending                    # 9: nothing left
```

**You should see** (the first number, the times and the ids differ):

```text
Processed 0 fact posts.
200  {"status":"pending"}
200  {"status":"pending"}
200  {"status":"pending"}
2026-10-10 19:12:51,727 INFO apps.pipeline.processor: Pipeline: post 50f256c2-fa78-4b3d-84d0-b7722b706d56 -> labelled
2026-10-10 19:12:51,733 INFO apps.pipeline.processor: Pipeline: post 0a17e2de-93dd-4595-b0e2-c04423d713d9 -> labelled
2026-10-10 19:12:51,737 INFO apps.pipeline.processor: Pipeline: post 069209e7-a9b5-417f-8706-789ca174f8c4 -> entered_review
Processed 3 fact posts.
200  {"status":"verified_true","confidence_score":"95.00","verdict_source":"pipeline"}
200  {"status":"verified_false","confidence_score":"92.00","verdict_source":"pipeline"}
200  {"status":"under_review","confidence_score":null,"verdict_source":null}
Processed 0 fact posts.
```

- 1: the end-to-end tests (step 2) leave pending facts in your local database, because their backend runs without the
  kick, so the first run checks those too: any number, 0 included (it printed `Processed 116 fact posts.` the first
  time on the Linux PC, then 0). `Select-Object -Last 1` hides their log lines.
- 5: one log line per post, then the count. One run checks **everything** that is due, in batches of 10
  (`--limit` changes the batch size).

#### Step 8: The tick needs the secret, and takes ten posts at a time

**Where:** Terminal window 2. Window 1 still runs without the kick.

**What this does:** The tick is what cron-job.org will call every hour (Part 17). It needs the `X-RZ-Cron-Secret`
header, read here from your own `backend\.env` without printing it. Then `bo` and `cy` leave twelve facts waiting and
three ticks clear them.

```powershell
$secret = (Select-String -Path .\.env -Pattern '^INTERNAL_CRON_SECRET=(.*)$').Matches.Groups[1].Value    # sets $secret; nothing is printed
# Tick [secret] [method]: prints the status, the answer and how long it took
function Tick($secret, $method = 'POST') {
  $a = @()
  if ($secret) { $a += '-H', "X-RZ-Cron-Secret: $secret" }
  $out = curl.exe -s -w "`n%{http_code} %{time_total}" -X $method @a http://localhost:8000/api/internal/tick/
  $last = $out[-1] -split ' '
  "$($last[0])  $($out[0..($out.Count - 2)] -join '')  ($($last[1]) s)"
}
Tick                                                # 1: no secret
Tick 'wrong-secret'                                 # 2: a wrong one
Tick $secret 'GET'                                  # 3: the right one, but not a POST
Tick $secret                                        # 4: nothing waits
foreach ($i in 1..6) { Mk $bo ('{{"content":"Backlog claim {0} from bo. #true","post_type":"fact"}}' -f $i) | Out-Null; Mk $cy ('{{"content":"Backlog claim {0} from cy. #false","post_type":"fact"}}' -f $i) | Out-Null }   # twelve facts wait
Tick $secret                                        # 5: ten of them
Tick $secret                                        # 6: the other two
Tick $secret                                        # 7: none left
```

**You should see** (the seconds differ):

```text
403  {"detail":"You do not have permission to perform this action.","code":"permission_denied"}  (0.001658 s)
403  {"detail":"You do not have permission to perform this action.","code":"permission_denied"}  (0.000825 s)
405  {"detail":"Method \"GET\" not allowed.","code":"method_not_allowed"}  (0.000850 s)
200  {"processed":0}  (0.008398 s)
200  {"processed":10}  (0.048147 s)
200  {"processed":2}  (0.017419 s)
200  {"processed":0}  (0.007578 s)
```

- Without the right secret the tick checks nothing. With it, it takes at most **10 posts** and answers in well under
  a second with the stub; cron-job.org gives it 30 s. It stops taking new posts so it always answers within about 25 s:
  a real pipeline, which may need up to 20 s per post, would check 1 to 5 per call (the tests cover that).
- Window 1 logs one line per post checked.

**If it differs:** if every tick is 403, `$secret` is empty: `INTERNAL_CRON_SECRET` is missing from `backend\.env`.

#### Step 9: The sweeper in a loop

**Where:** A new window 4, then window 2, then window 4 again.

**What this does:** `--loop` keeps checking every few seconds, a stand-in for the kick when you run the server without
it. `cy` posts a fact and the loop picks it up.

Window 4:

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero\backend
.\.venv\Scripts\Activate.ps1
python manage.py process_pending --loop --interval 2      # leave it running for now
```

Window 2:

```powershell
$l1 = Mk $cy '{"content":"Octopuses have three hearts. #true","post_type":"fact"}'
Start-Sleep 3                                       # one turn of the loop
Fetch "/posts/$l1/" $null @('status', 'confidence_score')
```

Then press `Ctrl+C` in window 4.

**You should see:** window 2 prints `200  {"status":"verified_true","confidence_score":"95.00"}`. Window 4 shows:

```text
Checking fact posts every 2 s. Press Ctrl+C to stop.
2026-10-10 19:12:56,906 INFO apps.pipeline.processor: Pipeline: post c923b87a-2fdd-4a19-b97c-808faa862766 -> labelled
Processed 1 fact post.
Stopped.
```

- The loop prints only when it checked something. `Ctrl+C` ends it cleanly with "Stopped." (your terminal may show
  `^C` in front of it); close window 4.

#### Step 10: A late answer on a post that reports sent to review

**Where:** Terminal window 2. Window 1 still runs without the kick (so the post isn't checked at once).

**What this does:** `cy` posts a `#false` fact, which is then put under review the way five counting reports would
(Part 8). Only then does the pipeline answer, with a decisive FALSE: a moderator must decide, and nothing reveals the
FALSE meanwhile (user decision 2026-10-11). For comparison, the FALSE post from step 4 is put under review the same
way: it was FALSE in public before, so it still can't be reposted.

```powershell
$r1 = Mk $cy '{"content":"The Sahara is growing every year. #false","post_type":"fact"}'
python manage.py shell -c "from apps.posts.models import Post; print(Post.objects.filter(pk='$r1').update(status='under_review', flagged_reason='reports', pre_review_status='pending'), 'post sent to review, as five reports would')" | Select-Object -Last 1    # 1
python manage.py shell -c "from apps.pipeline.processor import process_post; print(process_post('$r1'))" | Select-Object -Last 1    # 2: the pipeline answers late
python manage.py shell -c "from apps.posts.models import Post; p = Post.objects.get(pk='$r1'); print(p.status, p.flagged_reason, p.pre_review_status, p.verdict_source, p.pipeline_verdict, p.confidence_score)" | Select-Object -Last 1   # 3
Fetch "/posts/$r1/" $null @('status', 'confidence_score', 'verdict_source')   # 4: what everyone sees
Send POST "/posts/$r1/repost/" $dee                                       # 5: dee can still repost it
python manage.py shell -c "from apps.posts.models import Post; print(Post.objects.filter(pk='$t2').update(status='under_review', flagged_reason='reports', pre_review_status='verified_false'), 'FALSE post sent to review, as five reports would')" | Select-Object -Last 1    # 6
Send POST "/posts/$t2/repost/" $dee                                       # 7: a post that was FALSE in public can't be
```

**You should see:**

```text
1 post sent to review, as five reports would
True
under_review both pending None false 92.00
200  {"status":"under_review","confidence_score":null,"verdict_source":null}
201  {"reposted":true}
1 FALSE post sent to review, as five reports would
409  {"detail":"Posts labelled FALSE can't be reposted.","code":"cannot_repost_false"}
```

- 3: the post stays UNDER REVIEW and its reason becomes `both` (reports and the pipeline); the FALSE and its 92% are
  kept for the moderator, but nothing is stored as the label to restore, so dismissing the reports (Part 10) can't
  make it FALSE without a human. A late **TRUE** is kept as the label a dismissal restores (the tests cover it).
- 4 and 5: from outside, nothing shows the FALSE: no confidence, no source, and reposting works.
- 7: Part 8's rule still holds for a post whose FALSE label was public before the reports.

#### Step 11: A pipeline that fails is retried, then a moderator decides

**Where:** Terminal window 2. Window 1 still runs without the kick.

**What this does:** The stub never fails, so this step stands in a pipeline that never answers and moves the clock
forward between the tries: a failed try is retried after 2, 4, 8 and 16 minutes, and after the fifth the post goes to
review.

```powershell
$f1 = Mk $dee '{"content":"A claim nobody can check today. #true","post_type":"fact"}'
@"
from django.utils import timezone
from apps.pipeline.clients import PipelineError
from apps.pipeline.processor import process_post
from apps.posts.models import Post

class Down:  # a pipeline that never answers
    max_seconds = 0
    def check(self, request):
        raise PipelineError("timeout", "no answer in time")

when = timezone.now()
for _ in range(5):
    process_post("$f1", client=Down(), now=when)
    post = Post.objects.get(pk="$f1")
    wait = post.pipeline_next_attempt_at
    print(post.pipeline_attempts, post.status, post.flagged_reason, "next try in", wait - when if wait else None)
    when = wait or when
print(post.pipeline_result)
"@ | python manage.py shell | Where-Object { $_ -and $_ -notmatch 'imported automatically' }
Fetch "/posts/$f1/" $null @('status', 'confidence_score', 'verdict_source')
```

**You should see** (the times and the id differ):

```text
2026-10-10 19:13:02,399 WARNING apps.pipeline.processor: Pipeline: post c0cdf1cd-5c74-48c3-9184-11df1109645f, try 1 failed (timeout)
1 pending None next try in 0:02:00
2026-10-10 19:13:02,403 WARNING apps.pipeline.processor: Pipeline: post c0cdf1cd-5c74-48c3-9184-11df1109645f, try 2 failed (timeout)
2 pending None next try in 0:04:00
2026-10-10 19:13:02,407 WARNING apps.pipeline.processor: Pipeline: post c0cdf1cd-5c74-48c3-9184-11df1109645f, try 3 failed (timeout)
3 pending None next try in 0:08:00
2026-10-10 19:13:02,411 WARNING apps.pipeline.processor: Pipeline: post c0cdf1cd-5c74-48c3-9184-11df1109645f, try 4 failed (timeout)
4 pending None next try in 0:16:00
2026-10-10 19:13:02,415 ERROR apps.pipeline.processor: Pipeline: post c0cdf1cd-5c74-48c3-9184-11df1109645f given up after 5 tries (timeout)
5 under_review pipeline next try in None
{'error': 'timeout', 'detail': 'no answer in time', 'attempt': 5}
200  {"status":"under_review","confidence_score":null,"verdict_source":null}
```

- The post stays pending while it waits (2, 4, 8 and 16 minutes), then goes to UNDER REVIEW for the pipeline with
  the last error kept for the moderators. A failed try logs a warning; giving up logs an error (in production, one
  Sentry event per post).
- In real life nothing moves the clock: the next try happens at the next tick or loop after the wait.

#### Step 12: In the browser, a new fact's badge turns into its verdict by itself

**Where:** First window 1, then the browser, with `npm run dev` (window 3) running.

**What this does:** Restarts the server with your normal settings (the kick on), then posts three facts through the
composer and watches the cards change on their own, then opens each post's page.

Window 1: press `Ctrl+C`, then:

```powershell
Remove-Item Env:PIPELINE_INLINE_KICK ; python manage.py runserver   # your normal settings again; leave it running
```

Browser: log in at http://localhost:3000/login as `part9-dee-<id>@example.test` (use the `id` from step 3:
`$id` in window 2) with the password `correct-horse-battery-42`.

| Do this | Expect |
|---|---|
| On /home click **New post**, write `Paris is the capital of France. #true`, choose **Fact**, click **Post fact, will be checked** | A toast **"Posted. Checking the facts…"**. The new card is at the top with a grey dashed **CHECKING FACTS…** badge (a spinning glyph) and a grey stripe. After about **10 seconds**, without reloading, it turns into a teal **VERIFIED 95%** badge with a tick, and the stripe turns teal. |
| Post `The Great Wall of China is visible from space. #false` the same way | CHECKING FACTS…, then after about 10 s a red **FALSE 92%** badge with a crossed circle and a red stripe. |
| Post `Bats are blind. #unsure` | CHECKING FACTS…, then an amber **UNDER REVIEW** badge with an hourglass and an amber stripe. No percentage. |
| Click the text of the VERIFIED post | Its page: the VERIFIED 95% badge and, under **Verdict**, a teal box **"CHECKED AUTOMATICALLY · 95% CONFIDENCE"** with "This claim was found to be true." |
| Open the FALSE post's page | **"CHECKED AUTOMATICALLY · 92% CONFIDENCE"** and "This claim was found to be FALSE." The word "debunked" appears nowhere. |
| Open the UNDER REVIEW post's page | **"UNDER REVIEW"** and "A moderator is taking a look at this post. The label changes once they decide." No percentage. |
| Scroll down /home | The facts from steps 4 to 11 show their labels: VERIFIED, FALSE or UNDER REVIEW; "A claim nobody can check today." (step 11) is UNDER REVIEW. |

- The check itself takes a few milliseconds (window 1 logs it at once); the card changes at the page's first status
  check, 10 seconds after posting (Part 5's polling: 10 s, then 15, 22 …, while the tab is visible).
- Measured with headless Chromium: each of the three cards changed 10.4 s after posting.
- A moderator's verdict reads "Reviewed by a moderator" with no percentage (Part 10 adds the actions that make one).

#### Step 13: A phone-sized window

**Where:** Browser, logged in as `dee`.

**What this does:** Checks the badges at phone width. In Firefox or Chrome press `F12`, then the "responsive design" /
device toolbar button, and set the width to 390.

| Do this | Expect |
|---|---|
| Open /home | Each card shows the author line, then the FACT chip and the badge (VERIFIED 95%, FALSE 92%, UNDER REVIEW) on their own line, then the claim. **No sideways scrolling.** |
| Open the UNDER REVIEW post's page | The badge and the Verdict box fit the width. **No sideways scrolling.** |

- Measured with headless Chromium at 390 px: 0 px of horizontal overflow on `/home` and on a post's page.

#### Step 14: Django Admin: what the pipeline stored

**Where:** Browser, while `runserver` is running in window 1.

**What this does:** Shows a checked post in the read-only posts admin, with the fields the public never sees. The
review queue and the moderator actions are Part 10.

| URL / action | Expect |
|---|---|
| http://localhost:8000/admin/ (superuser from Part 0A; if it 404s, `ADMIN_URL_PATH` in `backend\.env` isn't `admin/`: use that path) | **Posts** is listed in the sidebar. |
| http://localhost:8000/admin/posts/post/, then click "Water boils at 100 degrees Celsius at sea level. #true" | **View post**, read-only (no **Save**): **Status** "Verified true", **Confidence score** 95.00, **Pipeline verdict** "True", **Pipeline result** `{"rule": "#true", "stub": true}`, **Pipeline attempts** 1, **Pipeline next attempt at** "-", **Pipeline checked at** the time, **Verdict source** "Pipeline". |
| Open "A claim nobody can check today. #true" (step 11) | **Status** "Under review", **Flagged reason** "Pipeline", **Pipeline attempts** 5, **Pipeline result** `{"error": "timeout", "detail": "no answer in time", "attempt": 5}`. |

- Checked with a scripted browser and a throwaway superuser, not by a person.

#### Step 15: Stop and clean up

**Where:** Every terminal window, plus the browser.

- Stop the servers: `Ctrl+C` in windows 1 and 3 (a leftover `next dev`: step 12 of Part 1). Window 1 still has
  `$env:PIPELINE_INLINE_KICK` removed since step 12; if you skipped step 12, run `Remove-Item Env:PIPELINE_INLINE_KICK`
  there before the next `runserver`.
- Delete the test accounts and their posts and reposts (all go with the accounts). In window 2, in `backend\` with the
  venv active:

  ```powershell
  python manage.py shell -c "from apps.accounts.models import User; print(User.objects.filter(email__startswith='part9-').delete())" | Select-Object -Last 1
  ```

  After one clean run of steps 3 to 11 of this guide it prints `(35, {'social.Repost': 1, 'account.EmailAddress': 4, 'posts.Post': 26, 'accounts.User': 4})`:
  how many rows went in all, and per table (26 posts: 8 by `ada` (steps 4 and 6), 9 by `bo` and 8 by `cy` (steps 7 to
  10), 1 by `dee` (step 11); 1 repost, `dee`'s in step 10). Your count differs if you did the browser steps (3 more
  posts) or made other accounts. Nothing else is touched; the pending facts that step 7 checked belong to the E2E
  tests' accounts, which stay in your local database as in earlier parts (Django Admin → Users deletes them).
- `docker compose down` (repo root) stops the containers and keeps the data; `docker compose down -v`
  wipes the whole local database, which is destructive.
- The only secret used is `INTERNAL_CRON_SECRET` in step 8, read from `backend\.env` into a variable and never
  printed; `Remove-Variable secret` forgets it. The other values in the commands are Cloudflare's public test token
  and the throwaway password of the test accounts.
