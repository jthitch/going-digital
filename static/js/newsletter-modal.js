(function() {
    var cancelNewsletterFabAttention = null;

    function getCookie(name) {
        var match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
        return match ? decodeURIComponent(match[2]) : '';
    }

    function cancelFabAnimations(wrap) {
        wrap.getAnimations().forEach(function(animation) {
            animation.cancel();
        });
        wrap.querySelectorAll('.newsletter-fab, .newsletter-fab__icon').forEach(function(el) {
            el.getAnimations().forEach(function(animation) {
                animation.cancel();
            });
        });
    }

    function playNewsletterBounce(wrap) {
        if (!wrap || typeof wrap.animate !== 'function') {
            return;
        }
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            return;
        }

        wrap.classList.add('newsletter-fab-wrap--bounce');

        var fab = wrap.querySelector('.newsletter-fab');
        var icon = wrap.querySelector('.newsletter-fab__icon');
        var duration = 1300;
        var easing = 'cubic-bezier(0.34, 1.56, 0.64, 1)';

        var bounceAnim = wrap.animate([
            { transform: 'translate3d(0, 0, 0) scale(1)' },
            { transform: 'translate3d(0, -24px, 0) scale(1.1)' },
            { transform: 'translate3d(0, 0, 0) scale(0.95)' },
            { transform: 'translate3d(0, -16px, 0) scale(1.06)' },
            { transform: 'translate3d(0, 0, 0) scale(0.98)' },
            { transform: 'translate3d(0, -8px, 0) scale(1.02)' },
            { transform: 'translate3d(0, 0, 0) scale(1)' },
        ], { duration: duration, easing: easing, fill: 'none' });

        if (fab) {
            fab.animate([
                { boxShadow: '0 8px 24px rgba(74, 158, 255, 0.35)' },
                { boxShadow: '0 22px 42px rgba(74, 158, 255, 0.62)' },
                { boxShadow: '0 8px 24px rgba(74, 158, 255, 0.35)' },
            ], { duration: duration, easing: 'ease-out', fill: 'none' });
        }

        if (icon) {
            icon.animate([
                { transform: 'rotate(0deg) scale(1)' },
                { transform: 'rotate(-16deg) scale(1.12)' },
                { transform: 'rotate(14deg) scale(1.06)' },
                { transform: 'rotate(-10deg) scale(1.04)' },
                { transform: 'rotate(0deg) scale(1)' },
            ], { duration: duration, easing: 'ease-in-out', fill: 'none' });
        }

        function finishBounce() {
            wrap.classList.remove('newsletter-fab-wrap--bounce');
            wrap.style.transform = '';
        }

        bounceAnim.onfinish = finishBounce;
        bounceAnim.oncancel = finishBounce;
        window.setTimeout(finishBounce, duration + 100);
    }

    function initNewsletterFabAttention() {
        var wrap = document.getElementById('newsletter-fab-wrap');
        if (!wrap) {
            return;
        }

        var dismissed = false;
        var attentionTimer = window.setTimeout(function() {
            if (dismissed) {
                return;
            }
            playNewsletterBounce(wrap);
        }, 3000);

        function dismissAttention() {
            if (dismissed) {
                return;
            }
            dismissed = true;
            window.clearTimeout(attentionTimer);
            cancelFabAnimations(wrap);
            wrap.classList.remove('newsletter-fab-wrap--bounce');
            wrap.style.transform = '';
        }

        cancelNewsletterFabAttention = dismissAttention;
    }

    function initNewsletterModal() {
        var modal = document.getElementById('newsletter-modal');
        var form = document.getElementById('newsletter-subscribe-form');
        if (!modal || !form) return;

        var panel = modal.querySelector('.newsletter-modal__panel');
        var errorEl = document.getElementById('newsletter-error');
        var successEl = document.getElementById('newsletter-success');
        var submitBtn = form.querySelector('.newsletter-modal__submit');
        var emailInput = form.querySelector('#newsletter-email');
        var previouslyFocused = null;

        function setMessage(el, text) {
            if (!el) return;
            if (text) {
                el.textContent = text;
                el.hidden = false;
            } else {
                el.textContent = '';
                el.hidden = true;
            }
        }

        function openModal() {
            if (cancelNewsletterFabAttention) {
                cancelNewsletterFabAttention();
            }
            previouslyFocused = document.activeElement;
            setMessage(errorEl, '');
            setMessage(successEl, '');
            modal.classList.add('is-open');
            modal.setAttribute('aria-hidden', 'false');
            document.body.classList.add('newsletter-modal-open');
            if (emailInput) emailInput.focus();
        }

        function closeModal() {
            modal.classList.remove('is-open');
            modal.setAttribute('aria-hidden', 'true');
            document.body.classList.remove('newsletter-modal-open');
            if (previouslyFocused && previouslyFocused.focus) {
                previouslyFocused.focus();
            }
        }

        document.querySelectorAll('[data-newsletter-open]').forEach(function(trigger) {
            trigger.addEventListener('click', openModal);
        });

        modal.querySelectorAll('[data-newsletter-close]').forEach(function(el) {
            el.addEventListener('click', closeModal);
        });

        modal.addEventListener('click', function(e) {
            if (e.target === modal.querySelector('.newsletter-modal__backdrop')) {
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
                    'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])'
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

        form.addEventListener('submit', function(e) {
            e.preventDefault();
            setMessage(errorEl, '');
            setMessage(successEl, '');

            var email = (emailInput && emailInput.value || '').trim();
            if (!email) {
                setMessage(errorEl, 'Please enter your email address.');
                return;
            }

            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.textContent = 'Subscribing…';
            }

            fetch(form.action, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken'),
                },
                body: JSON.stringify({ email: email }),
                credentials: 'same-origin',
            })
                .then(function(response) {
                    return response.json().then(function(data) {
                        return { ok: response.ok, data: data };
                    });
                })
                .then(function(result) {
                    if (result.ok && result.data.ok) {
                        setMessage(successEl, result.data.message || 'Thanks for subscribing!');
                        if (emailInput) emailInput.value = '';
                        return;
                    }
                    var message = result.data.message;
                    if (!message && result.data.errors && result.data.errors.email) {
                        message = result.data.errors.email[0].message;
                    }
                    setMessage(errorEl, message || 'Unable to subscribe. Please try again.');
                })
                .catch(function() {
                    setMessage(errorEl, 'Unable to subscribe. Please try again.');
                })
                .finally(function() {
                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.textContent = 'Subscribe';
                    }
                });
        });
    }

    function bootNewsletter() {
        initNewsletterModal();
        initNewsletterFabAttention();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bootNewsletter);
    } else {
        bootNewsletter();
    }
})();
