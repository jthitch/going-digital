/**
 * Workshop admin: control widths and byline label info button.
 */
(function ($) {
    'use strict';

    function fixWorkshopControlWidths() {
        if (!$('body').hasClass('model-workshop')) {
            return;
        }
        var width = '24em';
        $('.card-body .select2-container').each(function () {
            $(this).css({ width: width, maxWidth: '100%' });
        });
    }

    function initBylineInfo() {
        if (!$('body').hasClass('model-workshop')) {
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
