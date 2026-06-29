(function() {
    function initFbShareModal() {
        var modal = document.getElementById('fb-share-modal');
        if (!modal) return;

        var panel = modal.querySelector('.fb-share-modal__panel');
        var previouslyFocused = null;

        function setPaneVisibility(bookingRef) {
            var panes = modal.querySelectorAll('.fb-share-modal__pane');
            if (!panes.length) return;

            if (!bookingRef) {
                panes.forEach(function(pane) {
                    pane.hidden = false;
                });
                return;
            }

            panes.forEach(function(pane) {
                pane.hidden = pane.getAttribute('data-booking-ref') !== bookingRef;
            });
        }

        function openModal(bookingRef) {
            setPaneVisibility(bookingRef || '');
            previouslyFocused = document.activeElement;
            modal.classList.add('is-open');
            modal.setAttribute('aria-hidden', 'false');
            document.body.classList.add('fb-share-modal-open');
            var closeBtn = modal.querySelector('.fb-share-modal__close');
            if (closeBtn) closeBtn.focus();
        }

        function closeModal() {
            modal.classList.remove('is-open');
            modal.setAttribute('aria-hidden', 'true');
            document.body.classList.remove('fb-share-modal-open');
            if (previouslyFocused && previouslyFocused.focus) {
                previouslyFocused.focus();
            }
        }

        document.querySelectorAll('[data-fb-share-open]').forEach(function(trigger) {
            trigger.addEventListener('click', function() {
                openModal(trigger.getAttribute('data-booking-ref') || '');
            });
        });

        modal.querySelectorAll('[data-fb-share-close]').forEach(function(el) {
            el.addEventListener('click', closeModal);
        });

        modal.addEventListener('click', function(e) {
            if (e.target === modal.querySelector('.fb-share-modal__backdrop')) {
                closeModal();
            }
        });

        document.addEventListener('keydown', function(e) {
            if (!modal.classList.contains('is-open')) return;
            if (e.key === 'Escape') {
                e.preventDefault();
                closeModal();
            }
            if (e.key === 'Tab' && panel) {
                var focusable = panel.querySelectorAll(
                    'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])'
                );
                if (!focusable.length) return;
                var first = focusable[0];
                var last = focusable[focusable.length - 1];
                if (e.shiftKey && document.activeElement === first) {
                    e.preventDefault();
                    last.focus();
                } else if (!e.shiftKey && document.activeElement === last) {
                    e.preventDefault();
                    first.focus();
                }
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initFbShareModal);
    } else {
        initFbShareModal();
    }
})();
