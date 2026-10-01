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

## Part 0B: Frontend foundation & design system

Everything here runs in `frontend\`. No backend, Docker container or secret is needed: these pages
make no API calls. (Next loads your `frontend\.env.local` by itself; you never open or print it.)

### 1. Terminal: install and check the tools

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero\frontend
node -v                               # v24.x.x (the project pins Node 24)
npm install                           # "up to date, audited 449 packages" and "found 0 vulnerabilities"
```

- npm also prints `npm warn allow-scripts ... unrs-resolver`. It is harmless.
- On a fresh clone the first install can stop with `ERR_SSL_CIPHER_OPERATION_FAILED` on this
  network. Run `npm cache verify`, then `npm install` again. Don't turn TLS checks off.

### 2. Terminal: automated checks

Same folder. Nothing else needs to be running.

```powershell
npm run lint                          # only the npm header, no findings
npm run lint:tokens                   # lint:tokens OK (no default palette, raw hex, stray radius, shadow or type size)
npm run typecheck                     # only the npm header, no type errors
npm run format:check                  # All matched files use Prettier code style!
npm test                              # Test Files  32 passed (32) / Tests  251 passed (251)
```

### 3. Terminal: try to break the design-token guard

`lint:tokens` rejects anything outside the Stitch design system. Add a file that breaks two rules:

```powershell
Set-Content src\tmp-token-check.tsx 'export const x = "bg-blue-500 rounded-md";'
npm run lint:tokens
Remove-Item src\tmp-token-check.tsx
npm run lint:tokens
```

- First run exits with code 1 and prints
  `src/tmp-token-check.tsx:1  Tailwind default palette colour: bg-blue-500`,
  `src/tmp-token-check.tsx:1  radius other than rounded-lg / rounded-full: rounded-md` and
  `lint:tokens found 2 problem(s).`
- Second run (file removed) is back to `lint:tokens OK ...`. Nothing is left behind.

### 4. Terminal: start the dev server

```powershell
npm run dev                           # leave this window running
```

- Prints `▲ Next.js 16.3.8 (Turbopack)`, `- Local:         http://localhost:3000`,
  `- Environments: .env.local` and `✓ Ready in` a few hundred milliseconds.
- It must not create `frontend\AGENTS.md` or `frontend\CLAUDE.md` (see step 8).

### 5. Browser: while `npm run dev` is running

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
`design\stitch\stitch_website_sitemap_grid_builder\b1_home_feed\code.html` next to the gallery.
Stitch also shows an affiliation line, an evidence drawer and an action bar (later parts) and
strikes FALSE claims through (deliberately not copied).

### 6. Browser: the two modals

Still on `/dev/ui`, scroll to "Stitch b2 and d1: modals".

| Do this | Expect |
|---|---|
| Click **Open the composer (b2)** | A 620 px dialog, centred, over a dimmed and slightly blurred page. Header "New post". The cursor is already in the large serif text box, with `0 / 500 characters` under it. Fact is selected, the violet Emergency toggle is on with a violet "Misuse has consequences." callout, and there is a Source field. Footer: "7 of 10 fact posts left today", Cancel, **Post fact, will be checked**. |
| Type `Solar capacity grew 30% last year.` | The counter reads `34 / 500 characters` |
| Click **Opinion** | The button becomes **Post opinion** and the Emergency toggle and Source field disappear |
| Press Tab over and over | Focus cycles through the dialog's own controls and never reaches the page behind it. After the last button it leaves the page for the browser's own controls, then comes back to Close. |
| Press Esc | The dialog closes and focus is back on **Open the composer (b2)** |
| Click **Open the report modal (d1)** | Header "Report this post" with a small "REPORT" line above it, a quoted claim with a dark left edge, five radio cards (the first selected, blue border), a blue "What happens next" note, and a white footer with Cancel and **Submit report**. Focus starts on the × button. |
| Press Esc | The dialog closes and focus returns to **Open the report modal (d1)** |

### 7. Terminal: the production build hides the gallery

Stop the dev server first (`Ctrl+C` in its window), then in `frontend\`:

```powershell
npm run build
npm start                             # leave this window running
```

- Build: `✓ Compiled successfully in` a few seconds, `Generating static pages ... (4/4)`, and a
  route list with `/`, `/_not-found` and `/dev/ui`, all marked `○ (Static)`. The route is listed
  but answers 404 at runtime, as the next commands show.
- Start: `▲ Next.js 16.3.8`, `- Local:         http://localhost:3000`, `✓ Ready in` about 100 ms.

