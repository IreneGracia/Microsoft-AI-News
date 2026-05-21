# MAI Frontend

Tech news intelligence frontend for the Microsoft Capstone project.

## Files

- `index.html` — entry point (CSS + JSX inlined; works standalone)
- `app.jsx` — React app source (editable)
- `styles.css` — CSS source (editable)
- `tweaks-panel.jsx` — Tweaks panel helpers

> `index.html` already has the contents of `styles.css`, `app.jsx`, and `tweaks-panel.jsx` inlined,
> so you can open it directly without a build step. The separate files are kept for editing.

## Run locally (VS Code)

1. Open this folder in VS Code: `File → Open Folder…`
2. Install the **Live Server** extension (Ritwick Dey)
3. Right-click `index.html` → **Open with Live Server**
4. Browser opens at `http://127.0.0.1:5500`

> Tip: opening `index.html` directly via `file://` works too, but Live Server gives you hot reload.

## Microsoft Entra ID (SSO) integration

The "Continue with Microsoft" button currently shows a **mocked** Entra-style dialog
(account picker → password → "Stay signed in?" → spinner). To wire it to real Entra:

```bash
npm init -y
npm install @azure/msal-browser
```

Then in `app.jsx`, replace these two functions inside `AuthGate`:

```js
const ssoSignin = () => { setSsoOpen(true); };

const completeSso = (user) => {
  writeSession(user);
  setSsoOpen(false);
  onAuthed(user);
};
```

with real MSAL logic, e.g.:

```js
import { PublicClientApplication } from '@azure/msal-browser';

const msal = new PublicClientApplication({
  auth: {
    clientId: '<YOUR-APP-CLIENT-ID>',
    authority: 'https://login.microsoftonline.com/<YOUR-TENANT-ID>',
    redirectUri: window.location.origin,
  },
});

const ssoSignin = async () => {
  const result = await msal.loginPopup({ scopes: ['User.Read'] });
  // Fetch profile from Graph
  const profile = await fetch('https://graph.microsoft.com/v1.0/me', {
    headers: { Authorization: `Bearer ${result.accessToken}` },
  }).then((r) => r.json());

  const user = {
    name: profile.displayName,
    email: profile.mail || profile.userPrincipalName,
    department: profile.department || 'Engineering',
    region: mapOfficeLocationToRegion(profile.officeLocation),
    signedInAt: Date.now(),
    sso: true,
  };
  writeSession(user);
  onAuthed(user);
};
```

## Expected `user` shape

The app stores this in `localStorage` under key `mai_user`:

```ts
{
  name: string,
  email: string,         // must end with @microsoft.com (enforced on signup form)
  department: string,    // one of: Engineering, Cloud + AI, Azure, Research, Product, …
  region: string,        // "na" | "eu" | "china" | "apac" | "india" | "latam" | "mea"
  signedInAt: number     // Date.now()
}
```

## Preferences taxonomy

The preferences wizard is aligned with `sources.json` from the data team:

- **Role**: engineer / business / legal / exec / research (auto-prefills depth)
- **Region**: 7 Microsoft regions (prefilled from signup)
- **Topics**: 13 Technology + 6 Business + 7 Regulation & Policy tags
- **Depth**: Deep dive (IC) vs Brief (exec)
- **Delivery**: Daily brief / Weekly digest / Breaking-news alerts (+ keywords)
- **Voice** (extra): Calm / Plain / Technical + Quiet↔Lively slider

## Migrating to a real React project

When you outgrow inline Babel, scaffold a Vite project:

```bash
npm create vite@latest mai-frontend-vite -- --template react
cd mai-frontend-vite
npm install
# Copy app.jsx → src/App.jsx, styles.css → src/styles.css
# Move <TweaksPanel>, <PrefsDeck>, <AuthGate> etc. into src/components/
```
