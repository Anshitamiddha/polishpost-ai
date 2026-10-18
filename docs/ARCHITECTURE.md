# PublishPro-AI: System Architecture

This document explains how PublishPro-AI is built, how the parts talk to each other, and **why** we made each major choice. It is written in simple English. Technical words are explained in [section 2](#2-tech-terms-in-simple-words).

It describes the code as it is today. Parts that are only planned are clearly marked **(planned)**.

**Contents**

1. [The big picture](#1-the-big-picture)
2. [Tech terms in simple words](#2-tech-terms-in-simple-words)
3. [Backend](#3-backend)
4. [Security: login, tokens and permissions](#4-security-login-tokens-and-permissions)
5. [Database](#5-database)
6. [Frontend](#6-frontend)
7. [Main flows, step by step](#7-main-flows-step-by-step)
8. [Decisions and why we made them](#8-decisions-and-why-we-made-them)
9. [Limits today and what to improve](#9-limits-today-and-what-to-improve)

---

## 1. The big picture

PublishPro-AI has three parts:

```
+-------------------+     JSON over HTTP      +---------------------------+     SQL over SSL     +-------------------+
|  Browser          |  ------------------->   |  Backend (REST API)       |  ----------------->  |  Database         |
|  React app        |                         |  Spring Boot, port 8080   |                      |  PostgreSQL       |
|  (port 5173 in    |  <-------------------   |  Java 21                  |  <-----------------  |  hosted on        |
|   development)    |     JSON or text        |  Keeps no login session   |                      |  Supabase         |
+-------------------+                         +---------------------------+                      +-------------------+
```

- The **frontend** is what the user sees. It runs in the browser. It never talks to the database. It only calls the backend.
- The **backend** holds all the rules: who can log in, who can see which workspace, who can add members. It is the only part that talks to the database.
- The **database** stores users, workspaces and memberships.

The frontend and backend are **two separate programs**. They are in one Git repository (`backend/` and `frontend/`) to keep things simple, but they can be started, built and deployed on their own.

### What exists today

| Part | Built | Not built yet |
|---|---|---|
| Accounts | Register, login, profile | Forgot password, refresh tokens |
| Workspaces | Create, list, switch, view | Rename, delete |
| Members | List, add by email (owner only) | Change role, remove |
| Video, AI, thumbnails, activity | Empty placeholder classes only | Everything |

---

## 2. Tech terms in simple words

| Term | What it means here |
|---|---|
| **REST API** | The backend offers web addresses (like `POST /api/auth/login`). The frontend calls them and gets data back. |
| **JSON** | A text format for data, like `{"email": "a@b.com"}`. Frontend and backend use it to talk. |
| **Spring Boot** | A Java framework. It gives us a web server, security, and database tools ready to use. |
| **Spring Security** | The part of Spring that decides which requests are allowed. |
| **JPA / Hibernate** | A tool that turns Java objects (like `User`) into database rows, and back. We write Java, not SQL. |
| **Entity** | A Java class that matches a database table (for example `User` is the `users` table). |
| **Repository** | A Java interface used to read and save entities (for example `findByEmail`). |
| **DTO** (Data Transfer Object) | A small class that describes what goes **in** or **out** of the API. It is not the database entity, so we never leak things like password hashes. |
| **Controller** | The Java class that receives an HTTP request and returns a response. |
| **Service** | The Java class that holds the business rules ("only an owner can add members"). |
| **Bean Validation** | Rules written as labels on fields, such as `@NotBlank` and `@Size(min = 8)`. Spring checks them for us. |
| **PostgreSQL** | The database. |
| **Supabase** | A company that hosts PostgreSQL for us, so we do not install a database ourselves. |
| **JDBC** | The Java way to connect to a database. |
| **JWT** (JSON Web Token) | A signed text "ticket" the server gives you after login. You show it with each request to prove who you are. Nobody can change it without the secret key, or the signature will not match. |
| **Bearer token** | Sending the JWT in the header `Authorization: Bearer <token>`. |
| **BCrypt** | A way to store passwords as "hashes". A hash cannot be turned back into the password. BCrypt is slow on purpose, so guessing is hard. |
| **Stateless** | The server remembers nothing between requests. Each request carries its own proof (the token). |
| **Authentication** | Proving **who you are** (login). |
| **Authorization** | Deciding **what you may do** (for example, only owners add members). |
| **CORS** | A browser safety rule. A website may only call another address if that address says "yes". Our backend says yes only to the frontend address. |
| **CSRF** | An attack where another site tricks your browser into sending cookies. It matters for cookie logins. We use a header token, not cookies, so we turn this protection off. |
| **Filter** | Code that runs on every request **before** the controller. Our JWT filter lives here. |
| **Transaction** (`@Transactional`) | A group of database changes that all succeed or all fail together. |
| **React** | A JavaScript library for building screens from small pieces called components. |
| **Vite** | The tool that runs the React app while we develop and builds it for release. |
| **React Router** | Handles the pages (`/login`, `/team`) inside the React app. |
| **Context** | React's way to share data (like "who is logged in") with many components without passing it down by hand. |
| **Hook** | A React function that starts with `use` (like `useAuth`) and lets a component read shared data. |
| **SPA** (single-page app) | One web page that changes what it shows without reloading. |
| **sessionStorage / localStorage** | Small storage inside the browser. `sessionStorage` is cleared when the tab closes. `localStorage` stays. |
| **XSS** | An attack where someone gets their script to run on our page. Such a script could read storage, so we never show untrusted HTML. |
| **Environment variable** | A setting given to the program from outside (like a password), so it is not written in the code. |

---

## 3. Backend

### 3.1 Technology

Java 21, Spring Boot 4.0.8, Spring Web, Spring Security, Spring Data JPA (Hibernate), Bean Validation, the PostgreSQL driver, and `jjwt` 0.12.6 for tokens. Built with Maven.

### 3.2 Code is grouped by feature

```
com.PublishPro_AI
|-- auth/          controller, dto, service, token (JwtService)
|-- user/          controller, dto, entity, repository, service
|-- workspace/     controller, dto, entity, repository, service, authorization
|-- security/      JwtAuthenticationFilter, SecurityConfig, error handlers
|-- common/        exception (custom errors + GlobalExceptionHandler), response
|-- config/        SupabaseProperties
|-- video/ thumbnail/ ai/ activity/     placeholders (planned)
```

### 3.3 Four layers inside each feature

```
HTTP request
    |
    v
Controller   -> reads the request, calls a service, returns the response. No business rules.
    |
    v
Service      -> business rules and permission checks. Starts transactions.
    |
    v
Repository   -> reads and saves entities (Spring Data JPA writes the SQL).
    |
    v
Database
```

Data going in and out uses **DTOs** (`LoginRequest`, `WorkspaceResponse`, and so on). Entities stay inside the backend.

### 3.4 What happens to every request

```
Request
  -> CORS check               (is this browser address allowed?)
  -> JwtAuthenticationFilter  (is there a valid token? who is it?)
  -> Security rules           (/api/auth/** and /error are open, everything else needs a login)
  -> Controller -> Service -> Repository
  -> Response
```

If anything fails, it ends in one of two places:
- **`GlobalExceptionHandler`** turns our custom errors into HTTP codes (see below).
- **`CustomAuthenticationEntryPoint`** answers **401** when someone reaches a protected address without a valid login.

### 3.5 Errors

Each custom error maps to one status code. The body is a short plain-text message.

| Java exception | HTTP code | Used for |
|---|---|---|
| `MethodArgumentNotValidException` | 400 | A field breaks a validation rule. The first rule message is returned. |
| `UnauthorizedException` | 401 | Wrong email or password |
| (entry point) | 401 | No token, bad token or expired token |
| `ForbiddenException` | 403 | Logged in but not allowed |
| `NotFoundException` | 404 | Something does not exist |
| `ConflictException` | 409 | Already exists (email taken, already a member) |

### 3.6 Settings (`application.properties`)

- Database login and `JWT_SECRET` come from **environment variables**, never from the code.
- `jwt.expiration` is fixed at `86400000` ms (24 hours).
- `spring.jpa.hibernate.ddl-auto=update`: Hibernate creates and updates tables automatically.
- `spring.jpa.show-sql=true`: SQL is printed in the log (useful while developing).
- The server uses Spring's default port, **8080**.

---

## 4. Security: login, tokens and permissions

### 4.1 Passwords

When someone registers, the password is hashed with **BCrypt** and only the hash is saved (`users.password_hash`). The real password is never stored. On login, the backend checks the typed password against the hash.

### 4.2 Login and the JWT

1. The user sends email and password to `POST /api/auth/login`.
2. The backend finds the user by email, checks the account is `enabled`, and checks the password.
3. If all is fine, it creates a **JWT**:
   - **subject** = the user's id
   - **issued at** and **expires at** (24 hours later)
   - **signed** with `JWT_SECRET` (the secret is Base64, and its size picks the algorithm; a 32-byte secret gives HS256)
4. The backend returns `{ accessToken, tokenType: "Bearer", user }`.

### 4.3 Checking the token on later requests

For every request, `JwtAuthenticationFilter`:

1. Reads `Authorization: Bearer <token>`. If missing, it lets the request continue **without** a login (protected addresses will then answer 401).
2. Checks the signature and expiry.
3. Reads the user id from the token and **loads the user from the database**. It only accepts the request if the user still exists and is enabled.
4. Tells Spring Security "this request belongs to this user".

Step 3 means a deleted or disabled user stops working right away, even if their token has not expired.

### 4.4 Permissions (authorization) inside workspaces

Every workspace member has a **role**:

| Role | Can do |
|---|---|
| `OWNER` | See the workspace and its members, **add members** |
| `EDITOR` | See the workspace and its members |

All permission rules live in one class, `WorkspaceAuthorizationService`:

- `requireMember(workspaceId, userId)` -> 403 "User is not a member of this workspace" if not a member.
- `requireOwner(workspaceId, userId)` -> first `requireMember`, then 403 "Only the workspace owner can perform this action" if the role is not `OWNER`.

The **service layer** calls these before doing any work. The frontend also hides the "Add a member" box from non-owners, but that is only for convenience. **The backend is what really protects the data.**

### 4.5 Other security choices

- **Stateless sessions.** The server creates no login session.
- **CSRF protection is off**, because we do not use cookies for login.
- **CORS** allows only `http://localhost:5173` for now.
- **Same message for every login failure.** Unknown email, disabled account and wrong password all say "Invalid email or password", so nobody can find out which emails are registered.
- **401 versus 403.** 401 means "log in again". 403 means "you are logged in but not allowed". We keep them different so the frontend can react correctly.

---

## 5. Database

PostgreSQL on Supabase. Hibernate creates the tables from the entity classes.

```
users                          workspaces                       workspace_members
-----                          ----------                       -----------------
id (PK)                        id (PK)                          id (PK)
name                           name (max 100)                   workspace_id (FK -> workspaces)
email (unique)                 owner_id (FK -> users)           user_id      (FK -> users)
password_hash                  created_at                       role  (OWNER | EDITOR)
enabled                        updated_at                       joined_at
created_at                                                      unique (workspace_id, user_id)
updated_at
```

How they connect:

```
users 1 ----< workspaces            (a user can own many workspaces)
users 1 ----< workspace_members >---- 1 workspaces
                                    (a user can join many workspaces; a workspace has many members)
```

Notes:
- The table is called **`users`**, not `user`, because `user` is a reserved word in PostgreSQL.
- When a workspace is created, the creator is also saved as a member with role `OWNER`, in the **same transaction**. Either both rows are saved or neither is.
- The `unique (workspace_id, user_id)` rule means a person cannot be a member of the same workspace twice, even if two requests arrive at once.
- Indexes exist on the owner and on both sides of the membership table, because these are the columns we search by.

---

## 6. Frontend

### 6.1 Technology

React 19, Vite 8, React Router 7, and plain CSS (one CSS file per feature). No state library and no UI kit.

### 6.2 Folder layout

```
frontend/src/
|-- main.jsx            starts the app: BrowserRouter -> AuthProvider -> App
|-- App.jsx             the list of routes
|-- lib/
|   |-- apiClient.js    the ONE place that calls the backend
|   `-- getInitials.js  "Ada Lovelace" -> "AL"
|-- features/
|   |-- auth/           Login, Register, AuthLayout, AuthProvider, authApi, authStorage, useAuth
|   |-- workspace/      WorkspaceProvider, workspaceApi, useWorkspace,
|   |                   Modal, CreateWorkspaceModal, AddMemberModal
|   |-- team/           TeamPage (member list + add member)
|   |-- dashboard/      DashboardPage
|   `-- content-generator/   design-only screen
`-- components/
    |-- layout/         AppLayout, Sidebar, Topbar
    `-- common/         ProtectedRoute, PlaceholderPage
```

Each **feature folder** holds its own screens, API calls and styles, so related code stays together.

### 6.3 Pages and who can open them

```
Routes
|-- /login        public
|-- /register     public
`-- (ProtectedRoute: must be logged in)
    `-- (AppLayout: sidebar + top bar + WorkspaceProvider)
        |-- /               -> redirects to /dashboard
        |-- /dashboard
        |-- /team           member list + "+ Add member" button
        |-- /create         design only
        `-- /content /brand-kit /settings   "coming soon"
```

The `/analytics` route still exists in `App.jsx`, but its sidebar tab is hidden for now.

### 6.4 Two shared pieces of data (React Context)

**Auth** (`AuthProvider`, read with `useAuth()`)

| Value | Meaning |
|---|---|
| `status` | `loading` (checking a saved token), `authenticated`, `anonymous`, or `error` (backend down) |
| `user` | `{ id, name, email }` from `GET /api/users/profile` |
| `login(email, password)` | Calls login, saves the token, loads the profile |
| `logout()` | Clears the token and the user |

**Workspaces** (`WorkspaceProvider`, read with `useWorkspace()`)

| Value | Meaning |
|---|---|
| `workspaces`, `status`, `error` | The list from `GET /api/workspaces` and its loading state |
| `selectedWorkspace` | The one the user is working in |
| `selectWorkspace(id)`, `createWorkspace(name)` | Change or add a workspace |
| `openCreateWorkspace()` | Opens the "Create workspace" dialog from anywhere |
| `openAddMember(workspace)` | Opens the "Add member" dialog for that exact workspace (it does not have to be the selected one) |
| `membersVersion` | A counter that goes up each time a member is added, so a visible members list knows to load again |

### 6.5 How the frontend calls the backend

All calls go through `lib/apiClient.js`. It:

- adds the base address (`VITE_API_BASE_URL`),
- adds `Authorization: Bearer <token>` when asked,
- reads the answer, which can be JSON **or** plain text,
- turns failures into an `ApiError` with a message the screen can show (it only trusts the server's wording for client errors below 500, so a crash page or stack trace is never shown to users),
- on a **401** from a logged-in call, tells `AuthProvider` to log the user out.

The feature files (`authApi.js`, `workspaceApi.js`) are thin wrappers that say which path and body to use.

### 6.6 Where the token is kept

In **`sessionStorage`** under the name `accessToken`. It survives a page refresh but is removed when the tab closes. See decision 14 for the reasons and the risk.

### 6.7 Look and feel

New screens follow the login page colours: red `#d93645` as the main colour, warm greys for text, and silver (`#c0c4cc` and light silvers) for borders, avatars and neutral buttons. The older app shell (sidebar menu, top bar, content generator) still uses purple.

---

## 7. Main flows, step by step

### 7.1 Sign up

```
Register page                 Backend                              Database
     |  POST /api/auth/register    |                                    |
     |  {name, email, password}    |                                    |
     |---------------------------->| validate (name, email, 8+ chars)   |
     |                             | email already used? --------------->| 409 "Email is already registered"
     |                             | hash password (BCrypt)             |
     |                             | save user ------------------------>|
     |<----------------------------| 201 {id, name, email}              |
     |  then the page logs in automatically (flow 7.2)                  |
```

### 7.2 Log in

```
Login page                    Backend                              Database
     |  POST /api/auth/login       |                                    |
     |  {email, password}          |                                    |
     |---------------------------->| find user by email --------------->|
     |                             | enabled? password matches BCrypt?  |
     |                             | no -> 401 "Invalid email or password"
     |                             | yes -> create JWT                  |
     |<----------------------------| 200 {accessToken, tokenType, user} |
     | save token in sessionStorage                                     |
     |  GET /api/users/profile  (Bearer token)                          |
     |---------------------------->| JWT filter checks token + user --->|
     |<----------------------------| 200 {id, name, email}              |
     | status = authenticated -> go to the page the user wanted         |
```

The frontend loads the profile from the backend after login (instead of trusting only the login answer), so there is **one** way to know "who is logged in". It is the same path used after a page refresh.

### 7.3 Refresh the page

1. The app starts and finds a token in `sessionStorage`, so `status` is `loading`.
2. It calls `GET /api/users/profile`.
3. If the answer is OK, the user is logged in again. If it is **401**, the token is cleared and the user is sent to `/login`. If the server is down, the app shows "We couldn't load your account" with a **Try again** button, and keeps the token.

### 7.4 Protected pages

`ProtectedRoute` wraps every private page. If the user is not logged in, it redirects to `/login` and remembers the page they wanted. After login they go straight there.

### 7.5 Create a workspace

```
Sidebar -> "+ Create workspace" -> dialog -> POST /api/workspaces {name}
Backend (one transaction): save workspace (owner = you) + save membership (role OWNER)
Backend -> 201 {id, name, ownerId, ...}
Frontend: adds it to the list and selects it
```

### 7.6 Add a member

```
"+ Add member" button (Team page, or the person-plus icon next to
a workspace in the sidebar list; owner only) -> dialog -> POST /api/workspaces/{id}/members {email}
Backend: find the logged-in user
         requireOwner(workspace, user)             -> 403 if not the owner
         find the user with that email             -> 404 "User not found"
         already a member?                         -> 409
         save membership with role EDITOR
Backend -> 201 (no body)
Frontend: the dialog shows "<email> was added" and stays open so more people can be added;
          any members list on screen loads again (membersVersion goes up)
```

The frontend turns the 404 into a friendlier line: "No PublishPro-AI account uses that email. Ask them to sign up first."

---

## 8. Decisions and why we made them

| # | Decision | Why | What we give up or must watch |
|---|---|---|---|
| 1 | **Two apps in one repository** (`backend/` and `frontend/`) | One place to look, easy to change both together, but they stay independent programs | Two things to start and deploy |
| 2 | **Spring Boot on Java 21** | Mature tools for security, database and validation. Java 21 is a long-term-support version | A bigger framework to learn than a tiny one |
| 3 | **PostgreSQL on Supabase** | A real relational database with nothing to install. Good fit for linked data (users, workspaces, members) | We depend on an outside service. SSL is required |
| 4 | **JPA/Hibernate with `ddl-auto=update`** | Tables appear automatically from the entity classes, so early development is fast | There is **no migration history**, and automatic updates can be risky in production. Plan to move to Flyway or Liquibase |
| 5 | **Code grouped by feature** (`auth`, `workspace`, ...) instead of by type | Everything for one feature is in one place. New features (video, AI) are easy to add as new folders | Slightly more folders |
| 6 | **Controller -> Service -> Repository layers** | Each class has one job. Business rules are in one place and are easy to find and test | A bit more code for simple actions |
| 7 | **DTOs for requests and responses** | The API shape is separate from the database, so private fields (like `passwordHash`) can never leak | More small classes |
| 8 | **JWT, stateless login** | No server sessions to store or share, which suits a separate React app and makes scaling easy | A token cannot be cancelled before it expires. We reduce the risk by checking the user in the database on **every** request, and refresh tokens are planned |
| 9 | **BCrypt for passwords** | It is slow on purpose and adds a random "salt", so stolen hashes are hard to crack | Login costs a little CPU time |
| 10 | **One message for all login failures** ("Invalid email or password") | Stops people from testing which emails are registered | Slightly less help for a user who mistyped the email |
| 11 | **Return 401 for "not logged in"**, 403 for "not allowed" (`CustomAuthenticationEntryPoint`) | Spring's default answer is 403 for both, so the frontend could not tell them apart. With 401 the frontend knows to log the user out | Needs a small custom class |
| 12 | **`/error` is open in the security rules** | Spring sends validation and unexpected errors to `/error`. If that address were protected, every such error would look like a 403 | None |
| 13 | **CSRF off, CORS limited to `http://localhost:5173`** | We send the token in a header (not a cookie), so CSRF attacks do not apply. CORS lets in only our own frontend | The production website address **must be added** before release |
| 14 | **Token in `sessionStorage`** | It survives a refresh but is wiped when the tab closes, so it is exposed for a shorter time than in `localStorage`. It is simpler than cookies and works with a separate frontend | Scripts on the page can read it, so a successful XSS attack could steal it. Rule: **never render untrusted HTML**. A secure `HttpOnly` cookie is a possible upgrade later. Each new tab needs a new login |
| 15 | **One error handler class** (`GlobalExceptionHandler`) with our own exceptions | Same rules everywhere: each exception always gives the same HTTP code | Messages are plain text, not structured JSON. The frontend handles both |
| 16 | **All workspace permission checks in `WorkspaceAuthorizationService`**, called from services | One place to change a rule. The check happens in the service, so no new endpoint can forget it | Every service method must remember to call it |
| 17 | **Roles `OWNER` and `EDITOR`, stored as text** (`EnumType.STRING`) | Easy to read in the database, and safe if we later reorder or add roles. Two roles are enough for now | No finer permissions (viewer, admin) yet |
| 18 | **Owner is stored twice**: `workspaces.owner_id` and a membership row with role `OWNER` | Being the owner is different from being a member. Listing "my workspaces" can use one table (`workspace_members`), while ownership still has a clear field | Both must be kept in step. Creation does this in one transaction |
| 19 | **Add member by email, only if the user already has an account** (no invitations) | The simplest working version with no email sending | The person must sign up first. The screen says so. Invitations are a later feature |
| 20 | **New members are always `EDITOR`** | Keeps the first version simple and safe | The owner cannot choose another role yet |
| 21 | **React + Vite + React Router, plain CSS, no Redux** | Only two shared things exist (auth and workspace), and React Context handles them. Fewer libraries means less to maintain | If shared data grows a lot, a state library may help later |
| 22 | **One `apiClient`** for all backend calls | Token header, error reading and "401 means log out" are written once instead of in every screen | Every new call must use it |
| 23 | **Load the profile after login and after refresh** | One source of truth for "who is logged in" | One extra request after login |
| 24 | **`ProtectedRoute` and `WorkspaceProvider` placed inside the logged-in area** | The workspace list is only requested for a logged-in user, and it resets when someone logs out and another logs in | None |
| 25 | **Remember the selected workspace in `localStorage`, per user** | It is only a preference (not a secret), so it can live longer than the login | It can point to a workspace the user left. The code falls back to the first one |
| 26 | **Check the same rules in the browser** (8-character password, 100-character workspace name) | Instant feedback without a round trip | The rules exist in two places. **The backend rules always win** |
| 27 | **Log in automatically after sign-up** | One less step for the user. Register returns no token by design | Two requests in a row |
| 28 | **Secrets in environment variables**, `.env` ignored by Git | Passwords and keys never enter the code or the Git history | Every developer must set them (Spring does not read `.env` by itself) |
| 29 | **Login red + silver colour theme for new screens** | Matches the login page, with silver used for neutral parts | The older purple shell still needs to be re-coloured to match |
| 30 | **"Add member" is a dialog owned by `WorkspaceProvider`**, opened with `openAddMember(workspace)` | It can be opened from the Team page **and** from the sidebar, and it always targets the exact workspace you pick, not just the selected one | The provider holds a little more state |
| 31 | **One shared `Modal` component** for both dialogs | Escape to close, focus kept inside, and the backdrop are written once | None |
| 32 | **Analytics tab hidden, route kept** | The page has no content yet, so it is not offered. Keeping the route means nothing breaks and the tab can return with one line | `/analytics` is reachable by typing the address |
| 33 | **One "Team" tab** (`/team`) that shows the members. There is no separate "View Members" tab | Two tabs that open the same screen only confuse people | "Team" is a broad name, but today the page only lists members and adds them. Later team features (changing roles, invitations) can live on the same page |

---

## 9. Limits today and what to improve

### Backend

- **Use migrations.** Replace `ddl-auto=update` with Flyway or Liquibase before real users arrive.
- **Return 404, not 500.** Several "not found" cases throw `IllegalArgumentException` (for example `GET /api/workspaces/{id}` with a missing id, and the user lookups). They should use `NotFoundException`.
- **Make the token lifetime configurable.** `jwt.expiration` is hard-coded to 24 hours, so `JWT_EXPIRATION` in `.env.example` is ignored.
- **Add refresh tokens** (`RefreshTokenService` is an empty placeholder) and a way to end a session on the server.
- **Make CORS configurable** so the allowed website addresses come from settings, not code.
- **Member management.** Add endpoints to change a member's role and to remove a member (`UpdateMemberRoleRequest` is empty today).
- **Tests.** The only test is "the app starts", and it needs the real database settings. Add tests for login, register and the workspace permission rules.
- **Planned features (placeholders only today):**
  - `video/`: video projects inside a workspace.
  - `ai/`: an `AIProvider` interface with a `GeminiProvider`, so the AI vendor can be changed later without touching the rest of the code.
  - `thumbnail/` and `activity/` (an activity log).
- **Clean-up.** Spring prints "Using generated security password" because `CustomUserDetailsService` is empty. It is harmless, but it can confuse people reading the log.

### Frontend

- Connect the **Create Post** screen to the backend once video projects exist.
- Add **Forgot password**.
- Finish **My Content, Brand Kit and Settings** (they are placeholders). Bring the **Analytics** tab back when it has content.
- Replace the fake plan and credits card with real data.
- Apply the red and silver theme to the rest of the app shell.
- Add a catch-all route so unknown addresses do not show a blank page.
- Add tests for the login and workspace flows.

### Repository

- Fix the root `.gitignore` (it ignores `.env.example` and has the typo `.node_modules`).
- Remove files that should not be committed: `backend/register-payload.json`, `backend/response1.txt`, `backend/app-*.log`, `backend/app-pid.txt`, `*.zip`, `hs_err_pid*.log`, and the root `node_modules/`. Change any test password that was ever committed.
- Remove the unused `@supabase/*` packages from the root `package.json`.
