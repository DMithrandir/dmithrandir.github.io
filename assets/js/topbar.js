/* ==========================================================================
   灰度 · 统一顶栏行为（子页面侧）
   与首页 assets/b/system.js 的 nav() 同源抽取：手机抽屉开合、下拉展开按钮、
   Escape/点击链接收起、回到桌面宽度自动收起。改首页 nav() 时同步本文件。
   ========================================================================== */
(function () {
  'use strict';

  function nav() {
    var nav = document.querySelector('header.nav');
    if (!nav) return;
    var toggle = nav.querySelector('.nav__toggle');
    var bars = '<svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><path d="M2 5h14M2 13h14" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>';
    var cross = '<svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><path d="M4 4l10 10M14 4L4 14" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>';
    var setOpen = function (open) {
      nav.classList.toggle('is-open', open);
      document.body.classList.toggle('nav-locked', open);
      if (toggle) { toggle.setAttribute('aria-expanded', String(open)); toggle.innerHTML = open ? cross : bars; }
    };
    if (toggle) toggle.addEventListener('click', function () { setOpen(!nav.classList.contains('is-open')); });
    nav.querySelectorAll('.nav__item').forEach(function (item) {
      if (!item.querySelector('.nav__menu')) return;
      var btn = item.querySelector('.nav__expand');
      if (!btn) {
        btn = document.createElement('button');
        btn.className = 'nav__expand';
        btn.type = 'button';
        btn.innerHTML = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
        item.querySelector('.nav__link').after(btn);
      }
      var label = (item.querySelector('.nav__link') || {}).textContent;
      label = label ? label.trim() : 'section';
      btn.setAttribute('aria-label', 'Show ' + label + ' links');
      btn.setAttribute('aria-expanded', 'false');
      btn.addEventListener('click', function () {
        var open = !item.classList.contains('is-expanded');
        item.classList.toggle('is-expanded', open);
        btn.setAttribute('aria-expanded', String(open));
      });
    });
    document.addEventListener('keydown', function (e) {
      if (e.key !== 'Escape') return;
      if (nav.classList.contains('is-open')) { setOpen(false); if (toggle) toggle.focus(); return; }
      if (nav.contains(document.activeElement)) document.activeElement.blur();
    });
    // 抽屉里点任何链接都收起，页面不会留在抽屉底下
    nav.addEventListener('click', function (e) {
      if (nav.classList.contains('is-open') && e.target.closest && e.target.closest('a[href]')) setOpen(false);
    });
    window.matchMedia('(min-width: 1024px)').addEventListener('change', function (e) { if (e.matches) setOpen(false); });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', nav);
  else nav();
})();
