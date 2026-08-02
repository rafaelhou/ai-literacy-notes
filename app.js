/* AI 素養教育工作坊 — 課堂筆記
   行動清單勾選狀態（存於瀏覽器 localStorage） */

(function () {
  'use strict';

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
