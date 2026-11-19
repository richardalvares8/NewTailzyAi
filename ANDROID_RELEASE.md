# Tailzyai on Android / Google Play

The React frontend is wrapped as a native Android app with [Capacitor](https://capacitorjs.com).
The app bundles the built web UI and talks to the FastAPI backend over HTTPS.

- App ID (package name): `com.tailzyai.app` - **permanent once published on Play**, change it in
  `frontend/capacitor.config.json` and `frontend/android/app/build.gradle` (`namespace`, `applicationId`)
  before your first upload if you want something else.
- Native project: `frontend/android/`
- Icon / splash sources: `frontend/assets/` (regenerate with `npx @capacitor/assets generate --android`)
- Play listing icon: `store-assets/play-store-icon-512.png`

## 1. Host the backend (no Emergent needed)

The app needs the backend running at a public **HTTPS** address. Everything below has a free tier
and can be done from a phone or tablet browser.

**a. Database - MongoDB Atlas** (mongodb.com/atlas)
1. Sign up and create a free **M0** cluster.
2. *Database Access*: add a user with a password (letters and numbers only keeps it simple).
3. *Network Access*: add `0.0.0.0/0` (Render's addresses change, so allow all).
4. *Connect -> Drivers*: copy the connection string (`mongodb+srv://...`) and put your password in it.

**b. AI key - Google Gemini** (aistudio.google.com/apikey)
1. Sign in with a Google account and tap **Create API key**. Copy it.

**c. Server - Render** (render.com)
1. Sign up with GitHub and allow access to this repository.
2. **New -> Blueprint**, pick this repo and the branch. Render reads `render.yaml`.
3. Paste `MONGO_URL` (from a) and `GEMINI_API_KEY` (from b) when asked. `JWT_SECRET` is generated for you.
4. When it is live, open `https://<your-service>.onrender.com/api/` - it should say `"status":"healthy"`.
5. Set the GitHub variable `REACT_APP_BACKEND_URL` to `https://<your-service>.onrender.com` and rebuild the APK.

Render's free plan sleeps after ~15 minutes without traffic; the first request after that takes
about a minute. For a published app, upgrade the service to a paid plan (about $7/month) so it stays awake.

Backend environment variables (`backend/server.py`):

| Variable | Notes |
|---|---|
| `MONGO_URL`, `DB_NAME` | MongoDB connection |
| `JWT_SECRET` | long random string - never the default in `server.py` |
| `GEMINI_API_KEY` | Copilot chat. `GEMINI_MODEL` optionally overrides the model (default `gemini-flash-latest`) |
| `CORS_ORIGINS` | `*`, or a list that includes `https://localhost` (the Android app's origin) |

## 2. Build an APK with GitHub Actions (no local setup needed)

1. In GitHub: **Settings → Secrets and variables → Actions → Variables**, add
   `REACT_APP_BACKEND_URL` = your backend URL, e.g. `https://api.tailzyai.com` (no trailing `/api`).
2. Push to `main` (or run **Actions → Android build → Run workflow**).
3. Download the `tailzyai-debug-apk` artifact from the run and install it on a phone
   (enable "Install unknown apps").

## 3. Signed build for Google Play

Play requires an **AAB** signed with your upload key.

Create the key once (keep the file and passwords safe - losing them means you can't ship updates
without contacting Google support):

```bash
keytool -genkeypair -v -keystore tailzyai-upload.jks -keyalg RSA -keysize 2048 \
  -validity 10000 -alias tailzyai
base64 -w0 tailzyai-upload.jks   # copy the output
```

Add these repository **secrets**:

| Secret | Value |
|---|---|
| `ANDROID_KEYSTORE_BASE64` | base64 output above |
| `ANDROID_KEYSTORE_PASSWORD` | keystore password |
| `ANDROID_KEY_ALIAS` | `tailzyai` |
| `ANDROID_KEY_PASSWORD` | key password |

The next workflow run also produces a `tailzyai-release` artifact containing `app-release.aab`
(upload this to Play) and a signed `app-release.apk`. `versionCode` is the workflow run number, so
every build is uploadable; push a tag like `v1.2.0` to set `versionName` to `1.2.0`.

## Building locally (optional)

Requires Node 22, JDK 21 and the Android SDK (Android Studio is the easiest way).

```bash
cd frontend
yarn install
echo "REACT_APP_BACKEND_URL=https://your-backend" > .env.production.local
yarn android:apk        # -> android/app/build/outputs/apk/debug/app-debug.apk
yarn android:open       # open in Android Studio
```

For local release builds, create `frontend/android/keystore.properties` (git-ignored):

```properties
storeFile=/absolute/path/to/tailzyai-upload.jks
storePassword=...
keyAlias=tailzyai
keyPassword=...
```

then `yarn android:bundle`.

## Google Play checklist

- [ ] Google Play Developer account ($25 one-time)
- [ ] Backend deployed on HTTPS with a strong `JWT_SECRET`
- [ ] **Privacy policy URL** (required - the app collects emails and pet data)
- [ ] **Account deletion**: Play requires apps with sign-up to offer in-app account deletion
      and a web link to request it
- [ ] Data safety form, content rating questionnaire, target audience
- [ ] Store listing: 512×512 icon (`store-assets/`), 1024×500 feature graphic, 2+ phone screenshots
- [ ] New personal developer accounts must run a closed test (12+ testers for 14 days) before production
