// Financial RAG Documentation Script
(function() {
  // 1. Theme Management
  const THEME_KEY = 'f_rag_theme';
  
  function getPreferredTheme() {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored) return stored;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(THEME_KEY, theme);
    const themeBtn = document.getElementById('theme-toggle');
    if (themeBtn) {
      themeBtn.innerHTML = theme === 'dark' ? '☀️ ライト' : '🌙 ダーク';
    }
  }

  // Initialize theme
  const currentTheme = getPreferredTheme();
  applyTheme(currentTheme);

  document.addEventListener('DOMContentLoaded', () => {
    const themeBtn = document.getElementById('theme-toggle');
    if (themeBtn) {
      themeBtn.addEventListener('click', () => {
        const nextTheme = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
        applyTheme(nextTheme);
      });
    }

    // 2. Code Block Copy Buttons
    document.querySelectorAll('pre code').forEach((codeBlock) => {
      const pre = codeBlock.parentElement;
      if (!pre.querySelector('.copy-btn')) {
        const btn = document.createElement('button');
        btn.className = 'copy-btn';
        btn.textContent = 'コピー';
        btn.style.position = 'absolute';
        btn.style.top = '10px';
        btn.style.right = '12px';
        
        btn.addEventListener('click', async () => {
          try {
            await navigator.clipboard.writeText(codeBlock.innerText);
            btn.textContent = '完了!';
            btn.style.borderColor = '#10b981';
            btn.style.color = '#10b981';
            setTimeout(() => {
              btn.textContent = 'コピー';
              btn.style.borderColor = '';
              btn.style.color = '';
            }, 2000);
          } catch (err) {
            console.error('Copy failed:', err);
          }
        });
        pre.appendChild(btn);
      }
    });

    // 3. Smooth Anchor Scrolling with Header Offset
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
      anchor.addEventListener('click', function(e) {
        const targetId = this.getAttribute('href').substring(1);
        if (!targetId) return;
        const targetEl = document.getElementById(targetId);
        if (targetEl) {
          e.preventDefault();
          const headerOffset = 80;
          const elementPosition = targetEl.getBoundingClientRect().top;
          const offsetPosition = elementPosition + window.pageYOffset - headerOffset;
          window.scrollTo({
            top: offsetPosition,
            behavior: 'smooth'
          });
          history.pushState(null, null, '#' + targetId);
        }
      });
    });

    // 4. Initialize Mermaid if present
    if (window.mermaid) {
      mermaid.initialize({
        startOnLoad: true,
        theme: currentTheme === 'dark' ? 'dark' : 'default',
        securityLevel: 'loose',
        fontFamily: 'Inter, -apple-system, sans-serif'
      });
    }
  });
})();
