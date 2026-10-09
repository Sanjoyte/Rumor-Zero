# Test commands by part

Hands-on commands for trying each finished part yourself, in build order (Parts 0A, 0B, 0D, 0C, 1, 2, 3, 4, 5).
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
