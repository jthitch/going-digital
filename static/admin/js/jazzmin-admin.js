(function ($) {
    'use strict';

    /**
     * Jazzmin persists sidebar state in a jazzy_menu cookie. A stale "closed"
     * value collapses the sidebar on load. Default to expanded (AdminLTE 4).
     */
    function defaultSidebarOpen() {
        document.cookie = 'jazzy_menu=open; path=/; SameSite=Strict';
        $('body').removeClass('sidebar-collapse').addClass('sidebar-open');
    }

    function isAdminDarkMode() {
        return document.documentElement.getAttribute('data-bs-theme') === 'dark';
    }

    var CKEDITOR_DARK_CONTENTS_CSS = [
        'html, body {',
        '  background-color: #212529 !important;',
        '  color: #f8f9fa !important;',
        '}',
        'body {',
        '  margin: 8px;',
        '}',
        'body, body p, body div, body span, body li, body td, body th, body h1, body h2, body h3, body h4, body h5, body h6 {',
        '  color: #f8f9fa !important;',
        '}',
        'a { color: #6ea8fe !important; }',
        'hr { border-color: #565e64 !important; }',
    ].join('\n');

    function applyCkeditorContentsTheme(editor) {
        if (!editor) {
            return;
        }
        try {
            var doc = editor.document && editor.document.$;
            if (!doc) {
                return;
            }
            var styleId = 'gd-cke-dark-mode';
            var existing = doc.getElementById(styleId);
            if (isAdminDarkMode()) {
                if (!existing) {
                    var style = doc.createElement('style');
                    style.id = styleId;
                    style.appendChild(doc.createTextNode(CKEDITOR_DARK_CONTENTS_CSS));
                    (doc.head || doc.getElementsByTagName('head')[0] || doc.documentElement).appendChild(style);
                }
                if (doc.body) {
                    doc.body.style.backgroundColor = '#212529';
                    doc.body.style.color = '#f8f9fa';
                }
            } else if (existing && existing.parentNode) {
                existing.parentNode.removeChild(existing);
                if (doc.body) {
                    doc.body.style.backgroundColor = '';
                    doc.body.style.color = '';
                }
            }
        } catch (err) {
            // Cross-origin / destroyed instance — ignore.
        }
    }

    function syncAllCkeditorThemes() {
        if (typeof CKEDITOR === 'undefined' || !CKEDITOR.instances) {
            return;
        }
        Object.keys(CKEDITOR.instances).forEach(function (name) {
            applyCkeditorContentsTheme(CKEDITOR.instances[name]);
        });
    }

    function initCkeditorDarkMode() {
        if (typeof CKEDITOR === 'undefined') {
            return;
        }
        if (!window.gdCkeditorDarkModeBound) {
            window.gdCkeditorDarkModeBound = true;
            CKEDITOR.on('instanceReady', function (evt) {
                applyCkeditorContentsTheme(evt.editor);
                evt.editor.on('mode', function () {
                    window.setTimeout(function () {
                        applyCkeditorContentsTheme(evt.editor);
                    }, 0);
                });
                evt.editor.on('contentDom', function () {
                    applyCkeditorContentsTheme(evt.editor);
                });
            });
            if (window.MutationObserver) {
                new MutationObserver(syncAllCkeditorThemes).observe(document.documentElement, {
                    attributes: true,
                    attributeFilter: ['data-bs-theme'],
                });
            }
        }
        syncAllCkeditorThemes();
    }

    function initGdChangelistActions() {
        if (!$('body').hasClass('change-list')) {
            return;
        }
        const $form = $('#changelist-form');
        const $bar = $('#gd-changelist-actions-bar');
        if (!$form.length || !$bar.length) {
            return;
        }

        const $actionSelect = $form.find('select[name=action]');
        const $submit = $('#gd-changelist-action-submit');
        const $modal = $('#gd-delete-selected-modal');

        if ($actionSelect.length && $actionSelect.data('select2')) {
            $actionSelect.select2('destroy');
        }

        function selectedCount() {
            return $form.find('input.action-select:checked').length;
        }

        function updateBar() {
            const count = selectedCount();
            if (count > 0) {
                $bar.removeClass('d-none').addClass('d-flex');
            } else {
                $bar.addClass('d-none').removeClass('d-flex');
            }
        }

        $form.on('change', 'input.action-select, #action-toggle', function () {
            window.setTimeout(updateBar, 0);
        });

        const counter = document.querySelector('.gd-changelist-actions .action-counter');
        if (counter && window.MutationObserver) {
            new MutationObserver(updateBar).observe(counter, {
                childList: true,
                characterData: true,
                subtree: true,
            });
        }

        updateBar();

        function runAction(actionName) {
            if (!actionName || selectedCount() === 0) {
                return;
            }
            $actionSelect.val(actionName);
            $submit.trigger('click');
        }

        $bar.on('click', '.gd-changelist-run-action', function (e) {
            e.preventDefault();
            runAction($(this).data('action'));
        });

        $bar.on('click', '.gd-changelist-delete-trigger', function (e) {
            e.preventDefault();
            if (selectedCount() === 0) {
                return;
            }
            const count = selectedCount();
            const body = document.getElementById('gd-delete-selected-modal-body');
            if (body) {
                body.textContent = count === 1
                    ? 'Are you sure you want to delete the selected item? This cannot be undone.'
                    : 'Are you sure you want to delete the selected ' + count + ' items? This cannot be undone.';
            }
            const modalEl = $modal[0];
            if (modalEl && window.bootstrap && window.bootstrap.Modal) {
                window.bootstrap.Modal.getOrCreateInstance(modalEl).show();
            } else if (window.confirm && body) {
                if (window.confirm(body.textContent)) {
                    runAction('delete_selected');
                }
            }
        });

        $('#gd-delete-selected-confirm').on('click', function () {
            const modalEl = $modal[0];
            if (modalEl && window.bootstrap && window.bootstrap.Modal) {
                const instance = window.bootstrap.Modal.getInstance(modalEl);
                if (instance) {
                    instance.hide();
                }
            }
            runAction('delete_selected');
        });
    }

    $(document).ready(function () {
        if (!$('body').hasClass('no-sidebar') && $('#jazzy-sidebar').length) {
            defaultSidebarOpen();
        }
        window.setTimeout(initGdChangelistActions, 0);
        window.setTimeout(initCkeditorDarkMode, 0);
        window.setTimeout(initCkeditorDarkMode, 500);
    });
})(jQuery);
