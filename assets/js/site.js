(function () {
  'use strict';

  var root = document.documentElement;
  var content = document.getElementById('post-content');

  /* ---------- 深浅色切换 ---------- */
  var toggle = document.querySelector('[data-theme-toggle]');
  if (toggle) {
    var syncLabel = function () {
      var isDark = root.getAttribute('data-theme') === 'dark';
      toggle.setAttribute('aria-label', isDark ? '切换到浅色模式' : '切换到深色模式');
      toggle.setAttribute('title', isDark ? '切换到浅色模式' : '切换到深色模式');
    };
    syncLabel();
    toggle.addEventListener('click', function () {
      var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      try {
        localStorage.setItem('theme', next);
      } catch (e) {}
      syncLabel();
    });
  }

  /* ---------- 阅读进度条 ---------- */
  var bar = document.querySelector('.progress i');
  if (bar && content) {
    var updateProgress = function () {
      var rect = content.getBoundingClientRect();
      var total = rect.height - window.innerHeight;
      var scrolled = -rect.top;
      var ratio = total > 0 ? Math.min(1, Math.max(0, scrolled / total)) : 0;
      bar.style.width = (ratio * 100).toFixed(2) + '%';
    };
    window.addEventListener('scroll', updateProgress, { passive: true });
    window.addEventListener('resize', updateProgress);
    updateProgress();
  }

  /* ---------- 表格包一层横向滚动容器 ---------- */
  if (content) {
    Array.prototype.forEach.call(content.querySelectorAll('table'), function (table) {
      var parent = table.parentElement;
      if (parent && parent.classList.contains('table-wrap')) return;
      var wrap = document.createElement('div');
      wrap.className = 'table-wrap';
      parent.insertBefore(wrap, table);
      wrap.appendChild(table);
    });
  }

  /* ---------- 生成目录 + 滚动高亮 ---------- */
  var tocNav = document.getElementById('toc-nav');
  if (tocNav && content) {
    var heads = content.querySelectorAll('h2, h3');
    if (heads.length) {
      var list = document.createElement('ol');
      var map = {};

      Array.prototype.forEach.call(heads, function (head, index) {
        if (!head.id) {
          head.id = 'sec-' + (index + 1);
        }
        var li = document.createElement('li');
        li.className = 'toc-l' + head.tagName.charAt(1);

        var link = document.createElement('a');
        link.href = '#' + head.id;
        link.textContent = head.textContent.trim();
        li.appendChild(link);
        list.appendChild(li);

        map[head.id] = link;
      });

      tocNav.appendChild(list);

      if ('IntersectionObserver' in window) {
        var active = null;
        var observer = new IntersectionObserver(
          function (entries) {
            entries.forEach(function (entry) {
              if (!entry.isIntersecting) return;
              if (active) active.classList.remove('is-active');
              active = map[entry.target.id] || null;
              if (active) active.classList.add('is-active');
            });
          },
          { rootMargin: '-88px 0px -68% 0px', threshold: 0 }
        );
        Array.prototype.forEach.call(heads, function (head) {
          observer.observe(head);
        });
      }
    }
  }

  /* ---------- 代码块复制 ---------- */
  if (content) {
    Array.prototype.forEach.call(content.querySelectorAll('pre'), function (pre) {
      var button = document.createElement('button');
      button.type = 'button';
      button.className = 'copy-btn';
      button.textContent = '复制';
      button.addEventListener('click', function () {
        var code = pre.querySelector('code');
        var text = code ? code.innerText : pre.innerText;
        if (!navigator.clipboard) return;
        navigator.clipboard.writeText(text).then(function () {
          button.textContent = '已复制';
          window.setTimeout(function () {
            button.textContent = '复制';
          }, 1600);
        });
      });
      pre.appendChild(button);
    });
  }

  /* ---------- 正文外链新窗口打开 ---------- */
  Array.prototype.forEach.call(
    document.querySelectorAll('.post-content a[href^="http"]'),
    function (link) {
      if (link.hostname && link.hostname !== window.location.hostname) {
        link.setAttribute('target', '_blank');
        link.setAttribute('rel', 'noopener noreferrer');
      }
    }
  );
})();
