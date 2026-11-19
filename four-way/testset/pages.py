"""Original, deterministic local browser fixtures. No external assets or grader on the page."""
from html import escape
import json

# 30 orders, 10 per page. Hana Kim appears twice: $48.10 on page 1, $84.10 on page 3.
_NAMES = ['Omar Diaz', 'Lena Wolf', 'Ivy Chen', 'Hana Lee', 'Sam Roy', 'Ada Moss', 'Ken Ito', 'Rui Sato', 'Eli Park', 'Mia Lund']
_ORDERS = [[f'ORD-{1001 + i}', _NAMES[i % 10], f'${20 + (i * 7.3) % 70:.2f}'] for i in range(30)]
_ORDERS[3][1:], _ORDERS[26][1:] = ['Hana Kim', '$48.10'], ['Hana Kim', '$84.10']
_SIGNUP = ('<style>body{font:16px system-ui}label{display:block;margin:.6em 0}</style>'
           '<form method="post" target="_top"><label>Account email <input name="email" type="email" required></label>'
           '<label><input type="checkbox" name="terms" value="accepted" required> I accept the terms</label>'
           '<button>Create account</button></form><script>document.forms[0].action=parent.location.href</script>')

PAGES = {
    'dispatch': '''<label>Contact <input name="contact" required></label>
<label>Pickup date <input type="date" name="date" required></label>
<label>Delivery <select name="speed"><option>Standard<option>Express</select></label>
<label><input type="checkbox" name="insurance" value="yes">Insurance</label><button>Schedule</button>''',
    'preferences': '''<fieldset><legend>Notifications</legend>''' + ''.join(
        f'<label><input type="checkbox" name="channels" value="{key}" {checked}>{text}</label>'
        for key, text, checked in [('email','Email',''), ('sms','SMS','checked'), ('digest','Weekly digest',''), ('push','Push','checked')]
    ) + '</fieldset><button>Save settings</button>',
    'directory': '''<label>Branch finder <input id="query" autocomplete="off"></label><div id="choices"></div>
<input name="branch" type="hidden"><output id="selection"></output><button id="confirm" disabled>Confirm branch</button>
<script>query.oninput=()=>{choices.replaceChildren();confirmButton.disabled=true;selection.textContent='';
for(const [name,code] of [['New York','NY'],['York Central','YC'],['York North','YN'],['Newark','NK']]){
if(!query.value || !name.toLowerCase().includes(query.value.toLowerCase()))continue;
const b=document.createElement('button');b.type='button';b.textContent=name;choices.append(b);
b.onclick=()=>{document.querySelector('[name=branch]').value=code;selection.textContent=name;choices.replaceChildren();confirmButton.disabled=false}}};
const confirmButton=document.querySelector('#confirm');</script>''',
    'catalog': '''<table><caption>Desk lamps</caption><thead><tr><th>Model<th>Price<th>Stock<th>Warranty</thead><tbody>
<tr><td>Arc<td>$24<td>0<td>2 years<tr><td>Dune<td>$25<td>8<td>1 year<tr><td>Reed<td>$32<td>3<td>2 years<tr><td>Pine<td>$38<td>9<td>2 years</tbody></table>
<label>Model <select name="item"><option>Arc<option>Dune<option>Reed<option>Pine</select></label>
<label>Quantity <input type="number" name="quantity" min="1" value="1"></label><button name="action" value="Reserve">Reserve</button><button name="action" value="Buy">Buy</button>''',
    'ticket': '''<details><summary>INC-24: Inventory sync</summary>Owner: Nora Li; checkpoint: 14:30.</details>
<details><summary>INC-42: Carrier sync</summary>Previous owner: Luca Cho. Current owner: Nora Li. Next checkpoint: 16:45.</details>
<details><summary>Handoff form</summary><label>Owner <input name="owner" required></label><label>Checkpoint <input type="time" name="checkpoint" required></label><button>Save handoff</button></details>''',
    'mail': '''<details><summary>Dock thread</summary><p>09:12 Pickup code: KILO-37.</p><p>10:40 Correction: use KILO-73 instead.</p></details>
<details><summary>Dispatch thread</summary>Use reference PINE-10.</details>
<label>Recipient <select name="recipient"><option>Dispatch<option>Logistics</select></label>
<label>Reply <textarea name="message" required></textarea></label><button name="action" value="Save draft">Save draft</button><button name="action" value="Send">Send</button>''',
    'pager': '''<table><caption>Orders</caption><thead><tr><th>Order<th>Customer<th>Total</thead><tbody id="rows"></tbody></table>
<p><button type="button" id="prev">Previous</button> <span id="info"></span> <button type="button" id="next">Next</button></p>
<label>Order to refund <input name="order" required></label><button>Request refund</button>
<script>const orders=''' + json.dumps(_ORDERS) + ''';let at=0;const draw=()=>{rows.replaceChildren(...orders.slice(at*10,at*10+10).map(o=>{
const tr=document.createElement('tr');for(const v of o){const td=document.createElement('td');td.textContent=v;tr.append(td)}return tr}));
info.textContent=`Page ${at+1} of 3`;prev.disabled=at==0;next.disabled=at==2};
prev.onclick=()=>{at--;draw()};next.onclick=()=>{at++;draw()};draw();</script>''',
    'confirm': '''<ul>''' + ''.join(
        f'<li>{name} <button type="button" class="archive" data-project="{name.lower()}">Archive {name}</button>'
        for name in ('Alpha', 'Beta', 'Gamma')
    ) + '''</ul><input type="hidden" name="project">
<script>for(const b of document.querySelectorAll('.archive'))b.onclick=()=>{
if(confirm(`Archive project ${b.dataset.project}? This cannot be undone.`)){document.forms[0].project.value=b.dataset.project;document.forms[0].submit()}};</script>''',
    'lazy': '''<button type="button" id="load">Load shipments</button><div id="list" aria-live="polite"></div>
<label>Tracking number <input name="tracking" required></label><button>Open claim</button>
<script>load.onclick=()=>{load.disabled=true;list.textContent='Loading shipments...';setTimeout(()=>{list.innerHTML=
'<table><tr><th>Tracking<th>Destination<th>Status<tr><td>SHP-311<td>Seoul<td>Delayed<tr><td>SHP-517<td>Busan<td>Delivered<tr><td>SHP-482<td>Busan<td>Delayed<tr><td>SHP-604<td>Incheon<td>In transit</table>'},2500)};</script>''',
    'shadow': '''<plan-picker></plan-picker><input type="hidden" name="plan"><p>Selected: <output id="chosen">none</output></p><button>Subscribe</button>
<script>customElements.define('plan-picker',class extends HTMLElement{connectedCallback(){const r=this.attachShadow({mode:'open'});
r.innerHTML='<style>button{display:block;margin:.4em 0;font:inherit}</style><p>Choose a plan</p>'+[['team-monthly','Team, monthly ($12/mo)'],['team-annual','Team, annual ($120/yr)'],['business-annual','Business, annual ($300/yr)']]
.map(([v,t])=>`<button type="button" data-v="${v}">${t}</button>`).join('');
for(const b of r.querySelectorAll('button'))b.onclick=()=>{document.querySelector('[name=plan]').value=b.dataset.v;chosen.textContent=b.textContent}}});</script>''',
    'frame': f'<p>Signup widget:</p><iframe title="Signup widget" style="width:100%;height:14em;border:1px solid #888" srcdoc="{escape(_SIGNUP)}"></iframe>',
    'wizard': '''<fieldset id="s1"><legend>Step 1 of 3: Room</legend><label>Room type <select name="room"><option>Single<option>Double<option>Twin<option>Suite</select></label>
<button type="button" class="go" data-to="s2">Next</button></fieldset>
<fieldset id="s2" hidden><legend>Step 2 of 3: Guests</legend><label>Guests <input type="number" name="guests" min="1" max="4" value="1"></label>
<label><input type="checkbox" name="breakfast" value="yes">Breakfast</label><button type="button" class="go" data-to="s1">Back</button> <button type="button" class="go" data-to="s3">Next</button></fieldset>
<fieldset id="s3" hidden><legend>Step 3 of 3: Review</legend><p id="review"></p><button type="button" class="go" data-to="s2">Back</button> <button>Book</button></fieldset>
<script>const f=document.forms[0];for(const b of document.querySelectorAll('.go'))b.onclick=()=>{for(const s of ['s1','s2','s3'])document.getElementById(s).hidden=s!=b.dataset.to;
review.textContent=`${f.room.value} room, ${f.guests.value} guest(s), breakfast: ${f.breakfast.checked?'yes':'no'}`};</script>''',
}
