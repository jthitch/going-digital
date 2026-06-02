/**
 * Workshop admin: keep Jazzmin Select2 width in sync with CSS (width: element).
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

    $(document).ready(function () {
        fixWorkshopControlWidths();
        setTimeout(fixWorkshopControlWidths, 0);
    });
})(django.jQuery);
