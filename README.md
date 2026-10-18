# PublishPro-AI

PublishPro-AI is a web app that helps video creators get their content ready to publish, with the help of AI. The idea: a creator uploads a video, adds a few details, and the app suggests titles, descriptions, hashtags and thumbnails.

> **Status: early development.**
> Accounts, login, workspaces and team members work from start to finish (database, backend and screens).
> The AI and video features are **not built yet**.

For how the system is put together and *why* each choice was made, read **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

---

## What is done so far

| Area | Status | Notes |
|---|---|---|
| Sign up (create account) | Done | Backend + screen at `/register`. You are logged in right after. |
| Log in | Done | Backend gives a JWT token. Screen shows clear errors. |
| Log out | Done | Button in the top bar. |
| Stay logged in after a page refresh | Done | Token is kept for the browser tab. |
| Protected pages | Done | Logged-out users are sent to `/login`, then back to the page they wanted. |
| "Who am I" (profile) | Done | Name shown in the top bar and on the dashboard. |
| Create a workspace | Done | Button in the sidebar. You become its owner. |
| Switch between workspaces | Done | Sidebar switcher. Your choice is remembered. |
| See workspace members | Done | The **Team** tab opens the member list. |
| Add a member by email | Done | Owner only. Use **+ Add member** on the Team page, or the person-plus icon next to a workspace in the sidebar list. The person must already have an account. They join as an Editor. |
| Forgot password | Not built | The button is there but does nothing. |
| Refresh tokens / ending a session on the server | Not built | Empty placeholder in the backend. |
| Change a member's role / remove a member | Not built | No backend endpoint exists yet, so the screen has no buttons for it. |
| Upload a video, video projects | Not built | The form on **Create Post** is only a design. It does not save or send anything. |
| AI content (titles, descriptions, hashtags) | Not built | Gemini provider is an empty placeholder. |
| Thumbnails | Not built | Empty placeholder. |
| Activity log | Not built | Empty placeholder. |
| Dashboard | Basic | Shows your profile details only. |
| My Content, Brand Kit, Settings | Placeholder | Show "This page is coming soon." |
| Analytics | Hidden | The sidebar tab is removed for now. |
| Plan and credits card (sidebar) | Fake data | Example numbers, no billing yet. |
| Automated tests | Minimal | Only Spring's default "app starts" test. |

---

## Tech stack

**Backend** (`backend/`)
- Java 21 and Spring Boot 4.0.8
- Spring Web (REST API), Spring Security, Spring Data JPA (Hibernate), Bean Validation
- PostgreSQL, hosted on Supabase
- JWT tokens with the `jjwt` library, passwords hashed with BCrypt
- Maven (use the included `mvnw` wrapper)

**Frontend** (`frontend/`)
- React 19 and Vite 8
- React Router 7
- Plain CSS (one file per feature, no UI library)
- ESLint

---

## Project structure

```
PublishPro-AI/
|-- backend/                      Spring Boot REST API
|   `-- src/main/java/com/PublishPro_AI/
|       |-- auth/                 register + login, JWT creation
|       |-- user/                 user entity, profile
|       |-- workspace/            workspaces, members, role checks
|       |-- security/             JWT filter, security rules, CORS
|       |-- common/exception/     custom errors -> HTTP status codes
|       |-- video/ thumbnail/     empty placeholders (not built)
|       |-- ai/ activity/         empty placeholders (not built)
|       `-- config/               Supabase settings holder
|-- frontend/                     React app
|   `-- src/
|       |-- features/             auth, workspace, team, dashboard, content-generator
|       |-- components/           layout (sidebar, top bar) and shared pieces
|       `-- lib/                  apiClient.js (all calls to the backend)
`-- docs/ARCHITECTURE.md          how it works and why
```

---

## Run it on your computer

### What you need
- **JDK 21** (the project is built for Java 21). Make sure `JAVA_HOME` points to a real JDK 21 folder.
- **Node.js 20.19 or newer** (or 22.12+), and npm
- A **Supabase** project with a PostgreSQL database

### 1. Start the backend

Spring Boot does **not** read the `.env` file by itself. Set these as real environment variables (in your terminal, or in your IDE's run configuration).

| Variable | What it is |
|---|---|
| `SUPABASE_DB_URL` | JDBC connection string from Supabase, like `jdbc:postgresql://...` (SSL is required) |
| `SUPABASE_DB_USERNAME` | Database user |
| `SUPABASE_DB_PASSWORD` | Database password |
| `JWT_SECRET` | A random secret, **Base64 encoded, at least 32 bytes** |

Make a JWT secret in PowerShell:

```powershell
$b = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
[Convert]::ToBase64String($b)
```

Then, in the same terminal:

```powershell
$env:SUPABASE_DB_URL      = "jdbc:postgresql://..."
$env:SUPABASE_DB_USERNAME = "..."
$env:SUPABASE_DB_PASSWORD = "..."
$env:JWT_SECRET           = "<the value you generated>"

cd backend
.\mvnw spring-boot:run
```