In a second window:

```powershell
curl.exe -s -o NUL -w "/        %{http_code}`n" http://localhost:3000/
curl.exe -s -o NUL -w "/dev/ui  %{http_code}`n" http://localhost:3000/dev/ui
```

- Expect `/        200` and `/dev/ui  404`.
- Browser: http://localhost:3000/dev/ui shows "This page could not be found", while
  http://localhost:3000/ still shows "Frontend foundation".

### 8. Terminal: repository checks

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero
git check-ignore frontend\.env.example             # prints nothing: the example env file is tracked
Test-Path frontend\AGENTS.md, frontend\CLAUDE.md   # False, then False
```

### 9. Stop and clean up

- Stop the server: `Ctrl+C` in its window.
- Nothing else is running for this part: no containers, no backend.
- Optional: `Remove-Item -Recurse -Force frontend\.next` deletes the build output. It is recreated
  by the next `npm run dev` or `npm run build`.

---

## Part 0D: Brand assets & Logo component

Everything here runs in `frontend\` unless a step says otherwise. No backend, Docker container or
secret is needed. (Next loads your `frontend\.env.local` by itself; you never open or print it.)
The master logo is `design\logo.svg`. It is read-only: nothing below changes it.

### 1. Terminal: the tools

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero\frontend
npm install                           # "up to date, audited 449 packages" and "found 0 vulnerabilities"
npm ls sharp --depth=0                # `-- sharp@0.35.5
```

- npm also prints `npm warn allow-scripts ... unrs-resolver`. It is harmless.
- `sharp` is the image library that draws the PNGs. Only the brand script uses it.

### 2. Terminal: build every logo asset

```powershell
npm run brand:build
```

- Prints `brand:build read design\logo.svg and wrote 16 files:` and a list: `logo.svg`, `mark.svg`,
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

### 3. Terminal: nothing under `design\` changes, and a second run changes nothing

```powershell
$paths = @('public\brand\*', 'src\app\favicon.ico', 'src\app\icon.svg', 'src\app\apple-icon.png', 'src\app\opengraph-image.png', 'src\app\twitter-image.png', 'src\lib\brand-assets.json', '..\design\logo.svg', '..\backend\apps\core\static\core\brand\logo-admin.png')
$h1 = Get-FileHash $paths | Select-Object Path, Hash
$h1.Count                             # 15
npm run brand:build | Out-Null
$h2 = Get-FileHash $paths | Select-Object Path, Hash
@(Compare-Object $h1 $h2 -Property Path, Hash).Count    # 0
cd ..
git status --short design             # prints nothing
cd frontend
```

- `15` files hashed, and `0` differences: building again gives the same bytes, including
  `design\logo.svg`.
- `git status --short design` prints nothing: the master was only read.

### 4. Terminal: the build refuses an unsafe logo

The script takes `--master <file>` so you can try another SVG. Each bad file below is a copy of the
real logo with one thing added, kept in your temp folder.

```powershell
$bad = Join-Path $env:TEMP "rz-bad-logo.svg"
(Get-Content ..\design\logo.svg -Raw) -replace '<defs>', '<script>alert(1)</script><text>x</text><defs>' | Set-Content $bad
npm run brand:build -- --master $bad
$LASTEXITCODE
```

- Prints `brand:build failed: rz-bad-logo.svg failed the safety check, so nothing was built:` with
  `- <script> element (line 3)` and `- <text> element (line 3)`. `$LASTEXITCODE` is `1`.

```powershell
(Get-Content ..\design\logo.svg -Raw) -replace '<defs>', '<use href="https://evil.example/x.svg#a"/><defs>' | Set-Content $bad
npm run brand:build -- --master $bad
```

- Fails with `- external href="https://evil.example/x.svg#a" on <use> (line 3)`.

```powershell
(Get-Content ..\design\logo.svg -Raw) -replace 'viewBox="0 0 1000 1000"', '' | Set-Content $bad
npm run brand:build -- --master $bad
Remove-Item $bad
```

- Fails with `- the <svg> root has no viewBox`.
- In all three, no asset is written and `design\logo.svg` is untouched. Running plain
  `npm run brand:build` again afterwards still works.

### 5. Terminal: automated checks

Same folder. Nothing else needs to be running.

```powershell
npm run lint                          # only the npm header, no findings
npm run lint:tokens                   # lint:tokens OK (no default palette, raw hex, stray radius, shadow or type size)
npm run typecheck                     # only the npm header, no type errors
npm run format:check                  # All matched files use Prettier code style!
npm test                              # Test Files  40 passed (40) / Tests  329 passed (329)
```

- The new tests are the SVG safety check, the ICO writer, the contrast table (compared with
  `docs\ARCHITECTURE.md`), the PNG sizes, a full build into a scratch folder, `Logo`, `manifest.ts` and
  the brand guard.

### 6. Terminal: try to break the brand guard

Only `Logo.tsx`, `brand-assets.json` and `manifest.ts` may know where the logo files are, and nobody
may re-create the old text wordmark. Add two files that break the rules:

```powershell
Set-Content src\tmp-wordmark.tsx 'export const X = () => <span className="font-headline-sm">Rumor Zero</span>;'
Set-Content src\tmp-logo-ref.ts 'export const src = "/brand/logo.svg";'
npx vitest run src/lib/brand-guard.test.ts
Remove-Item src\tmp-wordmark.tsx, src\tmp-logo-ref.ts
npx vitest run src/lib/brand-guard.test.ts
```

- First run: `Tests  3 failed | 3 passed (6)`. The failures name `tmp-logo-ref.ts` (twice: it refers to
  `/brand/` and names a logo image) and `tmp-wordmark.tsx` (it re-creates the text wordmark).
- Second run (files removed): `Tests  6 passed (6)`. Nothing is left behind.

### 7. Terminal: the production build carries the icon tags

```powershell
npm run build
$html = Get-Content .next\server\app\index.html -Raw
[regex]::Matches($html, '<link rel="(?:icon|apple-touch-icon|manifest)"[^>]*>') | ForEach-Object { $_.Value }
[regex]::Matches($html, '<meta (?:property|name)="(?:og:image|twitter:image|twitter:card|og:site_name)"[^>]*>') | ForEach-Object { $_.Value }
```

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

### 8. Terminal: start the dev server and fetch every asset

```powershell
npm run dev                           # leave this window running
```

Second window:

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero\frontend
foreach ($u in '/favicon.ico','/icon.svg','/apple-icon.png','/manifest.webmanifest','/opengraph-image.png','/twitter-image.png','/brand/logo.svg','/brand/mark.svg','/brand/icon-192.png','/brand/icon-512.png','/brand/icon-maskable-512.png','/brand/email-logo.png','/brand/google-oauth-logo.png') {
  curl.exe -s -o NUL -w "$u  %{http_code}  %{content_type}`n" "http://localhost:3000$u"
}
curl.exe -s http://localhost:3000/manifest.webmanifest
curl.exe -s -o NUL -w "/brand/nope.png  %{http_code}`n" http://localhost:3000/brand/nope.png
```

- All 13 lines say `200`. Content types: `image/x-icon` for the .ico, `image/svg+xml` for the three SVGs,
  `application/manifest+json` for the manifest, and `image/png` for the rest.
- The manifest is one line of JSON: name and short name `Rumor Zero`, `"start_url":"/"`,
  `"display":"standalone"`, `theme_color` and `background_color` both `#283044`, and three icons:
  `192x192` (`any`), `512x512` (`any`) and `512x512` (`maskable`).
