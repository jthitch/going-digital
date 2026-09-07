/**
 * CARTO Voyager raster tiles. Key from window.GD_BASEMAPS_API_KEY
 * (set via Django context / admin base template from BASEMAPS_API_KEY).
 */
(function (global) {
    'use strict';

    var TILE_PATH = 'https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png';
    var ATTRIBUTION = (
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> '
        + 'contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
    );

    function basemapsApiKey() {
        return String(global.GD_BASEMAPS_API_KEY || '').trim();
    }

    function basemapTileUrl() {
        var key = basemapsApiKey();
        if (!key) {
            return TILE_PATH;
        }
        return TILE_PATH + '?key=' + encodeURIComponent(key);
    }

    function addBasemapTileLayer(map) {
        if (!global.L || !map) {
            return null;
        }
        return global.L.tileLayer(basemapTileUrl(), {
            attribution: ATTRIBUTION,
            maxZoom: 20,
        }).addTo(map);
    }

    global.GDBasemaps = {
        tileUrl: basemapTileUrl,
        addTileLayer: addBasemapTileLayer,
        attribution: ATTRIBUTION,
    };
}(typeof window !== 'undefined' ? window : this));
