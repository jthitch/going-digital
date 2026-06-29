(function () {
    'use strict';

    var PX_PER_SECOND = 48;

    function initTicker(root) {
        var track = root.querySelector('[data-google-reviews-ticker-track]');
        var group = root.querySelector('[data-google-reviews-ticker-group]');

        if (!track || !group) {
            return;
        }

        var cards = group.querySelectorAll('.google-review-card');
        if (cards.length <= 1) {
            root.classList.add('is-static');
            return;
        }

        var clone = group.cloneNode(true);
        clone.setAttribute('aria-hidden', 'true');
        track.appendChild(clone);

        function setDuration() {
            var width = group.getBoundingClientRect().width;
            if (!width) {
                return;
            }
            var duration = Math.max(18, width / PX_PER_SECOND);
            track.style.setProperty('--google-reviews-ticker-duration', duration + 's');
        }

        setDuration();
        window.addEventListener('resize', setDuration);

        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            root.classList.add('is-reduced-motion');
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('[data-google-reviews-ticker]').forEach(initTicker);
    });
})();
