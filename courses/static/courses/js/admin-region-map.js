/**
 * Admin region map — contract territory polygons with gd_region assignments.
 */
(function () {
    'use strict';

    var UK_CENTER = [54.5, -3.5];
    var DEFAULT_ZOOM = 6;
    var COLORS = [
        '#2563eb', '#059669', '#d97706', '#7c3aed', '#db2777',
        '#0891b2', '#65a30d', '#ea580c', '#4f46e5', '#0d9488',
        '#c026d3', '#ca8a04', '#dc2626', '#0284c7', '#16a34a',
        '#9333ea', '#e11d48', '#0369a1', '#15803d', '#b45309',
    ];

    function readPayload() {
        var node = document.getElementById('gd-region-map-data');
        if (!node) {
            return null;
        }
        try {
            var payload = JSON.parse(node.textContent);
            if (typeof payload === 'string') {
                payload = JSON.parse(payload);
            }
            return payload;
        } catch (err) {
            return null;
        }
    }

    function escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function popupHtml(feature, changeUrlPrefix) {
        var users = feature.users || [];
        var usersHtml = '';
        if (users.length) {
            usersHtml = '<ul class="gd-region-map-popup__users">' + users.map(function (user) {
                var label = escapeHtml(user.label);
                if (user.user_type && user.user_type !== '—') {
                    label += ' <span>(' + escapeHtml(user.user_type) + ')</span>';
                }
                return '<li>' + label + '</li>';
            }).join('') + '</ul>';
        } else {
            usersHtml = '<p class="gd-region-map-popup__users">No assigned users</p>';
        }

        var adminLink = '';
        if (feature.region_id && changeUrlPrefix) {
            adminLink = '<a class="gd-region-map-popup__link" href="'
                + changeUrlPrefix + feature.region_id + '/change/">Edit region</a>';
        }

        var title = feature.region_name || feature.kml_name;
        if (!feature.matched) {
            title += ' (unmatched KML territory)';
        }

        return (
            '<div class="gd-region-map-popup">'
            + '<h3 class="gd-region-map-popup__title">' + escapeHtml(title) + '</h3>'
            + usersHtml
            + adminLink
            + '</div>'
        );
    }

    function usersSummary(users) {
        if (!users || !users.length) {
            return 'No assigned users';
        }
        if (users.length === 1) {
            return users[0].label;
        }
        return users.length + ' assigned users';
    }

    function initRegionMap() {
        var mapElement = document.getElementById('gd-region-map');
        var legendElement = document.getElementById('gd-region-map-legend');
        if (!mapElement || !legendElement || typeof L === 'undefined') {
            return;
        }

        var payload = readPayload();
        if (!payload || !payload.features) {
            mapElement.textContent = 'Region map data is unavailable.';
            return;
        }

        var map = L.map(mapElement, { scrollWheelZoom: true }).setView(UK_CENTER, DEFAULT_ZOOM);
        L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
            attribution: (
                '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> '
                + 'contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
            ),
            subdomains: 'abcd',
            maxZoom: 19,
        }).addTo(map);

        var layers = [];
        var bounds = [];
        var changeUrlPrefix = window.location.pathname.replace(/map\/$/, '');

        payload.features.forEach(function (feature, index) {
            if (!feature.coordinates || !feature.coordinates.length) {
                return;
            }

            var color = feature.matched
                ? COLORS[index % COLORS.length]
                : '#6c757d';
            var layer = L.polygon(feature.coordinates, {
                color: color,
                weight: 2,
                fillColor: color,
                fillOpacity: feature.matched ? 0.28 : 0.12,
            }).addTo(map);
            layer.bindPopup(popupHtml(feature, changeUrlPrefix));
            layers.push({ feature: feature, layer: layer, color: color });
            bounds.push(layer.getBounds());
        });

        if (bounds.length) {
            map.fitBounds(L.latLngBounds(bounds), { padding: [24, 24] });
        }

        layers.forEach(function (entry, index) {
            var feature = entry.feature;
            var button = document.createElement('button');
            button.type = 'button';
            button.className = 'gd-region-map-legend__item';
            button.innerHTML = (
                '<span class="gd-region-map-legend__swatch" style="background:'
                + entry.color + ';"></span>'
                + '<span class="gd-region-map-legend__text">'
                + '<span class="gd-region-map-legend__name">' + escapeHtml(feature.region_name || feature.kml_name) + '</span>'
                + '<span class="gd-region-map-legend__meta">' + escapeHtml(usersSummary(feature.users)) + '</span>'
                + '</span>'
            );
            button.addEventListener('click', function () {
                legendElement.querySelectorAll('.gd-region-map-legend__item').forEach(function (item) {
                    item.classList.remove('is-active');
                });
                button.classList.add('is-active');
                map.fitBounds(entry.layer.getBounds(), { padding: [48, 48], maxZoom: 10 });
                entry.layer.openPopup();
            });
            legendElement.appendChild(button);
        });

        var unmapped = payload.unmapped_regions || [];
        if (unmapped.length) {
            var unmappedWrap = document.getElementById('gd-region-map-unmapped');
            var unmappedList = document.getElementById('gd-region-map-unmapped-list');
            if (unmappedWrap && unmappedList) {
                unmappedWrap.hidden = false;
                unmapped.forEach(function (region) {
                    var item = document.createElement('li');
                    item.textContent = region.region_name + ' — ' + usersSummary(region.users);
                    unmappedList.appendChild(item);
                });
            }
        }

        window.setTimeout(function () {
            map.invalidateSize();
        }, 100);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initRegionMap);
    } else {
        initRegionMap();
    }
})();
