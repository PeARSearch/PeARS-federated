// SPDX-FileCopyrightText: 2025 PeARS Project, <community@pearsproject.org>
// SPDX-License-Identifier: AGPL-3.0-only

// Client-side theme toggle using color-scheme property.
// Works with Oat UI's light-dark() CSS function.

(function () {
  'use strict';

  var STORAGE_KEY = 'pears-theme';

  function getPreferred() {
    var stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'light' || stored === 'dark') return stored;
    // Respect OS preference as default
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark';
    }
    return 'light';
  }

  function apply(theme) {
    document.documentElement.style.colorScheme = theme;
    document.documentElement.setAttribute('data-theme', theme);
    // Update toggle button icon visibility
    var sunIcon = document.getElementById('theme-icon-light');
    var moonIcon = document.getElementById('theme-icon-dark');
    if (sunIcon && moonIcon) {
      // Show sun when dark (clicking switches to light), show moon when light
      sunIcon.style.display = theme === 'dark' ? 'inline-block' : 'none';
      moonIcon.style.display = theme === 'light' ? 'inline-block' : 'none';
    }
  }

  function toggle() {
    var current = getPreferred();
    var next = current === 'dark' ? 'light' : 'dark';
    localStorage.setItem(STORAGE_KEY, next);
    apply(next);
  }

  // Apply immediately (before DOM ready) to prevent flash
  apply(getPreferred());

  // Bind toggle button once DOM is ready
  document.addEventListener('DOMContentLoaded', function () {
    var btn = document.getElementById('theme-toggle');
    if (btn) {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        toggle();
      });
    }
    // Re-apply to update icons after DOM is ready
    apply(getPreferred());
  });

  // Listen for OS theme changes
  if (window.matchMedia) {
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function (e) {
      // Only follow OS if user hasn't explicitly set a preference
      if (!localStorage.getItem(STORAGE_KEY)) {
        apply(e.matches ? 'dark' : 'light');
      }
    });
  }
})();