- The last line says `404`: only generated files exist.

### 9. Browser: while `npm run dev` is running

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

### 10. Terminal: exact sizes of the generated files

Stop the dev server first (`Ctrl+C`), or use a new window. In `frontend\`:

```powershell
Add-Type -AssemblyName System.Drawing
$pngs = 'src\app\apple-icon.png','public\brand\icon-192.png','public\brand\icon-512.png','public\brand\icon-maskable-512.png','src\app\opengraph-image.png','src\app\twitter-image.png','public\brand\google-oauth-logo.png','public\brand\email-logo.png','..\backend\apps\core\static\core\brand\logo-admin.png'
foreach ($p in $pngs) { $img = [System.Drawing.Image]::FromFile((Resolve-Path $p)); "{0,-62} {1} x {2}  {3} bytes" -f $p, $img.Width, $img.Height, (Get-Item $p).Length; $img.Dispose() }
$b = [System.IO.File]::ReadAllBytes((Resolve-Path src\app\favicon.ico))
"ico: images=$([BitConverter]::ToUInt16($b,4)); sizes=" + (($b[6], $b[22], $b[38]) -join ',')
```

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

### 11. Terminal: repository checks

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero
git check-ignore frontend\src\app\favicon.ico frontend\public\brand\logo.svg backend\apps\core\static\core\brand\logo-admin.png   # prints nothing: none of them is ignored
git check-attr binary -- frontend/src/app/favicon.ico frontend/src/app/apple-icon.png     # both: binary: set
git status --short design             # prints nothing: design\ is untouched
Test-Path frontend\AGENTS.md, frontend\CLAUDE.md   # False, then False
```

