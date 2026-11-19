// UI login for Aside's REPL (no cookie or CDP access). Port of webarena-pro-core autologin flows.
// The runner prepends `const SITE, BASE, CRED;` and attaches `page` to the tab.
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
async function until(check, ms = 20000) {
  for (const end = Date.now() + ms; Date.now() < end; await wait(250)) if (await check()) return;
  throw new Error(`login check timed out for ${SITE}`);
}
const path = async () => new URL(await page.url()).pathname;
const authOk = () => page.evaluate(async () => (await fetch('/api/auth/check', { credentials: 'include' })).ok);
// [login page, first form field, fill+submit, logged-in check]
const FLOWS = {
  'flight-search': [BASE, () => page.getByPlaceholder('Passkey'), async () => {
    await page.getByPlaceholder('Passkey').fill(CRED.passkey);
    await page.getByRole('button', { name: 'Continue' }).click();
  }, authOk],
  jobportal: [`${BASE}/accounts/login/`, () => page.getByLabel('Username or Email'), async () => {
    await page.locator(`input[name="user_type"][value="${CRED.user_type}"]`).check();
    await page.getByLabel('Username or Email').fill(CRED.username);
    await page.getByLabel('Password').fill(CRED.password);
    await page.getByLabel('Remember me').check();
    await page.getByRole('button', { name: 'Sign In' }).click();
  }, async () => (await path()).startsWith('/dashboard/')],
  thunderbird: [BASE, () => page.locator('#rcmloginuser'), async () => {
    await page.locator('#rcmloginuser').fill(CRED.username);
    await page.locator('#rcmloginpwd').fill(CRED.password);
    await page.locator('#rcmloginsubmit').click();
  }, async () => (await page.locator('#rcmloginuser').count()) === 0],
  travelmap: [`${BASE}/login`, () => page.getByPlaceholder('name@example.com'), async () => {
    await page.getByPlaceholder('name@example.com').fill(CRED.username);
    await page.getByPlaceholder('Enter your password').fill(CRED.password);
    await page.getByRole('button', { name: 'Sign In' }).click();
  }, async () => (await path()) !== '/login'],
  'x-lite': [`${BASE}/login`, () => page.locator('[data-test="login-username"]'), async () => {
    await page.locator('[data-test="login-username"]').fill(CRED.username);
    await page.locator('[data-test="login-password"]').fill(CRED.password);
    await page.locator('[data-test="login-submit"]').click();
  }, async () => !(await path()).startsWith('/login')],
  'minerva-lite': [`${BASE}/login`, () => page.locator('[data-test="login-student-id"]'), async () => {
    await page.locator('[data-test="login-student-id"]').fill(CRED.username);
    await page.locator('[data-test="login-password"]').fill(CRED.password);
    await page.locator('[data-test="login-submit"]').click();
  }, async () => !(await path()).startsWith('/login')],
  'password-manager': [BASE, () => page.getByPlaceholder('Enter your username'), async () => {
    await page.getByPlaceholder('Enter your username').fill(CRED.username);
    await page.getByPlaceholder('Enter your master password').fill(CRED.password);
    await page.getByRole('button', { name: 'Log in' }).click();
  }, async () => (await page.getByPlaceholder('Enter your master password').count()) === 0],
  pipedrive: [`${BASE}/login`, () => page.getByLabel('Email'), async () => {
    await page.getByLabel('Email').fill(CRED.username);
    await page.getByLabel('Password').fill(CRED.password);
    await page.getByRole('button', { name: 'Sign in' }).click();
  }, async () => (await path()) !== '/login'],
};
const [loginUrl, field, submit, loggedIn] = FLOWS[SITE];
await page.goto(loginUrl);
await wait(1000);
if ((await field().count()) > 0) await submit();
await until(loggedIn);
console.log(`LOGIN_OK ${SITE} ${await page.url()}`);
