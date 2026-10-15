/**
 * Flock Documentation - Custom JavaScript Enhancements
 * State-of-the-art interactive features for superior UX
 */

(function() {
  'use strict';

  // ============================================
  // READING PROGRESS BAR
  // ============================================

  function initReadingProgress() {
    // Create progress bar element
    const progressBar = document.createElement('div');
    progressBar.className = 'reading-progress-bar';
    progressBar.setAttribute('role', 'progressbar');
    progressBar.setAttribute('aria-label', 'Reading progress');
    document.body.appendChild(progressBar);

    // Update progress on scroll
    function updateProgress() {
      const windowHeight = window.innerHeight;
      const documentHeight = document.documentElement.scrollHeight - windowHeight;
      const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
      const progress = (scrollTop / documentHeight) * 100;

      progressBar.style.width = `${Math.min(progress, 100)}%`;
      progressBar.setAttribute('aria-valuenow', Math.round(progress));
    }

    // Throttled scroll handler for performance
    let ticking = false;
    window.addEventListener('scroll', () => {
      if (!ticking) {
        window.requestAnimationFrame(() => {
          updateProgress();
          ticking = false;
        });
        ticking = true;
      }
    });

    // Initial update
    updateProgress();
  }

  // ============================================
  // SMOOTH SCROLL TO ANCHOR ENHANCEMENT
  // ============================================

  function initSmoothScrollEnhancements() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
      anchor.addEventListener('click', function(e) {
        const href = this.getAttribute('href');

        // Skip if it's just "#"
        if (href === '#') return;

        const target = document.querySelector(href);
        if (target) {
          e.preventDefault();

          // Smooth scroll with offset for fixed header
          const headerOffset = 80;
          const elementPosition = target.getBoundingClientRect().top;
          const offsetPosition = elementPosition + window.pageYOffset - headerOffset;

          window.scrollTo({
            top: offsetPosition,
            behavior: 'smooth'
          });

          // Update URL without jumping
          if (history.pushState) {
            history.pushState(null, null, href);
          }

          // Focus management for accessibility
          target.setAttribute('tabindex', '-1');
          target.focus();
        }
      });
    });
  }

  // ============================================
  // COPY CODE BUTTON ENHANCEMENT
  // ============================================

  function enhanceCopyButtons() {
    document.querySelectorAll('.md-clipboard').forEach(button => {
      const originalTitle = button.getAttribute('title') || 'Copy to clipboard';

      button.addEventListener('click', () => {
        // Visual feedback
        button.style.transform = 'scale(0.9)';
        setTimeout(() => {
          button.style.transform = 'scale(1.1)';
        }, 100);

        // Update button text temporarily
        const icon = button.querySelector('svg');
        if (icon) {
          const checkIcon = `
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
              <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
            </svg>
          `;

          const originalIcon = icon.outerHTML;
          icon.outerHTML = checkIcon;
          button.setAttribute('title', 'Copied!');

          setTimeout(() => {
            button.querySelector('svg').outerHTML = originalIcon;
            button.setAttribute('title', originalTitle);
          }, 2000);
        }
      });
    });
  }

  // ============================================
  // TABLE OF CONTENTS ACTIVE HIGHLIGHTING
  // ============================================

  function initTOCHighlighting() {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach(entry => {
          const id = entry.target.getAttribute('id');
          if (id) {
            const tocLink = document.querySelector(`.md-nav__link[href="#${id}"]`);
            if (tocLink) {
              if (entry.isIntersecting) {
                // Remove active class from all links
                document.querySelectorAll('.md-nav__link--active-toc').forEach(link => {
                  link.classList.remove('md-nav__link--active-toc');
                });
                // Add active class to current link
                tocLink.classList.add('md-nav__link--active-toc');
              }
            }
          }
        });
      },
      {
        rootMargin: '-80px 0px -80% 0px',
        threshold: 0
      }
    );

    // Observe all headings
    document.querySelectorAll('h1[id], h2[id], h3[id], h4[id]').forEach(heading => {
      observer.observe(heading);
    });
  }

  // ============================================
  // KEYBOARD SHORTCUTS ENHANCEMENTS
  // ============================================

  function initKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
      // Skip if user is typing in an input
      if (e.target.matches('input, textarea, select')) return;

      // "/" - Focus search
      if (e.key === '/' && !e.ctrlKey && !e.metaKey && !e.altKey) {
        e.preventDefault();
        const searchInput = document.querySelector('.md-search__input');
        if (searchInput) {
          searchInput.focus();
        }
      }

      // "Escape" - Close search/modals
      if (e.key === 'Escape') {
        const searchInput = document.querySelector('.md-search__input');
        if (searchInput && document.activeElement === searchInput) {
          searchInput.blur();
          searchInput.value = '';
        }
      }

      // "t" - Back to top
      if (e.key === 't' && !e.ctrlKey && !e.metaKey && !e.altKey) {
        e.preventDefault();
        window.scrollTo({
          top: 0,
          behavior: 'smooth'
        });
      }
    });

    // Add keyboard shortcut hint to search
    const searchLabel = document.querySelector('.md-search__input');
    if (searchLabel) {
      const originalPlaceholder = searchLabel.getAttribute('placeholder') || 'Search';
      searchLabel.setAttribute('placeholder', `${originalPlaceholder} (Press "/" to focus)`);
    }
  }

  // ============================================
  // CODE BLOCK LINE NUMBERS TOGGLE
  // ============================================

  function initCodeBlockEnhancements() {
    document.querySelectorAll('.highlight').forEach(codeBlock => {
      // Add language badge if data-lang attribute exists
      const lang = codeBlock.querySelector('code')?.getAttribute('data-lang');
      if (lang && lang !== 'text') {
        const badge = document.createElement('span');
        badge.className = 'code-lang-badge';
        badge.textContent = lang;
        badge.style.cssText = `
          position: absolute;
          top: 0.5rem;
          right: 3rem;
          padding: 0.25rem 0.5rem;
          background: rgba(0, 0, 0, 0.3);
          color: white;
          font-size: 0.75rem;
          border-radius: 4px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          z-index: 1;
        `;
        codeBlock.style.position = 'relative';
        codeBlock.appendChild(badge);
      }
    });
  }

  // ============================================
  // EXTERNAL LINK INDICATORS
  // ============================================

  function initExternalLinkIndicators() {
    document.querySelectorAll('a[href^="http"]').forEach(link => {
      // Skip if it's a link to the same domain or GitHub repo links
      if (link.hostname === window.location.hostname ||
          link.href.includes('github.com/whiteducksoftware/flock')) {
        return;
      }

      // Add external link icon
      if (!link.querySelector('svg')) {
        link.setAttribute('target', '_blank');
        link.setAttribute('rel', 'noopener noreferrer');
        link.setAttribute('title', `${link.textContent} (opens in new tab)`);

        // Add subtle icon
        const icon = document.createElement('span');
        icon.innerHTML = ' ↗';
        icon.style.cssText = 'font-size: 0.75em; opacity: 0.6; margin-left: 0.2em;';
        link.appendChild(icon);
      }
    });
  }

  // ============================================
  // SEARCH RESULT HIGHLIGHTING
  // ============================================

  function initSearchEnhancements() {
    // Observe search results being added
    const searchObserver = new MutationObserver(() => {
      const searchResults = document.querySelectorAll('.md-search-result__item');
      searchResults.forEach((result, index) => {
        // Stagger animation for search results
        result.style.animation = `fadeInUp 0.3s ease-out ${index * 0.05}s both`;
      });
    });

    const searchResultContainer = document.querySelector('.md-search-result__list');
    if (searchResultContainer) {
      searchObserver.observe(searchResultContainer, {
        childList: true,
        subtree: true
      });
    }
  }

  // ============================================
  // IMPROVED BACK TO TOP BUTTON
  // ============================================

  function enhanceBackToTop() {
    const backToTop = document.querySelector('.md-top');
    if (backToTop) {
      // Hide initially
      backToTop.style.opacity = '0';
      backToTop.style.pointerEvents = 'none';

      window.addEventListener('scroll', () => {
        if (window.pageYOffset > 300) {
          backToTop.style.opacity = '1';
          backToTop.style.pointerEvents = 'auto';
        } else {
          backToTop.style.opacity = '0';
          backToTop.style.pointerEvents = 'none';
        }
      });
    }
  }

  // ============================================
  // PERFORMANCE MONITORING (DEV ONLY)
  // ============================================

  function logPerformanceMetrics() {
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
      window.addEventListener('load', () => {
        setTimeout(() => {
          const perfData = window.performance.timing;
          const pageLoadTime = perfData.loadEventEnd - perfData.navigationStart;
          const connectTime = perfData.responseEnd - perfData.requestStart;
          const renderTime = perfData.domComplete - perfData.domLoading;

          console.log('%c📊 Flock Docs Performance Metrics', 'font-size: 14px; font-weight: bold; color: #4f46e5;');
          console.log(`⚡ Total Page Load: ${pageLoadTime}ms`);
          console.log(`🔗 Server Connect: ${connectTime}ms`);
          console.log(`🎨 DOM Render: ${renderTime}ms`);
        }, 0);
      });
    }
  }

  // ============================================
  // INITIALIZATION
  // ============================================

  function init() {
    // Wait for DOM to be ready
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', init);
      return;
    }

    // Initialize all features
    try {
      initReadingProgress();
      initSmoothScrollEnhancements();
      enhanceCopyButtons();
      initTOCHighlighting();
      initKeyboardShortcuts();
      initCodeBlockEnhancements();
      initExternalLinkIndicators();
      initSearchEnhancements();
      enhanceBackToTop();
      logPerformanceMetrics();

      console.log('%c✨ Flock Docs Enhanced!', 'font-size: 12px; color: #10b981; font-weight: bold;');
    } catch (error) {
      console.error('Error initializing Flock docs enhancements:', error);
    }
  }

  // Start initialization
  init();

  // Re-initialize on navigation (for SPAs)
  if (window.app && window.app.document$) {
    window.app.document$.subscribe(() => {
      setTimeout(() => {
        enhanceCopyButtons();
        initCodeBlockEnhancements();
        initExternalLinkIndicators();
        initTOCHighlighting();
      }, 100);
    });
  }

})();
