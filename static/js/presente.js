"use strict";

function setupOverlayScrollbars() {
  const sidebarWrapper = document.querySelector('.sidebar-wrapper');

  if (sidebarWrapper && typeof OverlayScrollbarsGlobal?.OverlayScrollbars !== 'undefined') {
    OverlayScrollbarsGlobal.OverlayScrollbars(sidebarWrapper, {
      scrollbars: {
        theme: 'os-theme-light',
        autoHide: 'leave',
        clickScroll: true,
      },
    });
  }
}

function setupTomSelect() {
  // Multi-select for users / generic multi-select fields (ex: campus)
  document.querySelectorAll('[data-tom-select="users"], [data-tom-select="multi"]').forEach(function(el) {
    if (!el.tomselect) {
      new TomSelect(el, {
        plugins: ['remove_button'],
        persist: false,
        create: false,
        maxItems: null,
        preload: false,
        loadThrottle: 300,
        onInitialize: function() {
          // Hide dropdown initially
          this.clearOptions();
        },
        load: function(query, callback) {
          // Only load if at least 2 characters typed
          if (query.length < 2) {
            return callback();
          }
          // Reload all options and filter
          const allOptions = Array.from(el.querySelectorAll('option')).map(opt => ({
            value: opt.value,
            text: opt.text
          })).filter(opt => opt.value && opt.text.toLowerCase().includes(query.toLowerCase()));
          callback(allOptions);
        },
        render: {
          option: function(data, escape) {
            return '<div>' + escape(data.text) + '</div>';
          },
          item: function(data, escape) {
            return '<div>' + escape(data.text) + '</div>';
          }
        }
      });
    }
  });

  // Multi-select for tags with create
  document.querySelectorAll('[data-tom-select="tags"]').forEach(function(el) {
    if (!el.tomselect) {
      new TomSelect(el, {
        plugins: ['remove_button'],
        persist: false,
        create: true,
        maxItems: null,
        preload: false,
        loadThrottle: 300,
        onInitialize: function() {
          // Store all options and clear initially
          this.allOptions = Array.from(el.querySelectorAll('option')).map(opt => ({
            value: opt.value,
            text: opt.text
          })).filter(opt => opt.value);
          this.clearOptions();
        },
        load: function(query, callback) {
          // Only load if at least 2 characters typed
          if (query.length < 2) {
            return callback();
          }
          // Filter stored options
          const filtered = this.allOptions.filter(opt =>
            opt.text.toLowerCase().includes(query.toLowerCase())
          );
          callback(filtered);
        },
        render: {
          option_create: function(data, escape) {
            return '<div class="create">Adicionar <strong>' + escape(data.input) + '</strong>&hellip;</div>';
          },
          no_results: function(data, escape) {
            if (data.input.length < 2) {
              return '<div class="no-results">Digite ao menos 2 caracteres...</div>';
            }
            return '<div class="no-results">Nenhum resultado encontrado.</div>';
          }
        }
      });
    }
  });

  // Simple select dropdowns (single select)
  document.querySelectorAll('[data-tom-select="simple"]').forEach(function(el) {
    if (!el.tomselect) {
      new TomSelect(el, {
        persist: false,
        create: false,
        allowEmptyOption: true,
        placeholder: el.getAttribute('placeholder') || 'Selecione...',
      });
    }
  });
}

function copyPublicLink() {
  const input = document.getElementById('publicLink');
  input.select();
  input.setSelectionRange(0, 99999); // For mobile devices
  navigator.clipboard.writeText(input.value);

  const button = event.target.closest('button');
  const originalHTML = button.innerHTML;
  button.innerHTML = '<i class="bi bi-check"></i> Copiado!';
  button.classList.remove('btn-outline-secondary');
  button.classList.add('btn-success');

  setTimeout(() => {
    button.innerHTML = originalHTML;
    button.classList.remove('btn-success');
    button.classList.add('btn-outline-secondary');
  }, 2000);
}

function muteIpCheckbox() {
  // Handle IP restriction toggle
  const restrictIpCheckbox = document.getElementById('id_restrict_ip');
  const allowedNetworksContainer = document.querySelector('[name="allowed_networks"]')?.closest('.mb-3');

  if (restrictIpCheckbox && allowedNetworksContainer) {
    function toggleAllowedNetworks() {
      const isRestricted = restrictIpCheckbox.checked;
      const checkboxes = allowedNetworksContainer.querySelectorAll('input[type="checkbox"]');

      checkboxes.forEach(function(checkbox) {
        checkbox.disabled = !isRestricted;
      });

      if (isRestricted) {
        allowedNetworksContainer.style.opacity = '1';
      } else {
        allowedNetworksContainer.style.opacity = '0.5';
      }
    }

    // Initial state
    toggleAllowedNetworks();

    // Listen for changes
    restrictIpCheckbox.addEventListener('change', toggleAllowedNetworks);
  }
}

// Export modal functions
function loadExportPreferences() {
  const savedColumns = localStorage.getItem('export_columns');
  const savedSort = localStorage.getItem('export_sort');

  if (savedColumns) {
    try {
      const columns = JSON.parse(savedColumns);
      // Uncheck all first
      document.querySelectorAll('input[name="columns"]').forEach(cb => cb.checked = false);
      // Check saved columns
      columns.forEach(col => {
        const checkbox = document.querySelector(`input[name="columns"][value="${col}"]`);
        if (checkbox) checkbox.checked = true;
      });
    } catch (e) {
      console.error('Error loading column preferences:', e);
    }
  }

  if (savedSort) {
    const sortSelect = document.getElementById('modal_sort_by');
    if (sortSelect) sortSelect.value = savedSort;
  }
}

function saveExportPreferences() {
  const form = document.getElementById('exportConfigForm');
  if (!form) return;

  // Save selected columns
  const columns = Array.from(form.querySelectorAll('input[name="columns"]:checked'))
    .map(cb => cb.value);
  localStorage.setItem('export_columns', JSON.stringify(columns));

  // Save sort preference
  const sortBy = form.querySelector('select[name="sort_by"]')?.value;
  if (sortBy) {
    localStorage.setItem('export_sort', sortBy);
  }
}

function closeExportModal() {
  const modalElement = document.querySelector('#modals-here');
  if (modalElement) {
    const modal = bootstrap.Modal.getInstance(modalElement);
    if (modal) {
      modal.hide();
    }
  }
}

function downloadPDF(activityPk, pdfUrl) {
  const form = document.getElementById('exportConfigForm');
  if (!form) return;

  const formData = new FormData(form);
  const params = new URLSearchParams(formData);

  saveExportPreferences();
  window.open(pdfUrl + '?' + params.toString(), '_blank');
  closeExportModal();
}

function downloadCSV(activityPk, csvUrl) {
  const form = document.getElementById('exportConfigForm');
  if (!form) return;

  const formData = new FormData(form);
  const params = new URLSearchParams(formData);

  saveExportPreferences();
  window.location.href = csvUrl + '?' + params.toString();
  closeExportModal();
}
