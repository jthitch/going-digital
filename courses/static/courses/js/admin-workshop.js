/**
 * Workshop admin: control widths, date/time pickers, and byline help.
 */
(function ($) {
    'use strict';

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
                $('#id_date_0, #id_date_1').val('');
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

    function initWorkshopAdmin() {
        fixWorkshopControlWidths();
        initLoanCamerasToggle();
        initOpenDatedToggle();
        initWorkshopDateTimePicker();
        initBylineInfo();
    }

    $(document).ready(function () {
        initWorkshopAdmin();
        setTimeout(initWorkshopAdmin, 0);
    });

    $(document).on('shown.bs.tab', 'a[data-toggle="pill"]', function () {
        setTimeout(initWorkshopAdmin, 0);
    });
})(django.jQuery);
