// Exercise rendered controls, not the POST endpoint. Run via test_benchmark.py.
const { firefox } = require('playwright');
(async () => {
  const browser = await firefox.launch();
  try {
    const p = await browser.newPage();
    const actions = [
      async () => { await p.getByLabel('Contact').fill('Mira'); await p.getByLabel('Pickup date').fill('2027-04-12'); await p.getByLabel('Delivery').selectOption('Express'); await p.getByText('Schedule', {exact:true}).click(); },
      async () => { for (const label of ['Email','Weekly digest','SMS','Push']) await p.getByLabel(label,{exact:true}).click(); await p.getByText('Save settings').click(); },
      async () => { await p.getByLabel('Branch finder').fill('York'); await p.getByText('York Central',{exact:true}).click(); await p.getByText('Confirm branch').click(); },
      async () => { await p.getByLabel('Model').selectOption('Reed'); await p.getByRole('button',{name:'Reserve'}).click(); },
      async () => { await p.getByText('INC-42: Carrier sync').click(); await p.getByText('Handoff form').click(); await p.getByLabel('Owner').fill('Nora Li'); await p.getByLabel('Checkpoint').fill('16:45'); await p.getByText('Save handoff').click(); },
      async () => { await p.getByText('Dock thread').click(); await p.getByLabel('Recipient').selectOption('Logistics'); await p.getByLabel('Reply').fill('KILO-73'); await p.getByText('Save draft').click(); },
      async () => { await p.getByText('Next').click(); await p.getByText('Next').click(); await p.getByRole('row',{name:/Hana Kim/}).getByRole('cell',{name:/^ORD-/}).waitFor(); const id = await p.getByRole('row',{name:/Hana Kim.*84\.10/}).getByRole('cell').first().textContent(); await p.getByLabel('Order to refund').fill(id); await p.getByText('Request refund').click(); },
      async () => { p.once('dialog', d => d.accept()); await p.getByText('Archive Beta').click(); },
      async () => { await p.getByText('Load shipments').click(); await p.getByText('SHP-482').waitFor(); await p.getByLabel('Tracking number').fill('SHP-482'); await p.getByText('Open claim').click(); },
      async () => { await p.getByRole('button',{name:/Team, annual/}).click(); await p.getByText('Subscribe').click(); },
      async () => { const f = p.frameLocator('iframe'); await f.getByLabel('Account email').fill('ops@example.test'); await f.getByLabel('I accept the terms').check(); await f.getByText('Create account').click(); },
      async () => { await p.getByLabel('Room type').selectOption('Twin'); await p.getByRole('button',{name:'Next'}).click(); await p.getByLabel('Guests').fill('2'); await p.getByLabel('Breakfast').check(); await p.getByRole('button',{name:'Next'}).click(); await p.getByText('Twin room, 2 guest(s), breakfast: yes').waitFor(); await p.getByRole('button',{name:'Book'}).click(); },
    ];
    for (const [i, url] of process.argv.slice(2).entries()) {
      await p.goto(url); await actions[i](); await p.getByRole('heading',{name:'Recorded'}).waitFor();
    }
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
