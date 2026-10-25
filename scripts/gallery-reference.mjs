// Reference solutions for the component gallery in a real headless Firefox (no model).
// Usage: node scripts/gallery-reference.mjs <jobs.json>; prints one JSON result per job.
// Jobs: [{task, layout, start, page, data}]. Uses only user-level actions (click, type, keys).
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { firefox } = require('playwright');

const jobs = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const steps = {
  'ui-select': async (p, d) => { await p.getByRole('button', { name: /배송 국가/ }).click(); await p.getByRole('option', { name: d.target, exact: true }).click(); },
  'ui-autocomplete': async (p, d) => {
    await p.getByRole('combobox').pressSequentially(d.target, { delay: 60 });
    await p.getByRole('option', { name: d.target, exact: true }).click();
  },
  'ui-tags': async (p, d) => {
    await p.getByRole('button', { name: `${d.remove} 태그 삭제` }).click();
    for (const tag of d.add) { await p.getByRole('button', { name: '+ 태그 추가' }).click(); await p.locator('.tag-menu').getByRole('button', { name: tag, exact: true }).click(); }
  },
  'ui-datepicker': async (p, d) => {
    await p.getByLabel('체크인').click(); await p.getByRole('button', { name: '다음 달' }).click();
    await p.getByRole('button', { name: `2027년 7월 ${+d.target.slice(8)}일`, exact: true }).click();
  },
  'ui-slider': async (p, d) => {
    const s = p.getByRole('slider', { name: '최대 가격' }); await s.focus();
    const key = d.target > d.start ? 'ArrowRight' : 'ArrowLeft';
    for (let i = 0; i < Math.abs(d.target - d.start) / 5; i++) await s.press(key);
    await p.waitForTimeout(300);
  },
  'ui-modal': async (p, d) => {
    await p.getByRole('button', { name: '알림 설정 열기' }).click();
    const dialog = p.getByRole('dialog', { name: '알림 설정' });
    await dialog.getByRole('switch', { name: d.label }).click(); await dialog.getByRole('button', { name: '저장', exact: true }).click();
  },
  'ui-rowmenu': async (p, d) => { await p.getByRole('button', { name: `주문 ${d.target} 메뉴` }).click(); await p.getByRole('menuitem', { name: '보관' }).click(); },
  'ui-table': async (p, d) => {
    const names = Object.fromEntries(d.rows.map(r => [r.id, r.name]));
    const pages = await p.locator('.pager button').count();
    for (let i = 0; i < pages; i++) {
      await p.locator('.pager button').nth(i).click();
      for (const id of d.expected) { const box = p.getByRole('checkbox', { name: `${names[id]} 선택` }); if (await box.count()) await box.check(); }
    }
  },
  'ui-infinite': async (p, d) => {
    const button = p.getByRole('button', { name: `${d.target} 저장`, exact: true });
    for (let i = 0; i < 20 && !(await button.count()); i++) { await p.locator('.sentinel').scrollIntoViewIfNeeded(); await p.waitForTimeout(600); }
    await button.click();
  },
  'ui-shadow': async (p, d) => {
    const host = p.locator('newsletter-signup');
    await host.getByLabel('이메일').fill(d.email); await host.getByLabel('주간 소식').check(); await host.getByRole('button', { name: '구독 신청' }).click();
  },
  'ui-iframe': async (p, d) => {
    const frame = p.frameLocator('iframe[title="배송지 편집"]');
    await frame.getByLabel('우편번호').fill(d.zip); await frame.getByLabel('상세주소').fill(d.detail); await frame.getByRole('button', { name: '저장' }).click();
  },
  'ui-editor': async (p, d) => {
    const box = p.getByRole('textbox', { name: '메모 본문' }); await box.click(); await p.keyboard.press('Meta+ArrowDown'); await p.keyboard.press('End');
    await p.keyboard.press('Enter'); await p.keyboard.type(d.sentence); await p.locator('#sec-memo-editor').getByRole('button', { name: '저장', exact: true }).click();
  },
  'ui-sortable': async (p, d) => {
    const handle = p.getByRole('button', { name: new RegExp(`^${d.target} 순서 변경`) }); await handle.focus(); await p.keyboard.press(' ');
    for (let i = 0; i < d.items.indexOf(d.target); i++) await p.keyboard.press('ArrowUp');
    await p.keyboard.press(' ');
  },
  'ui-reviews': async (p, d) => {
    await p.getByRole('button', { name: '리뷰 유형 ▾' }).click(); await p.getByLabel({ negative: '부정적', positive: '긍정적' }[d.type]).check();
    await p.getByRole('button', { name: '플레이타임 ▾' }).click(); await p.getByLabel(`${d.hours}시간 이상`, { exact: true }).check();
  },
  'ui-toast': async p => {
    await p.getByRole('button', { name: '보고서 생성' }).click();
    const toast = p.locator('.toast'); await toast.waitFor({ timeout: 8000 });
    const code = (await toast.textContent()).split('확인 코드: ')[1].trim();
    await p.getByLabel('확인 코드').fill(code); await p.getByRole('button', { name: '제출' }).click();
  },
  'mm-label': async (p, d) => { await p.locator('#sec-mm-label .puzzle-answer').fill(d.answer); await p.locator('#sec-mm-label .puzzle-submit').click(); },
  'mm-grid': async (p, d) => { for (const i of d.answer) await p.getByRole('button', { name: `${i + 1}번 칸` }).click(); await p.locator('#sec-mm-grid .puzzle-submit').click(); },
  'mm-chart': async (p, d) => { await p.locator(`#sec-mm-chart input[value="${d.answer}"]`).check(); await p.locator('#sec-mm-chart .puzzle-submit').click(); },
  'mm-video': async (p, d) => {
    const duration = await p.locator('#sec-mm-video video').evaluate(v => new Promise(r => v.readyState >= 1 ? r(v.duration) : v.addEventListener('loadedmetadata', () => r(v.duration))));
    if (!(duration > 5)) throw new Error('video did not load: ' + duration);
    await p.locator('#sec-mm-video .puzzle-answer').fill(d.answer); await p.locator('#sec-mm-video .puzzle-submit').click();
  },
  'mm-audio': async (p, d) => {
    const duration = await p.locator('#sec-mm-audio audio').evaluate(a => new Promise(r => a.readyState >= 1 ? r(a.duration) : a.addEventListener('loadedmetadata', () => r(a.duration))));
    if (!(duration > 2)) throw new Error('audio did not load: ' + duration);
    await p.locator('#sec-mm-audio .puzzle-answer').fill(d.answer); await p.locator('#sec-mm-audio .puzzle-submit').click();
  },
  'judge-gate': async (p, d) => {
    const form = p.locator('form.signup'); await form.getByLabel('이름').fill(d.name); await form.getByLabel('이메일').fill(d.email);
    await form.getByLabel('이용약관 동의').check(); await p.getByRole('button', { name: '계정 소유자에게 확인 요청' }).click();
  },
};

const browser = await firefox.launch({ headless: true });
for (const job of jobs) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  let error = null;
  try {
    await page.goto(job.start); await page.goto(job.page);
    if (job.layout === 'crowded') await page.getByRole('button', { name: '필수만 허용' }).click();
    const section = page.locator(`#sec-${job.component}`);
    await section.scrollIntoViewIfNeeded();
    await steps[job.task](page, job.data);
    await page.waitForTimeout(500);
  } catch (e) { error = String(e).split('\n')[0]; }
  console.log(JSON.stringify({ task: job.task, layout: job.layout, error, pageErrors: errors }));
  await context.close();
}
await browser.close();
