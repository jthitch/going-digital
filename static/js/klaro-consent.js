/**
 * Klaro + Google Consent Mode v2 helpers.
 * Expects window.__GD_GTM_ID and window.dataLayer / gtag from the consent partial.
 */
(function () {
    'use strict';

    function gtag() {
        window.dataLayer = window.dataLayer || [];
        window.dataLayer.push(arguments);
    }

    function analyticsGranted(consents) {
        return !!(consents && consents['google-analytics']);
    }

    function applyGoogleConsent(consents) {
        var granted = analyticsGranted(consents);
        gtag('consent', 'update', {
            ad_storage: 'denied',
            ad_user_data: 'denied',
            ad_personalization: 'denied',
            analytics_storage: granted ? 'granted' : 'denied',
            functionality_storage: 'granted',
            personalization_storage: 'denied',
            security_storage: 'granted',
        });

        window.dataLayer = window.dataLayer || [];
        window.dataLayer.push({
            event: granted
                ? 'klaro-google-analytics-accepted'
                : 'klaro-google-analytics-declined',
            klaroAnalyticsConsent: granted,
        });
    }

    window.__gdApplyKlaroConsent = applyGoogleConsent;

    function watchKlaro() {
        if (!window.klaro || typeof window.klaro.getManager !== 'function') {
            return;
        }
        var manager = window.klaro.getManager(window.klaroConfig);
        if (!manager || typeof manager.watch !== 'function') {
            return;
        }
        // Restore consent for returning visitors (Klaro loads stored choices quietly).
        applyGoogleConsent(manager.consents || {});
        manager.watch({
            update: function (mgr, eventName, data) {
                if (eventName !== 'consents' && eventName !== 'saveConsents') {
                    return;
                }
                var consents =
                    (mgr && mgr.consents) ||
                    (data && data.consents) ||
                    data ||
                    {};
                applyGoogleConsent(consents);
            },
        });
    }

    function bindPreferencesLink() {
        document.querySelectorAll('[data-klaro-preferences]').forEach(function (el) {
            el.addEventListener('click', function (e) {
                if (window.klaro && typeof window.klaro.show === 'function') {
                    e.preventDefault();
                    window.klaro.show(undefined, true);
                }
            });
        });
    }

    function onReady(fn) {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', fn);
        } else {
            fn();
        }
    }

    onReady(function () {
        bindPreferencesLink();
        // Klaro may still be loading (defer); retry briefly.
        var tries = 0;
        (function waitForKlaro() {
            if (window.klaro) {
                watchKlaro();
                return;
            }
            tries += 1;
            if (tries < 40) {
                setTimeout(waitForKlaro, 50);
            }
        })();
    });
})();
