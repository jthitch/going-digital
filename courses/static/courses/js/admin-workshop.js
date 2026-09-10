/**
 * Workshop admin: control widths, date/time pickers, byline help, and image picker.
 *
 * Loaded via ModelAdmin.Media, which Jazzmin may inject before django.jQuery.
 * Wait for jQuery before bootstrapping.
 */
(function () {
    'use strict';

    var IMAGE_PREVIEW_COUNT = 5;
    var IMAGE_MODAL_PAGE_SIZE = 20;
    var bootAttempts = 0;
    var MAX_BOOT_ATTEMPTS = 40;

    function whenJqueryReady(callback) {
        var $ = (window.django && django.jQuery) || window.jQuery;
        if ($) {
            callback($);
            return;
        }
        bootAttempts += 1;
        if (bootAttempts > MAX_BOOT_ATTEMPTS) {
            return;
        }
        window.setTimeout(function () {
            whenJqueryReady(callback);
        }, 50);
    }

    function boot($) {
        function isWorkshopAdminPage() {
            return $('body').hasClass('model-workshop');
        }

        function fixWorkshopControlWidths() {
            if (!isWorkshopAdminPage()) {
                return;
            }
            var width = '24em';
            $('.card-body .select2-container').each(function () {
                $(this).css({ width: width, maxWidth: '100%' });
            });
        }

        function initLoanCamerasToggle() {
            if (!isWorkshopAdminPage()) {
                return;
            }
            var $checkbox = $('#id_cameras_available');
            if (!$checkbox.length) {
                return;
            }

            function clearLoanCamerasIfNeeded() {
                if (!$checkbox.is(':checked')) {
                    $('#id_number_of_loan_cameras_available').val('0');
                }
            }

            $checkbox.off('change.gdLoanCameras').on('change.gdLoanCameras', clearLoanCamerasIfNeeded);
            clearLoanCamerasIfNeeded();
        }

        function openNativePicker(input) {
            if (!input || typeof input.showPicker !== 'function') {
                return;
            }
            try {
                input.showPicker();
            } catch (err) {
                /* Browser may block showPicker without a user gesture or if already open. */
            }
        }

        function initWorkshopDateTimePicker() {
            if (!isWorkshopAdminPage()) {
                return;
            }

            $(document)
                .off('click.gdWorkshopPicker', '.gd-workshop-date-input, .gd-workshop-time-input')
                .on('click.gdWorkshopPicker', '.gd-workshop-date-input, .gd-workshop-time-input', function () {
                    openNativePicker(this);
                });
        }

        function initOpenDatedToggle() {
            if (!isWorkshopAdminPage()) {
                return;
            }
            var $checkbox = $('#id_open_dated');
            if (!$checkbox.length) {
                return;
            }

            function clearDateIfOpenDated() {
                if ($checkbox.is(':checked')) {
                    $('#id_date_0, #id_date_1, #id_end_at_0, #id_end_at_1').val('');
                }
            }

            $checkbox.off('change.gdOpenDated').on('change.gdOpenDated', clearDateIfOpenDated);
            clearDateIfOpenDated();
        }

        function initBylineInfo() {
            if (!isWorkshopAdminPage()) {
                return;
            }
            var $label = $('.field-byline label').first();
            if (!$label.length || $label.find('.gd-byline-info').length) {
                return;
            }

            var $btn = $(
                '<button type="button" class="gd-byline-info" ' +
                'aria-label="Jump to byline instructions" title="View instructions"></button>'
            );
            $btn.append('<i class="fas fa-info-circle" aria-hidden="true"></i>');
            $btn.on('click', function () {
                var help = document.querySelector('.field-byline .gd-byline-help');
                if (help) {
                    help.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                    help.classList.add('gd-byline-help-highlight');
                    window.setTimeout(function () {
                        help.classList.remove('gd-byline-help-highlight');
                    }, 1200);
                }
            });
            $label.append($btn);
        }

        function initSaveGuard() {
            if (!isWorkshopAdminPage()) {
                return;
            }
            var $form = $('body.model-workshop form').first();
            if (!$form.length || $form.data('gdSaveGuard')) {
                return;
            }
            $form.data('gdSaveGuard', true);
            $form.on('submit', function () {
                var $buttons = $form.find('input[type="submit"], button[type="submit"]');
                $buttons.prop('disabled', true);
                $buttons.filter('[name="_save"], [name="_continue"]').first().val('Saving…');
            });
        }

        function ensureImageModal() {
            var $modal = $('#gd-workshop-image-modal');
            if ($modal.length) {
                return $modal;
            }
            $modal = $(
                '<div id="gd-workshop-image-modal" class="gd-workshop-image-modal" hidden>' +
                  '<div class="gd-workshop-image-modal__backdrop" data-gd-image-modal-close></div>' +
                  '<div class="gd-workshop-image-modal__dialog" role="dialog" aria-modal="true" ' +
                       'aria-labelledby="gd-workshop-image-modal-title" tabindex="-1">' +
                    '<div class="gd-workshop-image-modal__header">' +
                      '<h2 id="gd-workshop-image-modal-title" class="gd-workshop-image-modal__title">Display images</h2>' +
                      '<button type="button" class="gd-workshop-image-modal__close" ' +
                              'data-gd-image-modal-close aria-label="Close">&times;</button>' +
                    '</div>' +
                    '<div class="gd-workshop-image-modal__grid" role="list"></div>' +
                    '<div class="gd-workshop-image-modal__footer">' +
                      '<div class="gd-workshop-image-modal__pager">' +
                        '<button type="button" class="gd-workshop-image-modal__prev btn btn-outline-secondary btn-sm">Previous</button>' +
                        '<span class="gd-workshop-image-modal__page" aria-live="polite"></span>' +
                        '<button type="button" class="gd-workshop-image-modal__next btn btn-outline-secondary btn-sm">Next</button>' +
                      '</div>' +
                      '<button type="button" class="gd-workshop-image-modal__done btn btn-primary btn-sm" ' +
                              'data-gd-image-modal-close>Done</button>' +
                    '</div>' +
                  '</div>' +
                '</div>'
            );
            $('body').append($modal);
            return $modal;
        }

        function getImagePickerItems($picker) {
            return $picker.children('li, div');
        }

        function csrfToken() {
            var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
            if (match) {
                return decodeURIComponent(match[1]);
            }
            var $input = $('input[name="csrfmiddlewaretoken"]').first();
            return $input.length ? $input.val() : '';
        }

        function updateSeeMoreLabel($picker) {
            var $seeMore = $picker.closest('.gd-workshop-image-picker-shell')
                .find('.gd-workshop-image-picker__see-more');
            if (!$seeMore.length) {
                return;
            }
            var $items = getImagePickerItems($picker);
            var extra = Math.max(0, $items.length - IMAGE_PREVIEW_COUNT);
            if (extra <= 0) {
                $seeMore.hide();
                return;
            }
            $seeMore.show();
            var selectedHidden = 0;
            $items.slice(IMAGE_PREVIEW_COUNT).each(function () {
                if ($(this).find('input[type="checkbox"]').prop('checked')) {
                    selectedHidden += 1;
                }
            });
            var label = 'See more (' + extra + ' more)';
            if (selectedHidden) {
                label += ' · ' + selectedHidden + ' selected';
            }
            $seeMore.text(label);
        }

        function refreshImagePickerCompact($picker) {
            if (!$picker || !$picker.length) {
                return;
            }
            var $items = getImagePickerItems($picker);
            $items.removeClass('gd-workshop-image-picker__overflow');

            if ($items.length <= IMAGE_PREVIEW_COUNT) {
                $picker.removeClass('gd-workshop-image-picker--compact');
                updateSeeMoreLabel($picker);
                return;
            }

            var $shell = $picker.closest('.gd-workshop-image-picker-shell');
            if (!$shell.length) {
                $shell = $('<div class="gd-workshop-image-picker-shell"></div>');
                $picker.before($shell);
                $shell.append($picker);
            }
            if (!$shell.find('.gd-workshop-image-picker__see-more').length) {
                $shell.append(
                    '<button type="button" class="gd-workshop-image-picker__see-more btn btn-outline-primary btn-sm"></button>'
                );
            }

            $picker.addClass('gd-workshop-image-picker--compact');
            $items.each(function (index) {
                if (index >= IMAGE_PREVIEW_COUNT) {
                    $(this).addClass('gd-workshop-image-picker__overflow');
                }
            });
            updateSeeMoreLabel($picker);
        }

        function prependUploadedImage(image) {
            var $picker = $('.gd-workshop-image-picker').first();
            if (!$picker.length) {
                return;
            }
            var existing = $picker.find('input[type="checkbox"][value="' + image.id + '"]');
            if (existing.length) {
                existing.prop('checked', true);
                refreshImagePickerCompact($picker);
                return;
            }
            var $item = $('<div></div>');
            var $label = $('<label></label>');
            var $checkbox = $('<input type="checkbox" name="images">')
                .attr('value', image.id)
                .prop('checked', true);
            $label.append($checkbox);
            $label.append(image.option_html || '');
            $item.append($label);
            $picker.prepend($item);
            refreshImagePickerCompact($picker);
        }

        function initWorkshopImagePicker() {
            if (!isWorkshopAdminPage()) {
                return;
            }
            var $picker = $('.gd-workshop-image-picker').first();
            if (!$picker.length) {
                return;
            }

            refreshImagePickerCompact($picker);

            if ($picker.data('gdImagePickerReady')) {
                return;
            }
            $picker.data('gdImagePickerReady', true);

            var $modal = ensureImageModal();
            var $grid = $modal.find('.gd-workshop-image-modal__grid');
            var $pageLabel = $modal.find('.gd-workshop-image-modal__page');
            var $prev = $modal.find('.gd-workshop-image-modal__prev');
            var $next = $modal.find('.gd-workshop-image-modal__next');
            var state = { page: 0, lastFocus: null };

            function pageCount() {
                return Math.max(1, Math.ceil(getImagePickerItems($picker).length / IMAGE_MODAL_PAGE_SIZE));
            }

            function renderModalPage() {
                var $items = getImagePickerItems($picker);
                var totalPages = pageCount();
                if (state.page >= totalPages) {
                    state.page = totalPages - 1;
                }
                if (state.page < 0) {
                    state.page = 0;
                }
                var start = state.page * IMAGE_MODAL_PAGE_SIZE;
                var end = start + IMAGE_MODAL_PAGE_SIZE;
                $grid.empty();

                $items.slice(start, end).each(function () {
                    var $li = $(this);
                    var $orig = $li.find('input[type="checkbox"]').first();
                    var optionHtml = $li.find('.gd-workshop-image-option').html() || '';
                    var $card = $(
                        '<label class="gd-workshop-image-modal__card" role="listitem">' +
                          '<input type="checkbox" class="gd-workshop-image-modal__check">' +
                          '<span class="gd-workshop-image-option">' + optionHtml + '</span>' +
                        '</label>'
                    );
                    var $mirror = $card.find('input.gd-workshop-image-modal__check');
                    $mirror.prop('checked', $orig.prop('checked'));
                    $mirror.on('change', function () {
                        $orig.prop('checked', $mirror.prop('checked')).trigger('change');
                        updateSeeMoreLabel($picker);
                    });
                    $grid.append($card);
                });

                $pageLabel.text('Page ' + (state.page + 1) + ' of ' + totalPages);
                $prev.prop('disabled', state.page <= 0);
                $next.prop('disabled', state.page >= totalPages - 1);
            }

            function openModal() {
                state.lastFocus = document.activeElement;
                state.page = 0;
                renderModalPage();
                $modal.prop('hidden', false);
                $('body').addClass('gd-workshop-image-modal-open');
                window.setTimeout(function () {
                    $modal.find('.gd-workshop-image-modal__dialog').trigger('focus');
                }, 0);
            }

            function closeModal() {
                $modal.prop('hidden', true);
                $('body').removeClass('gd-workshop-image-modal-open');
                if (state.lastFocus && typeof state.lastFocus.focus === 'function') {
                    state.lastFocus.focus();
                }
            }

            $(document)
                .off('click.gdWorkshopSeeMore')
                .on('click.gdWorkshopSeeMore', '.gd-workshop-image-picker__see-more', function (event) {
                    event.preventDefault();
                    openModal();
                });

            $prev.off('click.gdWorkshopImageModal').on('click.gdWorkshopImageModal', function () {
                state.page -= 1;
                renderModalPage();
            });

            $next.off('click.gdWorkshopImageModal').on('click.gdWorkshopImageModal', function () {
                state.page += 1;
                renderModalPage();
            });

            $modal
                .off('click.gdWorkshopImageModalClose')
                .on('click.gdWorkshopImageModalClose', '[data-gd-image-modal-close]', function (event) {
                    event.preventDefault();
                    closeModal();
                });

            $(document)
                .off('keydown.gdWorkshopImageModal')
                .on('keydown.gdWorkshopImageModal', function (event) {
                    if (event.key === 'Escape' && !$modal.prop('hidden')) {
                        closeModal();
                    }
                });

            $picker.on('change', 'input[type="checkbox"]', function () {
                updateSeeMoreLabel($picker);
            });
        }

        function initWorkshopImageUploadButton() {
            if (!isWorkshopAdminPage()) {
                return;
            }
            var $input = $('#id_image_upload');
            if (!$input.length || $input.data('gdUploadReady')) {
                return;
            }
            var uploadUrl = $input.attr('data-upload-url');
            if (!uploadUrl) {
                return;
            }
            $input.data('gdUploadReady', true);

            var $actions = $('<div class="gd-workshop-image-upload-actions"></div>');
            var $btn = $(
                '<button type="button" class="btn btn-primary btn-sm gd-workshop-image-upload-btn">Upload</button>'
            );
            var $status = $('<span class="gd-workshop-image-upload-status" aria-live="polite"></span>');
            $input.after($actions);
            $actions.append($btn).append($status);

            $btn.on('click', function (event) {
                event.preventDefault();
                var file = $input[0].files && $input[0].files[0];
                if (!file) {
                    $status.removeClass('is-success is-error').addClass('is-error').text('Choose a file first.');
                    return;
                }

                var formData = new FormData();
                formData.append('image', file);

                $btn.prop('disabled', true).text('Uploading…');
                $status.removeClass('is-success is-error').text('');

                $.ajax({
                    url: uploadUrl,
                    method: 'POST',
                    data: formData,
                    processData: false,
                    contentType: false,
                    headers: { 'X-CSRFToken': csrfToken() },
                }).done(function (response) {
                    if (!response || !response.ok) {
                        $status.addClass('is-error').text((response && response.error) || 'Upload failed.');
                        return;
                    }
                    prependUploadedImage(response);
                    $input.val('');
                    $status.addClass('is-success').text('Uploaded and selected in Display images.');
                }).fail(function (xhr) {
                    var message = 'Upload failed.';
                    if (xhr.responseJSON && xhr.responseJSON.error) {
                        message = xhr.responseJSON.error;
                    }
                    $status.addClass('is-error').text(message);
                }).always(function () {
                    $btn.prop('disabled', false).text('Upload');
                });
            });
        }

        function initWorkshopAdmin() {
            fixWorkshopControlWidths();
            initLoanCamerasToggle();
            initOpenDatedToggle();
            initWorkshopDateTimePicker();
            initBylineInfo();
            initSaveGuard();
            initWorkshopImagePicker();
            initWorkshopImageUploadButton();
        }

        $(document).ready(function () {
            initWorkshopAdmin();
            setTimeout(initWorkshopAdmin, 0);
            setTimeout(initWorkshopAdmin, 250);
        });

        $(document).on('shown.bs.tab', 'a[data-toggle="pill"], a[data-bs-toggle="pill"], a[data-toggle="tab"], a[data-bs-toggle="tab"]', function () {
            setTimeout(initWorkshopAdmin, 0);
        });
    }

    whenJqueryReady(boot);
})();
