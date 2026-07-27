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
    });
})(jQuery);
