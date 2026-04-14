/**
 * Interactions & Animations: The Digital Jurist
 * Enhanced user interactions, form validation, loading states
 */

(function() {
  'use strict';

  // ========================================
  // FORM VALIDATION
  // ========================================

  const FormValidator = {
    init(form) {
      if (!form) return;

      const inputs = form.querySelectorAll('input[required], select[required], textarea[required]');

      inputs.forEach(input => {
        // Validate on blur
        input.addEventListener('blur', () => this.validateField(input));

        // Clear error on input
        input.addEventListener('input', () => this.clearError(input));
      });

      // Form submission
      form.addEventListener('submit', (e) => {
        if (!this.validateForm(form)) {
          e.preventDefault();
          e.stopPropagation();

          // Focus first error
          const firstError = form.querySelector('.has-error input, .has-error select, .has-error textarea');
          if (firstError) {
            firstError.focus();
            firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
          }
        }
      });
    },

    validateField(field) {
      const formGroup = field.closest('.form-group');
      if (!formGroup) return true;

      const value = field.value.trim();
      let isValid = true;
      let errorMessage = '';

      // Required check
      if (field.required && !value) {
        isValid = false;
        errorMessage = '此项为必填项';
      }

      // Email validation
      if (isValid && field.type === 'email' && value) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(value)) {
          isValid = false;
          errorMessage = '请输入有效的邮箱地址';
        }
      }

      // Number validation
      if (isValid && field.type === 'number' && value) {
        const num = parseFloat(value);
        const min = parseFloat(field.min);
        const max = parseFloat(field.max);

        if (isNaN(num)) {
          isValid = false;
          errorMessage = '请输入有效的数字';
        } else if (!isNaN(min) && num < min) {
          isValid = false;
          errorMessage = `最小值为 ${min}`;
        } else if (!isNaN(max) && num > max) {
          isValid = false;
          errorMessage = `最大值为 ${max}`;
        }
      }

      // Custom pattern validation
      if (isValid && field.pattern && value) {
        const pattern = new RegExp(field.pattern);
        if (!pattern.test(value)) {
          isValid = false;
          errorMessage = field.dataset.errorMessage || '格式不正确';
        }
      }

      // Update UI
      if (!isValid) {
        this.showError(field, errorMessage);
      } else {
        this.clearError(field);
      }

      return isValid;
    },

    validateForm(form) {
      const inputs = form.querySelectorAll('input[required], select[required], textarea[required]');
      let isValid = true;

      inputs.forEach(input => {
        if (!this.validateField(input)) {
          isValid = false;
        }
      });

      return isValid;
    },

    showError(field, message) {
      const formGroup = field.closest('.form-group');
      if (!formGroup) return;

      formGroup.classList.add('has-error');

      // Remove existing error
      let errorEl = formGroup.querySelector('.form-error');
      if (!errorEl) {
        errorEl = document.createElement('span');
        errorEl.className = 'form-error';
        formGroup.appendChild(errorEl);
      }

      errorEl.textContent = message;

      // Add shake animation
      formGroup.classList.add('shake');
      setTimeout(() => formGroup.classList.remove('shake'), 500);
    },

    clearError(field) {
      const formGroup = field.closest('.form-group');
      if (!formGroup) return;

      formGroup.classList.remove('has-error');

      const errorEl = formGroup.querySelector('.form-error');
      if (errorEl) {
        errorEl.remove();
      }
    }
  };

  // Initialize validation on all forms
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('form').forEach(form => {
      FormValidator.init(form);
    });
  });

  // ========================================
  // PAGE LOADING STATE
  // ========================================

  window.PageLoader = {
    show(message = '加载中...') {
      // Remove existing loader
      this.hide();

      const loader = document.createElement('div');
      loader.id = 'page-loader';
      loader.className = 'page-loader';
      loader.innerHTML = `
        <div class="page-loader-content">
          <span class="material-symbols-outlined spinning">sync</span>
          <p class="page-loader-message">${message}</p>
        </div>
      `;

      document.body.appendChild(loader);
      document.body.style.overflow = 'hidden';
    },

    hide() {
      const loader = document.getElementById('page-loader');
      if (loader) {
        loader.classList.add('page-loader-hiding');
        setTimeout(() => {
          loader.remove();
          document.body.style.overflow = '';
        }, 300);
      }
    },

    // Show skeleton loading for specific container
    showSkeleton(container, type = 'card') {
      if (!container) return;

      container.dataset.originalContent = container.innerHTML;
      container.innerHTML = this.getSkeletonHTML(type);
      container.classList.add('skeleton-loading');
    },

    hideSkeleton(container) {
      if (!container || !container.dataset.originalContent) return;

      container.innerHTML = container.dataset.originalContent;
      container.classList.remove('skeleton-loading');
      delete container.dataset.originalContent;
    },

    getSkeletonHTML(type) {
      const skeletons = {
        card: `
          <div class="skeleton-card">
            <div class="skeleton-header">
              <div class="skeleton-avatar"></div>
              <div class="skeleton-title"></div>
            </div>
            <div class="skeleton-body">
              <div class="skeleton-text">
                <div class="skeleton-line"></div>
                <div class="skeleton-line"></div>
                <div class="skeleton-line"></div>
              </div>
            </div>
          </div>
        `,
        table: `
          <div class="skeleton-table">
            <div class="skeleton-table-header">
              <div class="skeleton-table-cell"></div>
              <div class="skeleton-table-cell"></div>
              <div class="skeleton-table-cell"></div>
              <div class="skeleton-table-cell"></div>
            </div>
            ${Array(5).fill(0).map(() => `
              <div class="skeleton-table-row">
                <div class="skeleton-table-cell"></div>
                <div class="skeleton-table-cell"></div>
                <div class="skeleton-table-cell"></div>
                <div class="skeleton-table-cell"></div>
              </div>
            `).join('')}
          </div>
        `,
        stat: `
          <div class="skeleton-stat-card">
            <div class="skeleton-stat-header">
              <div class="skeleton-stat-label"></div>
              <div class="skeleton-stat-icon"></div>
            </div>
            <div class="skeleton-stat-value"></div>
            <div class="skeleton-stat-footer"></div>
          </div>
        `
      };

      return skeletons[type] || skeletons.card;
    }
  };

  // ========================================
  // SMOOTH SCROLLING
  // ========================================

  document.addEventListener('DOMContentLoaded', () => {
    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
      anchor.addEventListener('click', function(e) {
        const targetId = this.getAttribute('href');
        if (targetId === '#') return;

        const target = document.querySelector(targetId);
        if (target) {
          e.preventDefault();
          target.scrollIntoView({
            behavior: 'smooth',
            block: 'start'
          });
        }
      });
    });
  });

  // ========================================
  // INTERSECTION OBSERVER FOR ANIMATIONS
  // ========================================

  const AnimationObserver = {
    init() {
      const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.classList.add('animate-in');
            observer.unobserve(entry.target);
          }
        });
      }, {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
      });

      document.querySelectorAll('.animate-on-scroll').forEach(el => {
        observer.observe(el);
      });
    }
  };

  document.addEventListener('DOMContentLoaded', () => {
    AnimationObserver.init();
  });

  // ========================================
  // KEYBOARD SHORTCUTS
  // ========================================

  document.addEventListener('keydown', (e) => {
    // Skip if in input
    if (e.target.matches('input, textarea, select')) return;

    // Ctrl/Cmd + K - Focus search
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      const searchInput = document.querySelector('.search-input');
      if (searchInput) {
        searchInput.focus();
      }
    }

    // Escape - Close modals and dropdowns
    if (e.key === 'Escape') {
      // Close active modal
      const activeModal = document.querySelector('.modal.active');
      if (activeModal) {
        closeModal(activeModal.id);
      }

      // Close active dropdowns
      document.querySelectorAll('.dropdown.active').forEach(d => {
        d.classList.remove('active');
      });
    }
  });

  // ========================================
  // COPY TO CLIPBOARD
  // ========================================

  window.copyToClipboard = function(text, successMessage = '已复制到剪贴板') {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(() => {
        showToast(successMessage, 'success');
      }).catch(() => {
        showToast('复制失败', 'error');
      });
    } else {
      // Fallback
      const textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();

      try {
        document.execCommand('copy');
        showToast(successMessage, 'success');
      } catch (err) {
        showToast('复制失败', 'error');
      }

      document.body.removeChild(textarea);
    }
  };

  // ========================================
  // LAZY LOADING IMAGES
  // ========================================

  document.addEventListener('DOMContentLoaded', () => {
    if ('IntersectionObserver' in window) {
      const imageObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            const img = entry.target;
            img.src = img.dataset.src;
            img.classList.remove('lazy-image');
            imageObserver.unobserve(img);
          }
        });
      });

      document.querySelectorAll('img[data-src]').forEach(img => {
        imageObserver.observe(img);
      });
    }
  });

  // ========================================
  // AUTO-REFRESH FUNCTIONALITY
  // ========================================

  window.AutoRefresh = {
    interval: null,

    start(callback, seconds = 30) {
      this.stop();
      this.interval = setInterval(callback, seconds * 1000);
    },

    stop() {
      if (this.interval) {
        clearInterval(this.interval);
        this.interval = null;
      }
    }
  };

  // ========================================
  // NOTIFICATION HELPERS
  // ========================================

  window.fetchUnreadCount = async function() {
    try {
      const response = await fetch('/notifications/api/unread-count');
      if (!response.ok) return 0;
      const data = await response.json();
      return data.unread_count || 0;
    } catch (err) {
      return 0;
    }
  };

  window.updateNotificationBadge = async function() {
    const badge = document.getElementById('notification-badge');
    if (!badge) return;
    const count = await fetchUnreadCount();
    if (count > 0) {
      badge.textContent = count > 99 ? '99+' : count;
      badge.classList.remove('hidden');
    } else {
      badge.classList.add('hidden');
    }
  };

  window.refreshNotifications = async function() {
    if (typeof loadNotifications === 'function') {
      await loadNotifications();
    }
    await updateNotificationBadge();
  };

  // ========================================
  // PRINT FUNCTIONALITY
  // ========================================

  window.printPage = function() {
    window.print();
  };

  // ========================================
  // DARK MODE TOGGLE
  // ========================================

  window.toggleDarkMode = function() {
    const html = document.documentElement;
    const currentTheme = html.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

    html.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
  };

  // Restore theme on load
  document.addEventListener('DOMContentLoaded', () => {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
      document.documentElement.setAttribute('data-theme', savedTheme);
    }
  });

})();
