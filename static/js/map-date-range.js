(function() {
    'use strict';

    function formatDisplayRange(start, end) {
        if (!start) return '';
        var opts = { day: 'numeric', month: 'short', year: 'numeric' };
        var a = start.toLocaleDateString('en-GB', opts);
        if (!end || start.getTime() === end.getTime()) return a;
        return a + ' – ' + end.toLocaleDateString('en-GB', opts);
    }

    function updateDisplay(wrap, selectedDates) {
        var displayEl = wrap.querySelector('.map-filter-date-display, .filter-date-range-display');
        if (!displayEl) return;
        var placeholder = displayEl.dataset.placeholder || 'Add dates';
        if (selectedDates.length >= 2) {
            displayEl.textContent = formatDisplayRange(selectedDates[0], selectedDates[1]);
            wrap.setAttribute('data-has-value', 'true');
        } else if (selectedDates.length === 1) {
            displayEl.textContent = formatDisplayRange(selectedDates[0], null);
            wrap.setAttribute('data-has-value', 'true');
        } else {
            displayEl.textContent = placeholder;
            wrap.removeAttribute('data-has-value');
        }
    }

    function initDateRangePicker(wrap) {
        if (!wrap || wrap.dataset.dateRangeInit === '1') return;
        if (typeof flatpickr === 'undefined') return;

        var fromInput = wrap.querySelector('input[name="date_from"], [data-filter-date-from]');
        var toInput = wrap.querySelector('input[name="date_to"], [data-filter-date-to]');
        var form = wrap.closest('form');
        var autoSubmit = wrap.dataset.autoSubmit !== 'false';
        var displayEl = wrap.querySelector('.map-filter-date-display, .filter-date-range-display');

        if (!fromInput || !toInput) return;
        if (displayEl && !displayEl.dataset.placeholder) {
            displayEl.dataset.placeholder = displayEl.textContent.trim() || 'Add dates';
        }

        var defaultDates = [];
        if (fromInput.value) defaultDates.push(fromInput.value);
        if (toInput.value) defaultDates.push(toInput.value);
        if (defaultDates.length) {
            wrap.setAttribute('data-has-value', 'true');
        }

        var showMonths = window.matchMedia('(min-width: 768px)').matches ? 2 : 1;
        var minDate = wrap.dataset.minDate || 'today';
        var maxDate = wrap.dataset.maxDate || null;

        function notifyChange() {
            wrap.dispatchEvent(new CustomEvent('gd:date-range-change', {
                bubbles: true,
                detail: {
                    from: fromInput.value,
                    to: toInput.value,
                },
            }));
        }

        // Flatpickr requires an input — attach off-screen, not in the visible UI
        var fpInput = document.createElement('input');
        fpInput.type = 'text';
        fpInput.setAttribute('aria-hidden', 'true');
        fpInput.tabIndex = -1;
        fpInput.className = 'map-date-range-fp-input';
        document.body.appendChild(fpInput);

        var fpOptions = {
            mode: 'range',
            dateFormat: 'Y-m-d',
            minDate: minDate,
            showMonths: showMonths,
            disableMobile: true,
            defaultDate: defaultDates.length ? defaultDates : null,
            locale: { firstDayOfWeek: 1 },
            clickOpens: false,
            positionElement: wrap,
            onChange: function(selectedDates) {
                if (selectedDates.length >= 1) {
                    fromInput.value = fp.formatDate(selectedDates[0], 'Y-m-d');
                } else {
                    fromInput.value = '';
                }
                if (selectedDates.length >= 2) {
                    toInput.value = fp.formatDate(selectedDates[1], 'Y-m-d');
                    updateDisplay(wrap, selectedDates);
                    if (autoSubmit && form) {
                        form.submit();
                    } else if (!autoSubmit) {
                        notifyChange();
                    }
                } else {
                    toInput.value = '';
                    updateDisplay(wrap, selectedDates);
                    if (!autoSubmit && selectedDates.length === 0) {
                        notifyChange();
                    }
                }
            },
            onClose: function(selectedDates) {
                if (selectedDates.length === 1) {
                    toInput.value = fromInput.value;
                    updateDisplay(wrap, [selectedDates[0], selectedDates[0]]);
                    if (!autoSubmit) {
                        notifyChange();
                    }
                }
            },
        };
        if (maxDate) {
            fpOptions.maxDate = maxDate;
        }

        var fp = flatpickr(fpInput, fpOptions);

        if (fp.selectedDates.length) {
            updateDisplay(wrap, fp.selectedDates);
        }

        function openPicker(e) {
            if (e) e.preventDefault();
            fp.open();
        }

        wrap.addEventListener('click', openPicker);
        wrap.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' || e.key === ' ') {
                openPicker(e);
            }
        });

        wrap.dataset.dateRangeInit = '1';
        wrap._flatpickr = fp;
    }

    window.initMapDateRangePickers = function(root) {
        var scope = root || document;
        scope.querySelectorAll('.map-date-range-wrap').forEach(initDateRangePicker);
    };
})();
