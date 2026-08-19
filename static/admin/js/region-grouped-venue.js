/**
 * Dual-list venue picker with collapsible region headers.
 * Replaces Django FilteredSelectMultiple for VenueMultipleChoiceField widgets.
 */
(function () {
    'use strict';

    function optionValue(opt) {
        return opt.value;
    }

    function optionRegion(opt) {
        return (opt.getAttribute('data-region') || 'No region').trim() || 'No region';
    }

    function optionLabel(opt) {
        return (opt.getAttribute('data-venue-name') || opt.textContent || '').trim();
    }

    function optionSearchHaystack(opt) {
        return [
            opt.getAttribute('data-venue-name'),
            opt.getAttribute('data-location'),
            opt.getAttribute('data-owner'),
            optionRegion(opt),
            opt.textContent,
        ]
            .filter(Boolean)
            .join(' ')
            .toLowerCase();
    }

    function populateItemElement(li, opt) {
        const name = opt.getAttribute('data-venue-name') || (opt.textContent || '').trim();
        const location = (opt.getAttribute('data-location') || '').trim();
        const owner = (opt.getAttribute('data-owner') || '').trim();

        li.replaceChildren();
        const body = document.createElement('div');
        body.className = 'gd-venue-picker__item-body';

        const nameEl = document.createElement('div');
        nameEl.className = 'gd-venue-picker__item-name';
        nameEl.textContent = name;
        body.appendChild(nameEl);

        if (location) {
            const locEl = document.createElement('div');
            locEl.className = 'gd-venue-picker__item-location';
            locEl.textContent = location;
            body.appendChild(locEl);
        }

        if (owner) {
            const ownerRow = document.createElement('div');
            ownerRow.className = 'gd-venue-picker__item-owner';
            const badge = document.createElement('span');
            badge.className = 'gd-venue-picker__owner-badge';
            const label = document.createElement('span');
            label.className = 'gd-venue-picker__owner-label';
            label.textContent = 'Owned by';
            const ownerName = document.createElement('span');
            ownerName.className = 'gd-venue-picker__owner-name';
            ownerName.textContent = owner;
            badge.appendChild(label);
            badge.appendChild(ownerName);
            ownerRow.appendChild(badge);
            body.appendChild(ownerRow);
        }

        li.appendChild(body);
    }

    function destroySelect2IfPresent(select) {
        if (!window.jQuery) {
            return;
        }
        const $ = window.jQuery;
        const $select = $(select);
        if ($select.data('select2')) {
            $select.select2('destroy');
        }
        // Jazzmin may leave a Select2 chrome sibling after destroy / race.
        $select
            .siblings('.select2-container')
            .add($select.next('.select2-container'))
            .add($select.prev('.select2-container'))
            .remove();
        select.classList.add('select2-hidden-accessible');
        select.setAttribute('aria-hidden', 'true');
        select.style.setProperty('display', 'none', 'important');
    }

    function buildPicker(select) {
        if (select.dataset.gdVenuePickerInit === '1') {
            destroySelect2IfPresent(select);
            return;
        }
        select.dataset.gdVenuePickerInit = '1';
        destroySelect2IfPresent(select);

        const verbose = select.getAttribute('data-verbose-name') || 'venues';
        const wrap = document.createElement('div');
        wrap.className = 'gd-venue-picker';
        wrap.setAttribute('data-verbose-name', verbose);

        wrap.innerHTML = [
            '<div class="gd-venue-picker__col gd-venue-picker__col--available">',
            '  <div class="gd-venue-picker__heading">Available ' + verbose + '</div>',
            '  <input type="search" class="form-control form-control-sm gd-venue-picker__filter" placeholder="Filter…" aria-label="Filter available ' + verbose + '">',
            '  <div class="gd-venue-picker__list" data-side="available" role="listbox" aria-multiselectable="true"></div>',
            '</div>',
            '<div class="gd-venue-picker__actions">',
            '  <button type="button" class="btn btn-sm btn-outline-secondary gd-venue-picker__choose" title="Choose selected">&rarr;</button>',
            '  <button type="button" class="btn btn-sm btn-outline-secondary gd-venue-picker__remove" title="Remove selected">&larr;</button>',
            '</div>',
            '<div class="gd-venue-picker__col gd-venue-picker__col--chosen">',
            '  <div class="gd-venue-picker__heading">Chosen ' + verbose + '</div>',
            '  <input type="search" class="form-control form-control-sm gd-venue-picker__filter" placeholder="Filter…" aria-label="Filter chosen ' + verbose + '">',
            '  <div class="gd-venue-picker__list" data-side="chosen" role="listbox" aria-multiselectable="true"></div>',
            '</div>',
        ].join('');

        select.classList.add('gd-venue-picker__select');
        select.setAttribute('aria-hidden', 'true');
        select.tabIndex = -1;
        select.parentNode.insertBefore(wrap, select);
        wrap.appendChild(select);

        const availableList = wrap.querySelector('[data-side="available"]');
        const chosenList = wrap.querySelector('[data-side="chosen"]');
        const filters = wrap.querySelectorAll('.gd-venue-picker__filter');

        function selectedValues() {
            return new Set(
                Array.from(select.options)
                    .filter(function (opt) { return opt.selected; })
                    .map(optionValue)
            );
        }

        function groupOptions(side) {
            const chosen = selectedValues();
            const byRegion = {};
            Array.from(select.options).forEach(function (opt) {
                const isChosen = chosen.has(optionValue(opt));
                if (side === 'available' && isChosen) {
                    return;
                }
                if (side === 'chosen' && !isChosen) {
                    return;
                }
                const region = optionRegion(opt);
                if (!byRegion[region]) {
                    byRegion[region] = [];
                }
                byRegion[region].push(opt);
            });
            return byRegion;
        }

        function renderSide(listEl, side) {
            const filterInput = listEl.parentElement.querySelector('.gd-venue-picker__filter');
            const filter = (filterInput && filterInput.value || '').trim().toLowerCase();
            const byRegion = groupOptions(side);
            const regions = Object.keys(byRegion).sort(function (a, b) {
                return a.localeCompare(b);
            });

            listEl.innerHTML = '';
            if (!regions.length) {
                const empty = document.createElement('div');
                empty.className = 'gd-venue-picker__empty';
                empty.textContent = side === 'chosen' ? 'None chosen' : 'None available';
                listEl.appendChild(empty);
                return;
            }

            regions.forEach(function (region) {
                const opts = byRegion[region].filter(function (opt) {
                    if (!filter) {
                        return true;
                    }
                    return optionSearchHaystack(opt).indexOf(filter) !== -1;
                });
                if (!opts.length) {
                    return;
                }

                const group = document.createElement('div');
                group.className = 'gd-venue-picker__group';

                const collapsedKey = 'gdVenuePickerCollapsed:' + select.name + ':' + side + ':' + region;
                let collapsed = false;
                try {
                    collapsed = sessionStorage.getItem(collapsedKey) === '1';
                } catch (e) { /* ignore */ }

                const toggle = document.createElement('button');
                toggle.type = 'button';
                toggle.className = 'gd-venue-picker__group-toggle';
                toggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
                toggle.innerHTML = '<span class="gd-venue-picker__chevron" aria-hidden="true"></span>'
                    + '<span class="gd-venue-picker__group-label"></span>'
                    + '<span class="gd-venue-picker__group-count"></span>';
                toggle.querySelector('.gd-venue-picker__group-label').textContent = region;
                toggle.querySelector('.gd-venue-picker__group-count').textContent = String(opts.length);

                const items = document.createElement('ul');
                items.className = 'gd-venue-picker__items';
                if (collapsed) {
                    items.hidden = true;
                    group.classList.add('is-collapsed');
                }

                opts.forEach(function (opt) {
                    const li = document.createElement('li');
                    li.className = 'gd-venue-picker__item';
                    li.tabIndex = 0;
                    li.setAttribute('role', 'option');
                    li.setAttribute('aria-selected', 'false');
                    li.dataset.value = optionValue(opt);
                    populateItemElement(li, opt);
                    items.appendChild(li);
                });

                toggle.addEventListener('click', function () {
                    const open = toggle.getAttribute('aria-expanded') !== 'true';
                    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
                    items.hidden = !open;
                    group.classList.toggle('is-collapsed', !open);
                    try {
                        sessionStorage.setItem(collapsedKey, open ? '0' : '1');
                    } catch (e) { /* ignore */ }
                });

                group.appendChild(toggle);
                group.appendChild(items);
                listEl.appendChild(group);
            });
        }

        function render() {
            renderSide(availableList, 'available');
            renderSide(chosenList, 'chosen');
        }

        function move(fromSide, toChosen) {
            const listEl = fromSide === 'available' ? availableList : chosenList;
            const selected = listEl.querySelectorAll('.gd-venue-picker__item.is-selected');
            if (!selected.length) {
                return;
            }
            const values = new Set(Array.from(selected).map(function (el) { return el.dataset.value; }));
            Array.from(select.options).forEach(function (opt) {
                if (values.has(optionValue(opt))) {
                    opt.selected = toChosen;
                }
            });
            select.dispatchEvent(new Event('change', { bubbles: true }));
            render();
        }

        function toggleItem(item) {
            item.classList.toggle('is-selected');
            item.setAttribute('aria-selected', item.classList.contains('is-selected') ? 'true' : 'false');
        }

        wrap.addEventListener('click', function (e) {
            const item = e.target.closest('.gd-venue-picker__item');
            if (!item || !wrap.contains(item)) {
                return;
            }
            if (e.detail === 2) {
                const side = item.closest('[data-side]').dataset.side;
                item.classList.add('is-selected');
                if (side === 'available') {
                    move('available', true);
                } else {
                    move('chosen', false);
                }
                return;
            }
            if (!e.ctrlKey && !e.metaKey) {
                item.closest('.gd-venue-picker__list')
                    .querySelectorAll('.gd-venue-picker__item.is-selected')
                    .forEach(function (el) {
                        if (el !== item) {
                            el.classList.remove('is-selected');
                            el.setAttribute('aria-selected', 'false');
                        }
                    });
            }
            toggleItem(item);
        });

        wrap.addEventListener('keydown', function (e) {
            const item = e.target.closest('.gd-venue-picker__item');
            if (!item) {
                return;
            }
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                toggleItem(item);
            }
        });

        wrap.querySelector('.gd-venue-picker__choose').addEventListener('click', function () {
            move('available', true);
        });
        wrap.querySelector('.gd-venue-picker__remove').addEventListener('click', function () {
            move('chosen', false);
        });

        filters.forEach(function (input) {
            input.addEventListener('input', render);
        });

        render();
    }

    function initAll() {
        document.querySelectorAll('select.gd-region-grouped-venue').forEach(buildPicker);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAll);
    } else {
        initAll();
    }
    // Jazzmin applySelect2() runs on document.ready; re-hide after it.
    window.setTimeout(initAll, 0);
    window.setTimeout(initAll, 50);
    window.setTimeout(initAll, 250);
})();
