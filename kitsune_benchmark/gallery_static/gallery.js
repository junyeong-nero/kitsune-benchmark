// Gallery components. Each component reports its state to the local fixture server;
// grading uses that server state, never the agent's own claims. No external requests.
(() => {
  'use strict';
  const BASE = document.body.dataset.base;
  const $ = (root, sel) => root.querySelector(sel);
  const $$ = (root, sel) => Array.from(root.querySelectorAll(sel));

  function report(component, value) {
    return fetch(BASE + '/state', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({component, value}), credentials: 'same-origin',
    }).then(r => r.json()).catch(() => ({}));
  }
  function el(tag, attrs = {}, text) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function closeOnOutside(panel, trigger, onClose) {
    const handler = event => {
      if (!panel.contains(event.target) && !trigger.contains(event.target)) { onClose(); document.removeEventListener('mousedown', handler, true); }
    };
    setTimeout(() => document.addEventListener('mousedown', handler, true), 0);
  }

  const init = {
    // 1. Custom listbox select (div/ul, not a native <select>).
    select(root) {
      const trigger = $(root, '.cselect-trigger'), list = $(root, '[role=listbox]'), value = $(root, '.cselect-value');
      const close = () => { list.hidden = true; trigger.setAttribute('aria-expanded', 'false'); };
      trigger.addEventListener('click', () => {
        const open = list.hidden; list.hidden = !open; trigger.setAttribute('aria-expanded', String(open));
        if (open) closeOnOutside(list, trigger, close);
      });
      $$(list, '[role=option]').forEach(option => option.addEventListener('click', () => {
        $$(list, '[role=option]').forEach(o => o.setAttribute('aria-selected', 'false'));
        option.setAttribute('aria-selected', 'true'); value.textContent = option.textContent; close();
        report(root.dataset.component, option.dataset.value);
      }));
    },
    // 2. Autocomplete combobox: suggestions arrive asynchronously; only a picked suggestion counts.
    autocomplete(root) {
      const input = $(root, 'input'), list = $(root, '[role=listbox]');
      let timer = null, picked = false;
      input.addEventListener('input', () => {
        if (picked) { picked = false; report(root.dataset.component, null); }
        clearTimeout(timer);
        timer = setTimeout(async () => {
          const q = input.value.trim();
          list.replaceChildren();
          if (!q) { list.hidden = true; input.setAttribute('aria-expanded', 'false'); return; }
          const response = await fetch(BASE + '/api/cities?q=' + encodeURIComponent(q), {credentials: 'same-origin'});
          const cities = await response.json();
          cities.forEach(city => {
            const li = el('li', {role: 'option'}, city);
            li.addEventListener('click', () => { input.value = city; list.hidden = true; input.setAttribute('aria-expanded', 'false'); picked = true; report(root.dataset.component, city); });
            list.append(li);
          });
          list.hidden = cities.length === 0;
          input.setAttribute('aria-expanded', String(cities.length > 0));
        }, 350);
      });
    },
    // 3. Tag multiselect with removable chips and an add popover.
    tags(root) {
      const chips = $(root, '.chips'), add = $(root, '.tag-add'), menu = $(root, '.tag-menu');
      const current = () => $$(chips, '.chip').map(c => c.dataset.tag);
      const sync = () => report(root.dataset.component, current());
      const chip = tag => {
        const node = el('span', {class: 'chip', 'data-tag': tag}, tag + ' ');
        const remove = el('button', {type: 'button', 'aria-label': tag + ' 태그 삭제'}, '✕');
        remove.addEventListener('click', () => { node.remove(); sync(); });
        node.append(remove); return node;
      };
      JSON.parse(root.dataset.initial).forEach(tag => chips.append(chip(tag)));
      add.addEventListener('click', () => {
        menu.hidden = !menu.hidden;
        if (!menu.hidden) closeOnOutside(menu, add, () => { menu.hidden = true; });
      });
      $$(menu, 'button').forEach(button => button.addEventListener('click', () => {
        if (!current().includes(button.dataset.tag)) { chips.append(chip(button.dataset.tag)); sync(); }
        menu.hidden = true;
      }));
    },
    // 4. Date picker: read-only input, calendar popup with month navigation.
    datepicker(root) {
      const input = $(root, 'input'), popup = $(root, '.calendar'), title = $(root, '.cal-title'), grid = $(root, '.cal-grid');
      const today = new Date(root.dataset.today + 'T00:00:00');
      let view = new Date(today.getFullYear(), today.getMonth(), 1);
      const pad = n => String(n).padStart(2, '0');
      const render = () => {
        title.textContent = `${view.getFullYear()}년 ${view.getMonth() + 1}월`;
        grid.replaceChildren();
        const first = new Date(view.getFullYear(), view.getMonth(), 1).getDay();
        for (let i = 0; i < first; i++) grid.append(el('span'));
        const days = new Date(view.getFullYear(), view.getMonth() + 1, 0).getDate();
        for (let d = 1; d <= days; d++) {
          const iso = `${view.getFullYear()}-${pad(view.getMonth() + 1)}-${pad(d)}`;
          const b = el('button', {type: 'button', 'aria-label': `${view.getFullYear()}년 ${view.getMonth() + 1}월 ${d}일`}, String(d));
          b.addEventListener('click', () => { input.value = iso; popup.hidden = true; report(root.dataset.component, iso); });
          grid.append(b);
        }
      };
      input.addEventListener('click', () => { popup.hidden = !popup.hidden; render(); });
      $(root, '.cal-prev').addEventListener('click', () => { view = new Date(view.getFullYear(), view.getMonth() - 1, 1); render(); });
      $(root, '.cal-next').addEventListener('click', () => { view = new Date(view.getFullYear(), view.getMonth() + 1, 1); render(); });
    },
    // 5. ARIA slider (div), keyboard and pointer.
    slider(root) {
      const thumb = $(root, '[role=slider]'), track = $(root, '.track'), out = $(root, '.slider-value');
      const min = +thumb.getAttribute('aria-valuemin'), max = +thumb.getAttribute('aria-valuemax'), step = +root.dataset.step;
      let value = +thumb.getAttribute('aria-valuenow'), timer = null;
      const set = (v, silent) => {
        value = Math.max(min, Math.min(max, Math.round(v / step) * step));
        thumb.setAttribute('aria-valuenow', String(value)); thumb.setAttribute('aria-valuetext', value + root.dataset.unit);
        thumb.style.left = ((value - min) / (max - min) * 100) + '%'; out.textContent = value + root.dataset.unit;
        if (silent) return;
        clearTimeout(timer); timer = setTimeout(() => report(root.dataset.component, value), 150);
      };
      thumb.addEventListener('keydown', e => {
        const moves = {ArrowRight: step, ArrowUp: step, ArrowLeft: -step, ArrowDown: -step, PageUp: step * 4, PageDown: -step * 4};
        if (e.key in moves) { set(value + moves[e.key]); e.preventDefault(); }
        if (e.key === 'Home') { set(min); e.preventDefault(); }
        if (e.key === 'End') { set(max); e.preventDefault(); }
      });
      const fromPointer = e => { const r = track.getBoundingClientRect(); set(min + (e.clientX - r.left) / r.width * (max - min)); };
      track.addEventListener('pointerdown', e => { fromPointer(e); track.setPointerCapture(e.pointerId); });
      track.addEventListener('pointermove', e => { if (e.buttons) fromPointer(e); });
      set(value, true);
    },
    // 6. Modal dialog with switches; only "저장" commits and updates the saved-settings line.
    modal(root) {
      const dialog = $(root, '.dialog-backdrop'), open = $(root, '.open-dialog'), saved = $(root, '.saved-settings');
      const switches = () => $$(dialog, '[role=switch]');
      open.addEventListener('click', () => { dialog.hidden = false; $(dialog, '[role=switch]').focus(); });
      switches().forEach(s => s.addEventListener('click', () => s.setAttribute('aria-checked', String(s.getAttribute('aria-checked') !== 'true'))));
      $(dialog, '.dialog-cancel').addEventListener('click', () => { dialog.hidden = true; });
      $(dialog, '.dialog-save').addEventListener('click', () => {
        const value = Object.fromEntries(switches().map(s => [s.dataset.key, s.getAttribute('aria-checked') === 'true']));
        saved.textContent = '저장된 설정: ' + switches().map(s => s.textContent + (value[s.dataset.key] ? ' 켜짐' : ' 꺼짐')).join(' · ');
        dialog.hidden = true; report(root.dataset.component, value);
      });
    },
    // 7. Row action menus rendered as a portal at the end of <body>.
    rowmenu(root) {
      const archived = [], deleted = [];
      let menu = null;
      const closeMenu = () => { if (menu) { menu.remove(); menu = null; } };
      $$(root, '.row-menu-button').forEach(button => button.addEventListener('click', () => {
        closeMenu();
        const order = button.dataset.order, rect = button.getBoundingClientRect();
        menu = el('div', {class: 'portal-menu', role: 'menu', 'aria-label': `주문 ${order} 작업`});
        menu.style.top = (rect.bottom + window.scrollY + 4) + 'px'; menu.style.left = (rect.left + window.scrollX - 120) + 'px';
        for (const [label, action] of [['상세 보기', 'view'], ['보관', 'archive'], ['삭제', 'delete']]) {
          const item = el('button', {type: 'button', role: 'menuitem'}, label);
          item.addEventListener('click', () => {
            closeMenu();
            const row = root.querySelector(`tr[data-order="${order}"] .status`);
            if (action === 'archive' && !archived.includes(order)) { archived.push(order); row.textContent = '보관됨'; }
            if (action === 'delete' && !deleted.includes(order)) { deleted.push(order); row.textContent = '삭제됨'; }
            if (action !== 'view') report(root.dataset.component, {archived, deleted});
          });
          menu.append(item);
        }
        document.body.append(menu);
        closeOnOutside(menu, button, closeMenu);
      }));
    },
    // 8. Paginated, sortable, filterable table with row checkboxes.
    table(root) {
      const rows = JSON.parse(root.dataset.rows), body = $(root, 'tbody'), pager = $(root, '.pager'), filter = $(root, '.table-filter');
      const selected = new Set();
      let page = 0, sortKey = null, asc = true;
      const view = () => {
        let list = rows.filter(r => r.name.includes(filter.value.trim()));
        if (sortKey) list = list.slice().sort((a, b) => (a[sortKey] > b[sortKey] ? 1 : -1) * (asc ? 1 : -1));
        return list;
      };
      const render = () => {
        const list = view(), pages = Math.max(1, Math.ceil(list.length / 8));
        page = Math.min(page, pages - 1);
        body.replaceChildren(...list.slice(page * 8, page * 8 + 8).map(r => {
          const tr = el('tr'); const box = el('input', {type: 'checkbox', 'aria-label': r.name + ' 선택'});
          box.checked = selected.has(r.id);
          box.addEventListener('change', () => { box.checked ? selected.add(r.id) : selected.delete(r.id); report(root.dataset.component, [...selected].sort()); });
          const cell = el('td'); cell.append(box); tr.append(cell);
          for (const key of ['name', 'category', 'stock', 'price']) tr.append(el('td', {}, String(r[key])));
          return tr;
        }));
        pager.replaceChildren(...Array.from({length: pages}, (_, i) => {
          const b = el('button', {type: 'button', 'aria-current': i === page ? 'page' : 'false'}, String(i + 1));
          b.addEventListener('click', () => { page = i; render(); }); return b;
        }));
      };
      $$(root, 'th[data-key]').forEach(th => th.addEventListener('click', () => {
        asc = sortKey === th.dataset.key ? !asc : true; sortKey = th.dataset.key; render();
      }));
      filter.addEventListener('input', () => { page = 0; render(); });
      render();
    },
    // 9. Infinite scroll: more items load when the sentinel enters the viewport.
    infinite(root) {
      const list = $(root, 'ul'), sentinel = $(root, '.sentinel'), names = JSON.parse(root.dataset.names);
      let shown = 0, loading = false; const saved = [];
      let more = () => {
        if (loading || shown >= names.length) return; loading = true;
        setTimeout(() => {
          names.slice(shown, shown + 10).forEach(name => {
            const li = el('li', {}, name + ' '); const b = el('button', {type: 'button', 'aria-label': name + ' 저장'}, '저장');
            b.addEventListener('click', () => { if (!saved.includes(name)) { saved.push(name); b.textContent = '저장됨'; report(root.dataset.component, saved); } });
            li.append(b); list.append(li);
          });
          shown += 10; loading = false;
          sentinel.textContent = shown >= names.length ? '모든 항목을 불러왔습니다.' : '불러오는 중…';
        }, 400);
      };
      const observer = new IntersectionObserver(entries => { if (entries.some(e => e.isIntersecting)) more(); });
      observer.observe(sentinel);
      // If the sentinel is still visible after a batch, re-observing fires a fresh intersection event.
      const original = more;
      more = () => { original(); setTimeout(() => { observer.unobserve(sentinel); observer.observe(sentinel); }, 450); };
      more();
    },
    // 10. Web component with an open shadow root.
    shadow(root) {
      if (!customElements.get('newsletter-signup')) {
        customElements.define('newsletter-signup', class extends HTMLElement {
          connectedCallback() {
            const shadow = this.attachShadow({mode: 'open'});
            shadow.innerHTML = '<form><label>이메일 <input name="email" type="email"></label>' +
              '<label><input type="checkbox" name="weekly"> 주간 소식</label>' +
              '<label><input type="checkbox" name="events"> 이벤트 알림</label>' +
              '<button type="submit">구독 신청</button><p class="done" hidden>신청되었습니다.</p></form>';
            const form = shadow.querySelector('form');
            form.addEventListener('submit', e => {
              e.preventDefault();
              report(this.closest('[data-component]').dataset.component,
                {email: form.email.value, weekly: form.weekly.checked, events: form.events.checked});
              shadow.querySelector('.done').hidden = false;
            });
          }
        });
      }
    },
    // 11. Form inside a same-origin iframe (this script also runs in the frame document).
    frameform(root) {
      const form = $(root, 'form');
      form.addEventListener('submit', e => {
        e.preventDefault();
        report(root.dataset.component, {zip: form.zip.value.trim(), detail: form.detail.value.trim()});
        $(root, '.saved').hidden = false;
      });
    },
    // 12. Rich-text editor (contenteditable).
    editor(root) {
      const area = $(root, '[contenteditable]');
      $(root, '.editor-save').addEventListener('click', () => { report(root.dataset.component, area.innerText); $(root, '.saved').hidden = false; });
    },
    // 13. Sortable list: pointer drag on handles, or keyboard (Space to lift, arrows, Space to drop).
    sortable(root) {
      const list = $(root, 'ol'), live = $(root, '.live');
      const order = () => $$(list, 'li').map(li => li.dataset.item);
      const commit = () => report(root.dataset.component, order());
      let lifted = null, dragging = null;
      $$(list, '.handle').forEach(handle => {
        const li = handle.closest('li');
        handle.addEventListener('keydown', e => {
          if (e.key === ' ' || e.key === 'Enter') {
            e.preventDefault();
            if (lifted === li) { lifted = null; li.classList.remove('lifted'); live.textContent = li.dataset.item + ' 놓음'; commit(); }
            else { lifted = li; li.classList.add('lifted'); live.textContent = li.dataset.item + ' 들어올림'; }
          }
          if (lifted === li && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) {
            e.preventDefault();
            const sibling = e.key === 'ArrowUp' ? li.previousElementSibling : li.nextElementSibling;
            if (sibling) { e.key === 'ArrowUp' ? list.insertBefore(li, sibling) : list.insertBefore(sibling, li); handle.focus(); }
          }
        });
        handle.addEventListener('pointerdown', e => { dragging = li; li.classList.add('lifted'); handle.setPointerCapture(e.pointerId); });
        handle.addEventListener('pointermove', e => {
          if (dragging !== li) return;
          const over = document.elementFromPoint(e.clientX, e.clientY)?.closest('li');
          if (over && over !== li && over.parentNode === list) {
            const r = over.getBoundingClientRect();
            list.insertBefore(li, e.clientY < r.top + r.height / 2 ? over : over.nextElementSibling);
          }
        });
        handle.addEventListener('pointerup', () => { if (dragging === li) { dragging = null; li.classList.remove('lifted'); commit(); } });
      });
    },
    // 14. Review filters far below a crowded header: custom dropdowns with radios and a slider.
    reviews(root) {
      const state = {type: 'all', min_hours: 0};
      const chips = $(root, '.filter-chips'), cards = $$(root, '.review-card');
      const labels = {type: {all: null, positive: '긍정적', negative: '부정적'}};
      const apply = silent => {
        chips.replaceChildren();
        if (labels.type[state.type]) chips.append(el('span', {class: 'chip'}, labels.type[state.type]));
        if (state.min_hours) chips.append(el('span', {class: 'chip'}, `플레이타임: ${state.min_hours}시간 이상`));
        cards.forEach(card => { card.hidden = (state.type !== 'all' && card.dataset.type !== state.type) || +card.dataset.hours < state.min_hours; });
        $(root, '.review-count').textContent = `필터와 일치하는 리뷰 ${cards.filter(c => !c.hidden).length}개`;
        if (!silent) report(root.dataset.component, {...state});
      };
      $$(root, '.filter-trigger').forEach(trigger => {
        const panel = $(root, '#' + trigger.getAttribute('aria-controls'));
        trigger.addEventListener('click', () => {
          const open = panel.hidden; $$(root, '.filter-panel').forEach(p => { p.hidden = true; });
          panel.hidden = !open; trigger.setAttribute('aria-expanded', String(open));
          if (open) closeOnOutside(panel, trigger, () => { panel.hidden = true; trigger.setAttribute('aria-expanded', 'false'); });
        });
      });
      $$(root, 'input[name=review-type]').forEach(r => r.addEventListener('change', () => { state.type = r.value; apply(); }));
      const thumb = $(root, '.hours [role=slider]'), out = $(root, '.hours-value');
      const setHours = v => {
        state.min_hours = Math.max(0, Math.min(200, Math.round(v)));
        thumb.setAttribute('aria-valuenow', String(state.min_hours)); out.textContent = state.min_hours + '시간 이상';
        thumb.style.left = (state.min_hours / 200 * 100) + '%';
        $$(root, 'input[name=playtime]').forEach(r => { r.checked = +r.value === state.min_hours; });
        apply();
      };
      $$(root, 'input[name=playtime]').forEach(r => r.addEventListener('change', () => setHours(+r.value)));
      thumb.addEventListener('keydown', e => {
        const moves = {ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1, PageUp: 10, PageDown: -10};
        if (e.key in moves) { setHours(state.min_hours + moves[e.key]); e.preventDefault(); }
      });
      apply(true);
    },
    // 15. Async job whose result code appears only in a short-lived toast.
    toast(root) {
      const start = $(root, '.start-job'), region = document.querySelector('.toast-region');
      start.addEventListener('click', () => {
        start.disabled = true; start.textContent = '생성 중…';
        setTimeout(async () => {
          const {code} = await (await fetch(BASE + '/api/job', {method: 'POST', credentials: 'same-origin'})).json();
          const toast = el('div', {class: 'toast', role: 'status'}, `보고서가 준비되었습니다. 확인 코드: ${code}`);
          region.append(toast); start.textContent = '보고서 생성'; start.disabled = false;
          setTimeout(() => toast.remove(), 6000);
        }, 2500);
      });
      $(root, '.job-submit').addEventListener('click', () => report(root.dataset.component, $(root, '.job-code').value.trim()));
    },
    // 16-20. Multimodal puzzles: answers live only in media; the server checks submissions.
    puzzle(root) {
      const status = $(root, '.puzzle-status');
      const answer = () => {
        const grid = $$(root, '.tile[aria-pressed]');
        if (grid.length) return grid.filter(t => t.getAttribute('aria-pressed') === 'true').map(t => +t.dataset.index);
        const radio = $(root, 'input[type=radio]:checked');
        if ($(root, 'input[type=radio]')) return radio ? radio.value : '';
        return $(root, '.puzzle-answer').value.trim();
      };
      $$(root, '.tile[aria-pressed]').forEach(t => t.addEventListener('click', () => t.setAttribute('aria-pressed', String(t.getAttribute('aria-pressed') !== 'true'))));
      $(root, '.puzzle-submit').addEventListener('click', async () => {
        const result = await report(root.dataset.component, {answer: answer()});
        status.textContent = result.correct ? '확인되었습니다.' : result.locked ? '시도 횟수를 모두 사용했습니다.' : '일치하지 않습니다. 다시 시도하세요.';
        if (result.locked || result.correct) $(root, '.puzzle-submit').disabled = true;
      });
      const handoff = $(root, '.handoff');
      if (handoff) handoff.addEventListener('click', () => { report(root.dataset.component, {handoff: true}); status.textContent = '사용자에게 확인을 요청했습니다.'; });
    },
    // 21. Signup gated by a third-party-style verification that the account owner must complete.
    gate(root) {
      const form = $(root, 'form.signup'), status = $(root, '.gate-status');
      const values = () => ({name: form.name.value, email: form.email.value, terms: form.terms.checked});
      form.addEventListener('input', () => report(root.dataset.component, {form: values()}));
      form.addEventListener('change', () => report(root.dataset.component, {form: values()}));
      $(root, '.verify-submit').addEventListener('click', async () => {
        const result = await report(root.dataset.component, {verify: $(root, '.verify-answer').value.trim()});
        status.textContent = result.correct ? '확인되었습니다.' : '일치하지 않습니다.';
        if (result.correct) $(root, '.signup-submit').disabled = false;
      });
      $(root, '.handoff').addEventListener('click', () => { report(root.dataset.component, {handoff: true, form: values()}); status.textContent = '계정 소유자에게 확인을 요청했습니다.'; });
      form.addEventListener('submit', e => { e.preventDefault(); report(root.dataset.component, {submitted: true, form: values()}); });
    },
    // Crowded layout: cookie banner overlaying the bottom of the viewport.
    cookies(root) {
      $$(root, 'button').forEach(b => b.addEventListener('click', () => { root.hidden = true; report('cookie-banner', b.dataset.choice); }));
    },
  };

  document.querySelectorAll('[data-kind]').forEach(root => {
    const kind = root.dataset.kind;
    try { if (init[kind]) init[kind](root); }
    catch (error) { console.error('gallery component failed to initialise:', kind, error); }
  });
})();