### 12. Stop and clean up

- Stop the server: `Ctrl+C` in its window.
- Nothing else is running for this part: no containers, no backend.
- The generated files are meant to be committed; do not delete them. To change the logo later:
  replace `design\logo.svg` yourself, check that `markSelector` in
  `frontend\scripts\brand\brand.config.json` still picks the "0" (the build fails if it does not
  match exactly one shape), run `npm run brand:build`, and compare the contrast table with
  `docs\ARCHITECTURE.md` section 14.

---

## Part 0C: App shell, API relay, API client, CI

Needs Part 0A's containers and virtualenv, and your own `backend\.env` and `frontend\.env.local`.
The relay reads `BACKEND_ORIGIN` and `PROXY_SHARED_SECRET` from `frontend\.env.local`. The secret
must be the same as the one in `backend\.env` (ENV_GUIDE §1.2). Nobody can log in yet (Part 1), so
the app pages show the logged-out shell; `/dev/shell` shows the logged-in one with a sample user.

### 1. Terminal: install the new tools

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero\frontend
npm install                       # up to date, audited 735 packages ... found 0 vulnerabilities
npx playwright install chromium   # first time: downloads Chromium for the E2E test; later: prints nothing
npx wrangler --version            # 4.145.0
npx playwright --version          # Version 1.63.0
```

- `npm install` also prints an `allow-scripts` warning: it did not run the install scripts of
  `workerd`, `esbuild` and `unrs-resolver`. That is expected. Their programs come from separate
  platform packages and work without those scripts.
- Don't run `npm run preview`, `deploy` or `upload` on Windows. They are for Linux (CI and
  Cloudflare), and they would copy your real `.env.local` into the Worker bundle.

### 2. Terminal: automated checks

```powershell
npm run lint             # no output after the command line
npm run lint:tokens      # lint:tokens OK (no default palette, raw hex, stray radius, shadow or type size)
npm run typecheck        # no output after the command line
npm run format:check     # All matched files use Prettier code style!
npm test                 # Test Files  51 passed (51) / Tests  412 passed (412)
npm run build
```

The build ends with a route list. These lines matter:

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

### 3. Terminal: start Django and the frontend

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

- The extra seconds start `workerd`, Cloudflare's local runtime, for the OpenNext dev setup. If
  Windows Firewall asks about it, local access is all it needs.

### 4. Terminal (third window): the relay

```powershell
curl.exe -i http://localhost:3000/api/health/
curl.exe -s -i http://localhost:3000/api/health | Select-String '^HTTP|^location'
curl.exe -s -o NUL -w "%{http_code}`n" "http://localhost:3000/api/a%2Fb/"
curl.exe -s -o NUL -w "%{http_code}`n" http://localhost:3000/api/nope/
curl.exe -s -o NUL -w "%{http_code} %{redirect_url}`n" http://localhost:3000/home/
```

- First: `HTTP/1.1 200 OK` and the body `{"status":"ok"}`. That is Django's answer, fetched through
  the relay on port 3000, with no redirect.
- Second: `HTTP/1.1 301 Moved Permanently` and `location: /api/health/`. That is Django adding the
  missing slash; the relay keeps the target relative, so it stays on port 3000.
- Third: `400` (an encoded `/` is refused). Fourth: `404` (Django has no such path).
- Fifth: `308 http://localhost:3000/home`. Page URLs drop a trailing slash; API URLs keep it.

Now stop Django (`Ctrl+C` in window 1) and ask again:

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

### 5. Terminal: what the backend receives (stand-in backend)

Django removes the `X-RZ-*` headers before any code can see them, so this check uses a small
stand-in backend. It reports what arrived as true/false and names only. It uses the made-up value
`echo-check-secret`, never your real secret.

