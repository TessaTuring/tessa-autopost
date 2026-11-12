# Tessa Autopost

Posts one Instagram carousel for @tessaturing every day, automatically.

## How it works

| When (Eastern) | What happens | Your part |
|---|---|---|
| ~6 PM the night before | Claude writes tomorrow's carousel, the slides are rendered, and GitHub opens an issue titled **"Post for YYYY-MM-DD"** with previews. GitHub emails you. | Nothing. Glance at it if you like. |
| 8 AM | If that issue is still open, the carousel is posted to Instagram with Instagram's AI label on, and the issue is closed with a link to the post. | Nothing. |
| To skip a day | Close that day's issue before 8 AM. | One tap. |
| Mondays | The Instagram login token is refreshed so it never expires. | Nothing. |

Content rotates through 7 pillars by weekday (email, planning, writing, life admin, learning,
everyday life, weekly reset), never repeats a recent topic, and never mentions AI on the slides.
Covers rotate through 8 Tessa photos in `assets/covers/`.

Times shift one hour later during daylight saving time (GitHub schedules run in UTC).

## Costs

- **Claude API:** a few cents per post (roughly $3 to $10 a month).
- **GitHub:** free (public repository).
- **Instagram API:** free.
- **Higgsfield:** nothing day to day. New cover photos are optional (about 2 credits each).

## One-time setup

### 1. Make @tessaturing a professional account
Instagram app: **Settings and activity → Account type and tools → Switch to professional account → Creator**.

### 2. Get an Instagram API token
1. Go to <https://developers.facebook.com/apps> and log in with Facebook.
2. **Create app** → use case **"Manage messaging & content on Instagram"** → finish creating the app.
3. In the app: **Instagram → API setup with Instagram login → Generate access tokens → Add account**, and log in as @tessaturing.
4. Copy the **access token** and the **Instagram user ID** shown next to the account.
   The app can stay in development mode; it only needs to post to your own account.

### 3. Get a Claude API key
<https://console.anthropic.com> → **Settings → Billing** (add about $5 of credit) → **API keys → Create key**. Copy it.

### 4. Put this folder on GitHub
Create a **public** repository named `tessa-autopost` and upload this folder's contents
(it must be public so Instagram can download the slide images). Nothing secret is stored in the files.

### 5. Add the secrets
Repository → **Settings → Secrets and variables → Actions → New repository secret**:

| Name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | the Claude API key from step 3 |
| `IG_USER_ID` | the Instagram user ID from step 2 |
| `IG_ACCESS_TOKEN` | the Instagram access token from step 2 |
| `GH_SECRETS_TOKEN` | *Only needed for expiring tokens that start with `IG`.* A GitHub fine-grained token for this repo with **Secrets: Read and write**, used for the Monday refresh. Skip it if your token came from Unified login (system-user tokens never expire). |

Then: **Settings → Actions → General → Workflow permissions → Read and write permissions → Save**.

### 6. Test it
1. **Actions → Draft tomorrow's post → Run workflow.** An issue with slide previews appears in a few minutes.
2. To test posting right away: **Actions → Publish today's post → Run workflow**, and enter the date of that draft.

## Everyday controls

- **Skip a day:** close that day's issue.
- **Pause everything:** Actions → each workflow → **⋯ → Disable workflow**.
- **Edit before it posts:** open `drafts/<date>/post.json` on GitHub and edit the caption.
  (Slide images are already rendered; to change slide text, close the issue to skip that day.)
- **Change the voice or rules:** edit the `SYSTEM` text and `PILLARS` in `scripts/generate.py`.
