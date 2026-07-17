(function ($) {
    'use strict';

    function includeFuture() {
        return $('#id_include_future_workshops').is(':checked') ? '1' : '0';
    }

    function patchWorkshopAutocomplete() {
        var $workshop = $('#id_workshop');
        if (!$workshop.length) {
            return false;
        }
        var select2 = $workshop.data('select2');
        if (!select2 || !select2.options || !select2.options.ajax) {
            return false;
        }
        if (select2.options.ajax._gdIncludeFuturePatched) {
            return true;
        }
        var originalData = select2.options.ajax.data;
        select2.options.ajax.data = function (params) {
            var data;
            if (typeof originalData === 'function') {
                data = originalData.call(this, params) || {};
            } else {
                data = $.extend({}, originalData || {}, {
                    term: params.term,
                    page: params.page
                });
            }
            data.include_future = includeFuture();
            return data;
        };
        select2.options.ajax._gdIncludeFuturePatched = true;
        return true;
    }

    function init() {
        if (!$('#id_include_future_workshops').length || !$('#id_workshop').length) {
            return;
        }
        var attempts = 0;
        var timer = window.setInterval(function () {
            if (patchWorkshopAutocomplete() || ++attempts > 40) {
                window.clearInterval(timer);
            }
        }, 50);

        $(document).on('change', '#id_include_future_workshops', function () {
            var $workshop = $('#id_workshop');
            if ($workshop.length) {
                $workshop.val(null).trigger('change');
            }
            patchWorkshopAutocomplete();
        });
    }

    $(init);
})(django.jQuery);