The API runs at **http://localhost:8080**. On first start, Hibernate creates the tables for you (`users`, `workspaces`, `workspace_members`).

### 2. Start the frontend

First create the file `frontend/.env`. It is **not stored in Git**, so every new copy of the project needs it. It tells the frontend where the backend is:

```
VITE_API_BASE_URL=http://localhost:8080
```

If your backend uses another port, change this value (and restart `npm run dev` after any change to this file).

Then:

```powershell
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** (use exactly this address, because the backend only allows it).

### 3. Try it

1. Open `/register` and create an account.
2. You land on the dashboard. Your name shows in the top bar.
3. Open the workspace switcher in the sidebar and choose **+ Create workspace**.
4. Open **Team** and click **+ Add member**. Enter a second registered user's email. (You can also click the person-plus icon next to a workspace in the sidebar list.)
5. Log out and log in as that user. They will see the workspace, but only the owner sees the **+ Add member** button.

### Useful commands

```powershell
# frontend/
npm run lint        # check code style
npm run build       # production build into dist/

# backend/
.\mvnw test         # needs the database variables above, because the test starts the whole app
```

---

## API summary

All paths start with `/api`. For the rows marked "yes" in the **Token** column, send the login token in a header: `Authorization: Bearer <token>`.

| Method and path | Token | What it does |
|---|---|---|
| `POST /auth/register` | no | Create an account. Body: `name`, `email`, `password` (min 8 characters). Returns `201` with the new user. |
| `POST /auth/login` | no | Body: `email`, `password`. Returns `accessToken`, `tokenType`, `user`. |
| `GET /users/profile` | yes | The logged-in user: `id`, `name`, `email`. |
| `POST /workspaces` | yes | Create a workspace. Body: `name` (max 100 characters). |
| `GET /workspaces` | yes | The workspaces you belong to. |
| `GET /workspaces/{id}` | yes | One workspace (members only). |
| `GET /workspaces/{id}/members` | yes | List members (members only). |
| `POST /workspaces/{id}/members` | yes | Add a member by `email`. **Owner only.** Returns `201`, no body. |

Errors come back as short plain text with these status codes:

| Code | Meaning | Example message |
|---|---|---|
| 400 | The request body is invalid | `Password must contain at least 8 characters` |
| 401 | Not logged in, bad login, or expired token | `Invalid email or password` |
| 403 | Logged in but not allowed | `Only the workspace owner can perform this action` |
| 404 | Not found | `User not found` |
| 409 | Already exists | `Email is already registered` |

---

## Screens (frontend routes)

| Route | Who can open it | State |
|---|---|---|
| `/login`, `/register` | Everyone | Done |
| `/dashboard` | Logged in | Basic |
| `/team` | Logged in | Done (member list and **+ Add member**) |
| `/create` | Logged in | Design only |
| `/content`, `/brand-kit`, `/settings` | Logged in | "Coming soon" |

The `/analytics` address still exists, but its sidebar tab is hidden for now.

---

## Known issues and housekeeping

Things worth fixing soon. None of them stop the app from working.

- **Use JDK 21.** On the machine used so far, `JAVA_HOME` pointed to a folder that does not exist (`D:\Program FIles\...`), and JDK 25 crashed the JVM (`EXCEPTION_ACCESS_VIOLATION`, files named `hs_err_pid*.log`). Install JDK 21 and fix `JAVA_HOME`.
- **`JWT_EXPIRATION` is ignored.** It is listed in `.env.example`, but `application.properties` has the value fixed at 24 hours (`jwt.expiration=86400000`).
- **Some "not found" cases return 500.** `GET /workspaces/{id}` for a missing workspace, and a few other places, throw `IllegalArgumentException`, which is not handled. They should use `NotFoundException` (404).
- **The root `.gitignore` is not quite right.** It ignores `.env.example` (so the template is not shared) and has a typo `.node_modules` (so `node_modules` is not ignored).
- **Files that should not be in git.** `backend/register-payload.json`, `backend/response1.txt`, `backend/app-*.log` and `backend/app-pid.txt` are committed and contain test data and logs. `backend.zip`, `frontend.zip`, `hs_err_pid*.log` and the root `node_modules/` also should not be committed.
- **Unused packages at the repo root.** The root `package.json` lists `@supabase/*` libraries that the frontend does not use.
- **CORS only allows `http://localhost:5173`.** Add your real website address before deploying.
- **Spring prints "Using generated security password" at start-up.** It is not used for login. It appears because `CustomUserDetailsService` is still an empty placeholder.

## What comes next

Likely next steps, roughly in order:

1. Video projects: save a project (title, description, file) inside a workspace.
2. AI: connect Gemini through the `AIProvider` placeholder to suggest titles, descriptions and hashtags.
3. Thumbnails and the activity log.
4. Member management: change role and remove member (backend first, then screen).
5. Forgot password and refresh tokens.
6. Database migrations (Flyway) instead of `ddl-auto=update`, more tests, and deployment settings.
