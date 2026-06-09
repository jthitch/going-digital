/**
 * Venue admin postcode lookup (vanilla JS — does not depend on jQuery load order).
 */
(function () {
    'use strict';

    if (window.gdVenuePostcodeLookupInit) {
        return;
    }
    window.gdVenuePostcodeLookupInit = true;

    var lookupPayloads = new WeakMap();

    function venuePostcodeLookupUrl() {
        var match = window.location.pathname.match(/^(\/admin\/courses\/venue\/)/);
        if (match) {
            return match[1] + 'postcode-lookup/';
        }
        return '/admin/courses/venue/postcode-lookup/';
    }

    function normaliseCounty(value) {
        return (value || '').toLowerCase().replace(/[^a-z0-9]+/g, '');
    }

    function findPostcodeFieldContainer(input) {
        var wrap = input.closest('.venue-postcode-lookup-wrap');
        return (
            input.closest('.field-postcode_lookup')
            || input.closest('.form-group')
            || input.closest('.form-row')
            || (wrap ? wrap.parentElement : null)
            || input.parentElement
        );
    }

    function findPostcodeInputColumn(input) {
        var wrap = input.closest('.venue-postcode-lookup-wrap');
        if (wrap) {
            var column = wrap.closest('.col-sm-7, .flex-container');
            if (column) {
                return column;
            }
            return wrap.parentElement;
        }
        return findPostcodeFieldContainer(input);
    }

    function selectCountyOption(countySelect, countyName) {
        if (!countySelect || !countyName) {
            return;
        }
        var target = normaliseCounty(countyName);
        if (!target) {
            return;
        }
        var matched = null;
        Array.prototype.forEach.call(countySelect.options, function (option) {
            if (matched !== null) {
                return;
            }
            var text = normaliseCounty(option.text);
            if (!text) {
                return;
            }
            if (text === target || text.indexOf(target) !== -1 || target.indexOf(text) !== -1) {
                matched = option.value;
            }
        });
        if (matched !== null) {
            countySelect.value = matched;
            countySelect.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }

    function applyVenueAddressSelection(selection, payload) {
        var addressField = document.getElementById('id_venue_address');
        var locationField = document.getElementById('id_location');
        var latitudeField = document.getElementById('id_latitude');
        var longitudeField = document.getElementById('id_longitude');
        var countyField = document.getElementById('id_county');

        if (addressField && selection.address) {
            addressField.value = selection.address;
        }
        if (locationField) {
            var locationValue = selection.location || payload.location || '';
            if (locationValue) {
                locationField.value = locationValue;
            }
        }
        if (latitudeField && payload.latitude != null) {
            latitudeField.value = payload.latitude;
        }
        if (longitudeField && payload.longitude != null) {
            longitudeField.value = payload.longitude;
        }
        selectCountyOption(countyField, selection.county || payload.county || '');

        if (latitudeField && longitudeField && payload.latitude != null && payload.longitude != null) {
            document.dispatchEvent(new CustomEvent('gdVenueCoordsChanged', {
                detail: {
                    latitude: parseFloat(payload.latitude),
                    longitude: parseFloat(payload.longitude),
                    pan: true,
                },
            }));
        }
    }

    function setPostcodeLookupMessage(container, text, type) {
        if (!container) {
            return;
        }
        var message = container.querySelector('.venue-postcode-lookup-message');
        if (!message) {
            message = document.createElement('p');
            message.className = 'venue-postcode-lookup-message';
            message.setAttribute('role', 'status');
            var results = container.querySelector('.venue-postcode-lookup-results');
            if (results) {
                results.insertAdjacentElement('afterend', message);
            } else {
                container.appendChild(message);
            }
        }
        message.className = 'venue-postcode-lookup-message' + (type ? ' is-' + type : '');
        message.textContent = text || '';
        message.hidden = !text;
    }

    function getOrCreateResults(column, wrap) {
        var results = column.querySelector('.venue-postcode-lookup-results');
        if (!results) {
            results = document.createElement('select');
            results.className = 'venue-postcode-lookup-results';
            results.setAttribute('aria-label', 'Select an address');
            results.hidden = true;
            results.innerHTML = '<option value="">Select an address…</option>';
            if (wrap) {
                wrap.insertAdjacentElement('afterend', results);
            } else {
                column.appendChild(results);
            }
        }
        return results;
    }

    function resetResults(results) {
        results.hidden = true;
        results.innerHTML = '<option value="">Select an address…</option>';
        lookupPayloads.delete(results);
    }

    function runPostcodeLookup(input, button) {
        var column = findPostcodeInputColumn(input);
        var wrap = input.closest('.venue-postcode-lookup-wrap');
        var results = getOrCreateResults(column, wrap);
        var postcode = (input.value || '').trim();

        if (!postcode) {
            setPostcodeLookupMessage(column, 'Enter a UK postcode first.', 'error');
            resetResults(results);
            return;
        }

        if (button) {
            button.disabled = true;
            button.textContent = 'Looking up…';
        }
        setPostcodeLookupMessage(column, '', null);
        resetResults(results);

        var url = venuePostcodeLookupUrl() + '?postcode=' + encodeURIComponent(postcode);
        fetch(url, {
            method: 'GET',
            headers: { Accept: 'application/json' },
            credentials: 'same-origin',
        })
            .then(function (response) {
                return response.json().then(function (payload) {
                    if (!response.ok) {
                        throw payload;
                    }
                    return payload;
                }).catch(function (parseError) {
                    if (!response.ok) {
                        throw { error: 'Postcode lookup failed (' + response.status + ').' };
                    }
                    throw parseError;
                });
            })
            .then(function (payload) {
                var addresses = payload.addresses || [];
                if (!addresses.length) {
                    setPostcodeLookupMessage(column, 'No addresses found for this postcode.', 'error');
                    return;
                }

                addresses.forEach(function (item, index) {
                    var option = document.createElement('option');
                    option.value = String(index);
                    option.textContent = item.label || item.address;
                    results.appendChild(option);
                });
                lookupPayloads.set(results, payload);
                results.hidden = false;

                if (addresses.length === 1) {
                    results.value = '0';
                    applyVenueAddressSelection(addresses[0], payload);
                }

                var message = payload.message;
                if (!message) {
                    message = addresses.length > 1
                        ? 'Select an address to fill the venue details below.'
                        : 'Address and map coordinates updated.';
                }
                setPostcodeLookupMessage(
                    column,
                    message,
                    addresses.length > 1 ? 'info' : 'success',
                );
            })
            .catch(function (error) {
                var message = 'Postcode lookup failed.';
                if (error && error.error) {
                    message = error.error;
                }
                setPostcodeLookupMessage(column, message, 'error');
            })
            .finally(function () {
                if (button) {
                    button.disabled = false;
                    button.textContent = 'Look up';
                }
            });
    }

    document.addEventListener('click', function (event) {
        var button = event.target.closest('.venue-postcode-lookup-btn');
        if (!button) {
            return;
        }
        event.preventDefault();
        var wrap = button.closest('.venue-postcode-lookup-wrap');
        if (!wrap) {
            return;
        }
        var input = wrap.querySelector('#id_postcode_lookup, .venue-postcode-lookup-input');
        if (!input) {
            return;
        }
        runPostcodeLookup(input, button);
    });

    document.addEventListener('keydown', function (event) {
        if (event.key !== 'Enter') {
            return;
        }
        var input = event.target;
        if (!input.matches || !input.matches('#id_postcode_lookup, .venue-postcode-lookup-input')) {
            return;
        }
        event.preventDefault();
        var wrap = input.closest('.venue-postcode-lookup-wrap');
        var button = wrap ? wrap.querySelector('.venue-postcode-lookup-btn') : null;
        runPostcodeLookup(input, button);
    });

    document.addEventListener('change', function (event) {
        var results = event.target;
        if (!results.matches || !results.matches('.venue-postcode-lookup-results')) {
            return;
        }
        var payload = lookupPayloads.get(results) || {};
        var addresses = payload.addresses || [];
        var index = parseInt(results.value, 10);
        if (Number.isNaN(index) || !addresses[index]) {
            return;
        }
        applyVenueAddressSelection(addresses[index], payload);
        setPostcodeLookupMessage(
            results.closest('.col-sm-7, .flex-container') || findPostcodeFieldContainer(results),
            'Address and map coordinates updated.',
            'success',
        );
    });
})();

/**
 * Venue admin: draggable map pin synced with latitude / longitude fields.
 */
(function () {
    'use strict';

    var UK_CENTER = { lat: 54.7024, lng: -3.2766 };
    var DEFAULT_ZOOM = 6;
    var DETAIL_ZOOM = 15;
    var mapState = null;
    var updatingFromMap = false;

    function parseCoord(value) {
        var num = parseFloat((value || '').trim());
        return Number.isFinite(num) ? num : null;
    }

    function coordsFromInputs(latInput, lngInput) {
        var lat = parseCoord(latInput && latInput.value);
        var lng = parseCoord(lngInput && lngInput.value);
        if (lat == null || lng == null) {
            return null;
        }
        return { lat: lat, lng: lng };
    }

    function inputsAreEditable(latInput, lngInput) {
        return Boolean(
            latInput
            && lngInput
            && !latInput.disabled
            && !lngInput.disabled
            && !latInput.readOnly
            && !lngInput.readOnly,
        );
    }

    function setInputCoords(latInput, lngInput, lat, lng) {
        if (!latInput || !lngInput) {
            return;
        }
        updatingFromMap = true;
        latInput.value = lat.toFixed(6);
        lngInput.value = lng.toFixed(6);
        latInput.dispatchEvent(new Event('change', { bubbles: true }));
        lngInput.dispatchEvent(new Event('change', { bubbles: true }));
        updatingFromMap = false;
    }

    function ensureMarker(state, lat, lng, editable) {
        if (!state.marker) {
            state.marker = L.marker([lat, lng], { draggable: editable }).addTo(state.map);
            if (editable) {
                state.marker.on('dragend', function () {
                    var pos = state.marker.getLatLng();
                    setInputCoords(state.latInput, state.lngInput, pos.lat, pos.lng);
                });
            }
            return;
        }
        state.marker.setLatLng([lat, lng]);
        if (state.marker.dragging) {
            if (editable) {
                state.marker.dragging.enable();
            } else {
                state.marker.dragging.disable();
            }
        }
    }

    function setMapCoords(lat, lng, options) {
        if (!mapState || !mapState.map) {
            return;
        }
        var editable = inputsAreEditable(mapState.latInput, mapState.lngInput);
        ensureMarker(mapState, lat, lng, editable);
        if (options && options.pan) {
            mapState.map.setView([lat, lng], DETAIL_ZOOM);
        }
    }

    function syncMapFromInputs() {
        if (!mapState || updatingFromMap) {
            return;
        }
        var coords = coordsFromInputs(mapState.latInput, mapState.lngInput);
        if (!coords) {
            return;
        }
        var editable = inputsAreEditable(mapState.latInput, mapState.lngInput);
        ensureMarker(mapState, coords.lat, coords.lng, editable);
        mapState.map.setView([coords.lat, coords.lng], mapState.map.getZoom());
    }

    function initVenueLocationMap() {
        if (mapState || typeof L === 'undefined') {
            return;
        }

        var latInput = document.getElementById('id_latitude');
        var lngInput = document.getElementById('id_longitude');
        if (!latInput || !lngInput) {
            return;
        }

        var longitudeField = document.querySelector('.field-longitude');
        if (!longitudeField || document.getElementById('venue-location-map')) {
            return;
        }

        var row = document.createElement('div');
        row.className = 'form-group field-venue_location_map row';

        var label = document.createElement('label');
        label.className = 'col-sm-3 text-left';
        label.textContent = 'Map';

        var column = document.createElement('div');
        column.className = 'col-sm-7';

        var mapElement = document.createElement('div');
        mapElement.id = 'venue-location-map';
        mapElement.className = 'venue-location-map';

        var help = document.createElement('p');
        help.className = 'venue-location-map-help';
        help.textContent = inputsAreEditable(latInput, lngInput)
            ? 'Drag the pin to set latitude and longitude.'
            : 'Venue location on the map.';

        column.appendChild(mapElement);
        column.appendChild(help);
        row.appendChild(label);
        row.appendChild(column);
        longitudeField.insertAdjacentElement('afterend', row);

        var coords = coordsFromInputs(latInput, lngInput);
        var center = coords || UK_CENTER;
        var zoom = coords ? DETAIL_ZOOM : DEFAULT_ZOOM;
        var editable = inputsAreEditable(latInput, lngInput);

        var map = L.map(mapElement, { scrollWheelZoom: editable }).setView([center.lat, center.lng], zoom);
        L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
            attribution: (
                '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> '
                + 'contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
            ),
            subdomains: 'abcd',
            maxZoom: 19,
        }).addTo(map);

        mapState = {
            map: map,
            marker: null,
            latInput: latInput,
            lngInput: lngInput,
        };

        if (coords) {
            ensureMarker(mapState, coords.lat, coords.lng, editable);
        }

        if (editable) {
            help.textContent = coords
                ? 'Drag the pin to set latitude and longitude.'
                : 'Click the map or use postcode lookup to place the pin.';

            map.on('click', function (event) {
                ensureMarker(mapState, event.latlng.lat, event.latlng.lng, true);
                setInputCoords(latInput, lngInput, event.latlng.lat, event.latlng.lng);
                help.textContent = 'Drag the pin to set latitude and longitude.';
            });

            latInput.addEventListener('input', syncMapFromInputs);
            latInput.addEventListener('change', syncMapFromInputs);
            lngInput.addEventListener('input', syncMapFromInputs);
            lngInput.addEventListener('change', syncMapFromInputs);
        }

        document.addEventListener('gdVenueCoordsChanged', function (event) {
            var detail = (event && event.detail) || {};
            if (!Number.isFinite(detail.latitude) || !Number.isFinite(detail.longitude)) {
                syncMapFromInputs();
                return;
            }
            setInputCoords(latInput, lngInput, detail.latitude, detail.longitude);
            setMapCoords(detail.latitude, detail.longitude, { pan: Boolean(detail.pan) });
        });

        window.setTimeout(function () {
            map.invalidateSize();
        }, 0);
        window.setTimeout(function () {
            map.invalidateSize();
        }, 300);
    }

    function bootVenueLocationMap() {
        initVenueLocationMap();
        if (!mapState && typeof L === 'undefined') {
            window.setTimeout(bootVenueLocationMap, 100);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bootVenueLocationMap);
    } else {
        bootVenueLocationMap();
    }
    window.addEventListener('load', bootVenueLocationMap);
})();

/**
 * Venue admin: Jazzmin Select2 treats duplicate numeric option values as one
 * (e.g. region id 6 and user id 6). Keep venue FK/status fields on native selects.
 */
(function ($) {
    'use strict';

    if (!$) {
        return;
    }

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

    $(document).on('formset:added', function () {
        patchSelect2();
        setTimeout(destroyVenueSelect2, 0);
    });
})(window.django && django.jQuery ? django.jQuery : window.jQuery);
