/* AI 素養教育工作坊 — 課堂筆記
   相簿產生、燈箱、行動清單勾選狀態 */

(function () {
  'use strict';

  /* ── 投影片相簿 ─────────────────────── */

  /* 4730 / 4739 / 4740 未收錄——涉及講者未成年子女的手寫反思與私人談話 */
  var SLIDES = [
    4671, 4672, 4673, 4674, 4678, 4679, 4680, 4681, 4682, 4683,
    4684, 4686, 4688, 4689, 4690, 4691, 4693, 4695, 4698, 4699,
    4700, 4701, 4702, 4703, 4704, 4705, 4706, 4707, 4710, 4711,
    4713, 4715, 4716, 4717, 4721, 4722, 4723, 4724, 4725, 4726,
    4727, 4728, 4733, 4736, 4737, 4741, 4744, 4748, 4752
  ];

  var gallery = document.getElementById('gallery');
  if (gallery) {
    var frag = document.createDocumentFragment();
    SLIDES.forEach(function (n, i) {
      var src = 'img/slides/IMG_' + n + '.jpg';
      var fig = document.createElement('figure');
      fig.className = 'thumb';

      var img = document.createElement('img');
      img.src = src;
      img.loading = 'lazy';
      img.alt = '第 ' + (i + 1) + ' 張投影片';

      var cap = document.createElement('figcaption');
      cap.textContent = i + 1;

      fig.appendChild(img);
      fig.appendChild(cap);
      fig.addEventListener('click', function () { openBox(i); });
      frag.appendChild(fig);
    });
    gallery.appendChild(frag);
  }

  /* ── 燈箱 ───────────────────────────── */

  var box = null;
  var boxImg = null;
  var boxNum = null;
  var current = 0;

  function buildBox() {
    box = document.createElement('div');
    box.className = 'lightbox';
    box.hidden = true;
    box.innerHTML =
      '<button class="lb-close" aria-label="關閉">×</button>' +
      '<button class="lb-prev" aria-label="上一張">‹</button>' +
      '<img alt="">' +
      '<button class="lb-next" aria-label="下一張">›</button>' +
      '<span class="lb-num"></span>';
    document.body.appendChild(box);

    boxImg = box.querySelector('img');
    boxNum = box.querySelector('.lb-num');

    box.querySelector('.lb-close').addEventListener('click', closeBox);
    box.querySelector('.lb-prev').addEventListener('click', function (e) {
      e.stopPropagation(); step(-1);
    });
    box.querySelector('.lb-next').addEventListener('click', function (e) {
      e.stopPropagation(); step(1);
    });
    box.addEventListener('click', function (e) {
      if (e.target === box) closeBox();
    });
  }

  function openBox(i) {
    if (!box) buildBox();
    current = i;
    render();
    box.hidden = false;
    document.body.style.overflow = 'hidden';
  }

  function closeBox() {
    box.hidden = true;
    document.body.style.overflow = '';
  }

  function step(d) {
    current = (current + d + SLIDES.length) % SLIDES.length;
    render();
  }

  function render() {
    boxImg.src = 'img/slides/IMG_' + SLIDES[current] + '.jpg';
    boxImg.alt = '第 ' + (current + 1) + ' 張投影片';
    boxNum.textContent = (current + 1) + ' / ' + SLIDES.length;
  }

  document.addEventListener('keydown', function (e) {
    if (!box || box.hidden) return;
    if (e.key === 'Escape') closeBox();
    else if (e.key === 'ArrowLeft') step(-1);
    else if (e.key === 'ArrowRight') step(1);
  });

  /* ── 行動清單狀態 ───────────────────── */

  var KEY = 'ai-notes-todo';
  var saved = {};
  try { saved = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) {}

  var boxes = document.querySelectorAll('.todo input[type=checkbox]');
  Array.prototype.forEach.call(boxes, function (cb) {
    var k = cb.getAttribute('data-k');
    if (saved[k]) cb.checked = true;
    cb.addEventListener('change', function () {
      saved[k] = cb.checked;
      try { localStorage.setItem(KEY, JSON.stringify(saved)); } catch (e) {}
    });
  });
})();