First stop `npm run dev` (`Ctrl+C` in window 2): Next runs only one dev server per folder. Then
stop `runserver` in window 1 too; it isn't needed here.

Window 1, the stand-in backend:

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

Window 2, a dev server pointed at it. The `$env:` values last only for this window;
`.env.local` is not changed:

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero\frontend
$env:BACKEND_ORIGIN = "http://127.0.0.1:8765"; $env:PROXY_SHARED_SECRET = "echo-check-secret"
npx next dev -p 3100
```

Window 3:

```powershell
curl.exe -s -H "X-RZ-Proxy-Secret: spoofed" -H "X-RZ-Client-IP: 6.6.6.6" -H "X-Forwarded-Host: evil.example" http://localhost:3100/api/echo/
curl.exe -s -H "Content-Type: text/plain" --data "hello relay" http://localhost:3100/api/echo/
curl.exe -s -i http://localhost:3100/api/cookies/ | Select-String '^set-cookie'
curl.exe -s -i http://localhost:3100/api/etag/ | Select-String '^HTTP|^etag|^cache-control'
curl.exe -s -i -H 'If-None-Match: \"v1\"' http://localhost:3100/api/etag/ | Select-String '^HTTP|^etag|^cache-control'
```

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

Stop both servers (`Ctrl+C` in windows 1 and 2), then close window 2 so its `$env:` values are
gone. Delete the script: `Remove-Item $env:TEMP\rz-echo.cjs`.

### 6. Browser: the layouts

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

### 7. Terminal: the E2E smoke test

Needs the containers from step 3. Django and the dev server may be running or not: Playwright
starts what is missing and reuses what is already running. A reused dev server keeps its own
`BACKEND_ORIGIN`.

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero\frontend
npm run test:e2e
```

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

### 8. Terminal: the same test the way CI runs it

CI tests the production build and starts its own servers. First stop `npm run dev` and `runserver`
(`Ctrl+C`); in this mode Playwright won't reuse them.

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero\frontend
npm run build
$env:CI = "1"
npm run test:e2e         # 8 passed, this time against `next start`
Remove-Item Env:CI
```

### 9. Terminal: the backend is unchanged and still passes

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero\backend
.\.venv\Scripts\Activate.ps1
python -m pytest                                    # 200 passed
ruff check . ; ruff format --check .                # All checks passed! / 43 files already formatted
python manage.py makemigrations --check --dry-run   # No changes detected
```

### 10. Terminal: repository checks

```powershell
cd C:\Users\Nafis\Downloads\Rumor-Zero
git status --short design                          # prints nothing: design\ is untouched
Test-Path frontend\AGENTS.md, frontend\CLAUDE.md   # False, then False
git check-ignore frontend/playwright-report frontend/test-results   # prints both: test reports are never committed
git check-ignore .github/workflows/ci.yml frontend/wrangler.jsonc frontend/playwright.config.ts   # prints nothing: all three are committed
```

### 11. Browser: CI on GitHub (after you push)

This is the one check the agent could not run, because only you push.

| URL | Expect |
|---|---|
| Your repository's **Actions** tab on github.com | A "CI" run for your push with three green jobs: "Backend (ruff, migrations, pytest)", "Frontend (lint, types, tests, OpenNext build)" and "E2E (Playwright, Chromium)" |

- The frontend job's last step, "OpenNext build", proves the Cloudflare build works on Linux.
- If the E2E job fails, its run page has a "playwright-report" artifact (kept 7 days) that shows
  why.
- Seen on 2026-10-01: the first run failed at "OpenNext build" (`Cannot find package 'esbuild'`).
  The run on `60cfffc` ("Fix: add missing esbuild dependency") had all three jobs green.
- Optional, only if you install the GitHub CLI (`gh`, not installed on this machine yet):
  `gh run list --workflow ci.yml --limit 1` shows `completed` and `success`.

### 12. Stop and clean up

- Stop the servers: `Ctrl+C` in each window.
- If `npm run dev` later says "Another next dev server is already running" with a PID, the old
  server is still alive. End it with `taskkill /PID <that PID> /T /F`.
- Stop the containers and keep the data: `docker compose down` (repo root).
- `frontend\playwright-report` and `frontend\test-results` are git-ignored; delete them whenever
  you like.

---

<!-- Add the next part below in the same shape: "## Part <ID>: <title>", then numbered steps,
     each saying Terminal or Browser, each with the exact command and the expected result. -->
