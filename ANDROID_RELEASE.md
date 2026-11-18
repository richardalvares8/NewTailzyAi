# Tailzyai on Android / Google Play

The React frontend is wrapped as a native Android app with [Capacitor](https://capacitorjs.com).
The app bundles the built web UI and talks to the FastAPI backend over HTTPS.

- App ID (package name): `com.tailzyai.app` - **permanent once published on Play**, change it in
  `frontend/capacitor.config.json` and `frontend/android/app/build.gradle` (`namespace`, `applicationId`)
  before your first upload if you want something else.
- Native project: `frontend/android/`
- Icon / splash sources: `frontend/assets/` (regenerate with `npx @capacitor/assets generate --android`)
- Play listing icon: `store-assets/play-store-icon-512.png`

## 1. Host the backend

The app needs a publicly reachable backend over **HTTPS** (Android blocks plain HTTP).
Deploy `backend/` (FastAPI + MongoDB) to any host (Render, Railway, Fly.io, a VPS, ...) and set:

| Variable | Notes |
|---|---|
| `MONGO_URL`, `DB_NAME` | e.g. a MongoDB Atlas cluster |
| `JWT_SECRET` | a long random string - do **not** use the default in `server.py` |
| `EMERGENT_LLM_KEY` | used by the Copilot chat (see "Known follow-ups") |
| `CORS_ORIGINS` | include `https://localhost` (the origin the Android app uses) |

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

## Known follow-ups

- The Copilot chat uses the `emergentintegrations` package and `EMERGENT_LLM_KEY`, which are tied to
  the Emergent platform. Outside Emergent, switch the call in `backend/server.py` to an LLM provider
  SDK with your own API key.
