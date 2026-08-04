/* 訪問計數器 — Supabase
   與其他站共用同一個專案，以 COUNTER_ID 區分。
   anon key 設計上就是公開的；安全性由資料庫端的 RLS 與
   security definer 函式保證，詳見個人網站 repo 的說明。 */

const SUPABASE_URL  = 'https://ciptftupkllmwwnrqmkt.supabase.co';
const SUPABASE_ANON = 'sb_publishable_wlrk7HnxRKzo2bhSsRgbEQ_U4KzaFZz';
const COUNTER_ID    = 'ai-notes';

(function () {
  'use strict';

  const box = document.getElementById('counter');
  const el  = document.getElementById('view-count');
  if (!box || !el) return;

  let counted = false;
  try { counted = sessionStorage.getItem('al-counted') === '1'; } catch (e) {}

  const fn = counted ? 'get_counter' : 'increment_counter';

  fetch(SUPABASE_URL + '/rest/v1/rpc/' + fn, {
    method: 'POST',
    headers: {
      'apikey': SUPABASE_ANON,
      'Authorization': 'Bearer ' + SUPABASE_ANON,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ counter_id: COUNTER_ID })
  })
    .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(function (n) {
      if (typeof n !== 'number') throw new Error('unexpected payload');
      try { sessionStorage.setItem('al-counted', '1'); } catch (e) {}
      el.textContent = n.toLocaleString('zh-TW');
      box.hidden = false;
    })
    .catch(function () { box.hidden = true; });
})();