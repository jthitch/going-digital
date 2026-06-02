/**
 * Venue admin: Jazzmin Select2 treats duplicate numeric option values as one
 * (e.g. region id 6 and user id 6). Keep venue FK/status fields on native selects.
 */
(function ($) {
    'use strict';

    var VENUE_NATIVE_SELECT = 'select.venue-admin-select';

    function patchSelect2() {
        if (!$.fn.select2 || $.fn.select2._venueAdminPatched) {
            return;
        }
        var original = $.fn.select2;
        $.fn.select2 = function () {
            var $eligible = this.filter(function () {
                return !$(this).is(VENUE_NATIVE_SELECT);
            });
            if (!$eligible.length) {
                return this;
            }
            return original.apply($eligible, arguments);
        };
        $.fn.select2._venueAdminPatched = true;
    }

    function destroyVenueSelect2() {
        if (!$('body').hasClass('model-venue')) {
            return;
        }
        $(VENUE_NATIVE_SELECT).each(function () {
            var $el = $(this);
            if ($el.hasClass('select2-hidden-accessible')) {
                $el.select2('destroy');
            }
        });
    }

    function slugifyVenueName(value) {
        var text = (value || '').trim();
        if (!text) {
            return '';
        }
        if (typeof URLify === 'function') {
            return URLify(text, 255, false);
        }
        return text
            .toLowerCase()
            .replace(/[^\w\s-]/g, '')
            .replace(/[\s_-]+/g, '-')
            .replace(/^-+|-+$/g, '');
    }

    /** Slug follows venue name until the slug field is edited manually. */
    function initVenueSlugPrepopulate() {
        if (!$('body').hasClass('model-venue')) {
            return;
        }
        var $slug = $('#id_slug');
        var $name = $('#id_venue_name');
        if (!$slug.length || !$name.length || $slug.data('gdSlugPrepopulate')) {
            return;
        }
        $slug.data('gdSlugPrepopulate', true);

        if (typeof $.fn.prepopulate === 'function') {
            $slug.prepopulate(['#id_venue_name'], 255, false);
            return;
        }

        var slugEdited = Boolean(($slug.val() || '').trim());
        $slug.on('change', function () {
            slugEdited = true;
        });

        function syncSlugFromName() {
            if (slugEdited && ($slug.val() || '').trim()) {
                return;
            }
            $slug.val(slugifyVenueName($name.val()));
        }

        $name.on('input keyup change', syncSlugFromName);
        syncSlugFromName();
    }

    function syncVenueCkEditorFields() {
        if (!$('body').hasClass('model-venue') || typeof CKEDITOR === 'undefined') {
            return;
        }
        ['id_main_content', 'id_sub_content'].forEach(function (id) {
            var textarea = document.getElementById(id);
            if (!textarea) {
                return;
            }
            var html = textarea.value || textarea.defaultValue || textarea.textContent;
            if (!html) {
                return;
            }
            var editor = CKEDITOR.instances[id];
            if (editor) {
                if (editor.status === 'ready') {
                    editor.setData(html);
                } else {
                    editor.on('instanceReady', function () {
                        editor.setData(html);
                    });
                }
            }
        });
    }

    function initVenueContentTabCkEditor() {
        if (!$('body').hasClass('model-venue')) {
            return;
        }
        var tabSelector = 'a[href="#venue-content-tab"]';
        $(document).on('shown.bs.tab', tabSelector, syncVenueCkEditorFields);
        setTimeout(syncVenueCkEditorFields, 0);
        setTimeout(syncVenueCkEditorFields, 500);
    }

    function initVenueAdmin() {
        patchSelect2();
        destroyVenueSelect2();
        initVenueSlugPrepopulate();
        initVenueContentTabCkEditor();
    }

    $(document).ready(function () {
        initVenueAdmin();
        setTimeout(initVenueAdmin, 0);
    });

    $(window).on('load', function () {
        initVenueAdmin();
    });

    django.jQuery(document).on('formset:added', function () {
        patchSelect2();
        setTimeout(destroyVenueSelect2, 0);
    });
})(django.jQuery);
