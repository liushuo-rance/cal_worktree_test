/**
 * Component Interactions: The Digital Jurist
 * Modal, Dropdown, Tabs, and other interactive components
 */

(function() {
  'use strict';

  // ========================================
  // MODAL
  // ========================================

  window.openModal = function(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;

    modal.classList.add('active');
    document.body.style.overflow = 'hidden';

    // Focus first focusable element
    const focusable = modal.querySelector('input, button, select, textarea, [href]');
    if (focusable) focusable.focus();

    // Close on Escape key
    const escapeHandler = function(e) {
      if (e.key === 'Escape') {
        closeModal(modalId);
        document.removeEventListener('keydown', escapeHandler);
      }
    };
    modal.dataset.escapeHandler = escapeHandler;
    document.addEventListener('keydown', escapeHandler);
  };

  window.closeModal = function(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) return;

    modal.classList.remove('active');
    document.body.style.overflow = '';

    // Remove escape handler
    const escapeHandler = modal.dataset.escapeHandler;
    if (escapeHandler) {
      document.removeEventListener('keydown', escapeHandler);
      delete modal.dataset.escapeHandler;
    }
  };

  // Initialize modal triggers
  document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('[data-modal]').forEach(trigger => {
      trigger.addEventListener('click', function() {
        const modalId = this.dataset.modal;
        openModal(modalId);
      });
    });
  });

  // ========================================
  // DROPDOWN
  // ========================================

  document.addEventListener('DOMContentLoaded', function() {
    const dropdowns = document.querySelectorAll('.dropdown');

    dropdowns.forEach(dropdown => {
      const toggle = dropdown.querySelector('.dropdown-toggle');

      if (toggle) {
        toggle.addEventListener('click', function(e) {
          e.stopPropagation();

          // Close other dropdowns
          dropdowns.forEach(d => {
            if (d !== dropdown) d.classList.remove('active');
          });

          dropdown.classList.toggle('active');
        });
      }
    });

    // Close dropdowns on outside click
    document.addEventListener('click', function() {
      dropdowns.forEach(dropdown => {
        dropdown.classList.remove('active');
      });
    });
  });

  // ========================================
  // TABS
  // ========================================

  window.initTabs = function(container) {
    const tabs = container.querySelectorAll('.tab');
    const contents = container.querySelectorAll('.tab-content');

    tabs.forEach(tab => {
      tab.addEventListener('click', function() {
        const target = this.dataset.tab;

        // Update tabs
        tabs.forEach(t => t.classList.remove('active'));
        this.classList.add('active');

        // Update content
        contents.forEach(c => {
          c.classList.toggle('active', c.id === target);
        });
      });
    });
  };

  document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.tabs-container').forEach(container => {
      initTabs(container);
    });
  });

  // ========================================
  // TOOLTIP
  // ========================================

  document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('[data-tooltip]').forEach(el => {
      const tooltip = document.createElement('div');
      tooltip.className = 'tooltip-content';
      tooltip.textContent = el.dataset.tooltip;
      el.classList.add('tooltip');
      el.appendChild(tooltip);
    });
  });

  // ========================================
  // DATA TABLE SORTING
  // ========================================

  window.initSortableTable = function(table) {
    const headers = table.querySelectorAll('th.sortable');

    headers.forEach(header => {
      header.addEventListener('click', function() {
        const sortKey = this.dataset.sort;
        const isAsc = !this.classList.contains('sort-asc');

        // Reset all headers
        headers.forEach(h => {
          h.classList.remove('sort-asc', 'sort-desc');
        });

        // Set current header
        this.classList.add(isAsc ? 'sort-asc' : 'sort-desc');

        // Sort table
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));

        rows.sort((a, b) => {
          const aVal = a.querySelector(`[data-sort="${sortKey}"]`)?.textContent || '';
          const bVal = b.querySelector(`[data-sort="${sortKey}"]`)?.textContent || '';

          if (isAsc) {
            return aVal.localeCompare(bVal, 'zh-CN');
          } else {
            return bVal.localeCompare(aVal, 'zh-CN');
          }
        });

        rows.forEach(row => tbody.appendChild(row));
      });
    });
  };

  // ========================================
  // CONFIRM DIALOG
  // ========================================

  window.confirmAction = function(message, callback) {
    const modalId = 'confirm-dialog-' + Date.now();

    const modal = document.createElement('div');
    modal.id = modalId;
    modal.className = 'modal modal-confirm';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');

    modal.innerHTML = `
      <div class="modal-backdrop" onclick="closeModal('${modalId}')"></div>
      <div class="modal-dialog modal-sm">
        <div class="modal-content">
          <div class="modal-body text-center">
            <div class="confirm-icon confirm-warning">
              <span class="material-symbols-outlined">help</span>
            </div>
            <h3 class="modal-title">确认操作</h3>
            <p class="confirm-message">${message}</p>
            <div class="confirm-actions">
              <button type="button" class="btn btn-secondary" onclick="closeModal('${modalId}')">
                取消
              </button>
              <button type="button" class="btn btn-primary" id="${modalId}-confirm">
                确认
              </button>
            </div>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(modal);

    document.getElementById(`${modalId}-confirm`).addEventListener('click', function() {
      closeModal(modalId);
      callback();
      setTimeout(() => modal.remove(), 300);
    });

    modal.addEventListener('click', function(e) {
      if (e.target === modal) {
        setTimeout(() => modal.remove(), 300);
      }
    });

    openModal(modalId);
  };

  // ========================================
  // AJAX FORM SUBMISSION
  // ========================================

  window.submitFormAjax = function(form, options = {}) {
    const url = form.action;
    const method = form.method || 'POST';
    const formData = new FormData(form);

    // Show loading state
    const submitBtn = form.querySelector('[type="submit"]');
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.dataset.originalText = submitBtn.innerHTML;
      submitBtn.innerHTML = '<span class="material-symbols-outlined spinning">sync</span> 处理中...';
    }

    fetch(url, {
      method: method,
      body: formData,
      headers: {
        'X-Requested-With': 'XMLHttpRequest'
      }
    })
    .then(response => response.json())
    .then(data => {
      if (data.success) {
        if (options.onSuccess) {
          options.onSuccess(data);
        } else {
          showToast(data.message || '操作成功', 'success');
        }
      } else {
        if (options.onError) {
          options.onError(data);
        } else {
          showToast(data.message || '操作失败', 'error');
        }
      }
    })
    .catch(error => {
      console.error('Error:', error);
      if (options.onError) {
        options.onError({ message: '网络错误，请稍后重试' });
      } else {
        showToast('网络错误，请稍后重试', 'error');
      }
    })
    .finally(() => {
      // Restore button state
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = submitBtn.dataset.originalText;
      }
    });
  };

  // ========================================
  // UTILITY FUNCTIONS
  // ========================================

  // Debounce function
  window.debounce = function(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  };

  // Throttle function
  window.throttle = function(func, limit) {
    let inThrottle;
    return function(...args) {
      if (!inThrottle) {
        func.apply(this, args);
        inThrottle = true;
        setTimeout(() => inThrottle = false, limit);
      }
    };
  };

  // Format date
  window.formatDate = function(date, format = 'YYYY-MM-DD') {
    const d = new Date(date);
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');

    return format
      .replace('YYYY', year)
      .replace('MM', month)
      .replace('DD', day);
  };

  // Format number with commas
  window.formatNumber = function(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  };

})();
