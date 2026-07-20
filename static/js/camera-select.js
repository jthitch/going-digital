(function () {
    var UNKNOWN = (document.body && document.body.getAttribute('data-camera-unknown')) || '__unknown__';
    var OTHER = (document.body && document.body.getAttribute('data-camera-other')) || '__other__';

    function parseCatalog() {
        var node = document.getElementById('camera-catalog-data');
        if (!node) return [];
        try {
            return JSON.parse(node.textContent || '[]');
        } catch (err) {
            return [];
        }
    }

    function modelsForMake(catalog, makeId) {
        for (var i = 0; i < catalog.length; i += 1) {
            if (String(catalog[i].id) === String(makeId)) {
                return catalog[i].models || [];
            }
        }
        return [];
    }

    function setOptions(select, options, selected) {
        var html = '';
        options.forEach(function (opt) {
            html += '<option value="' + opt.value + '"' +
                (String(opt.value) === String(selected) ? ' selected' : '') +
                '>' + opt.label + '</option>';
        });
        select.innerHTML = html;
    }

    function toggleOther(wrap, showMake, showModel) {
        var row = wrap.querySelector('[data-camera-other-row]');
        var makeOther = wrap.querySelector('[data-camera-make-other-wrap]');
        var modelOther = wrap.querySelector('[data-camera-model-other-wrap]');
        if (makeOther) makeOther.hidden = !showMake;
        if (modelOther) modelOther.hidden = !showModel;
        if (row) row.hidden = !(showMake || showModel);
    }

    function syncGroup(wrap, catalog, preferModel) {
        var makeSelect = wrap.querySelector('[data-camera-make]');
        var modelSelect = wrap.querySelector('[data-camera-model]');
        if (!makeSelect || !modelSelect) return;

        var makeValue = makeSelect.value;
        var selectedModel = preferModel != null ? preferModel : modelSelect.value;

        if (makeValue === UNKNOWN) {
            setOptions(modelSelect, [{ value: UNKNOWN, label: 'Unknown' }], UNKNOWN);
            toggleOther(wrap, false, false);
            return;
        }

        var options = [
            { value: '', label: 'Select model' },
            { value: UNKNOWN, label: 'Unknown' },
        ];

        if (makeValue === OTHER) {
            options.push({ value: OTHER, label: 'Other' });
        } else if (makeValue) {
            modelsForMake(catalog, makeValue).forEach(function (model) {
                options.push({ value: String(model.id), label: model.name });
            });
            options.push({ value: OTHER, label: 'Other' });
        } else {
            options.push({ value: OTHER, label: 'Other' });
        }

        var keep = selectedModel;
        if (keep && !options.some(function (opt) { return String(opt.value) === String(keep); })) {
            keep = '';
        }
        setOptions(modelSelect, options, keep);
        toggleOther(wrap, makeValue === OTHER, modelSelect.value === OTHER);
    }

    function init() {
        var catalog = parseCatalog();
        document.querySelectorAll('[data-camera-select]').forEach(function (wrap) {
            var makeSelect = wrap.querySelector('[data-camera-make]');
            var modelSelect = wrap.querySelector('[data-camera-model]');
            if (!makeSelect || !modelSelect) return;

            var initialModel = modelSelect.getAttribute('data-initial-model') || modelSelect.value || '';
            syncGroup(wrap, catalog, initialModel);

            makeSelect.addEventListener('change', function () {
                syncGroup(wrap, catalog, '');
            });
            modelSelect.addEventListener('change', function () {
                toggleOther(
                    wrap,
                    makeSelect.value === OTHER,
                    modelSelect.value === OTHER
                );
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
