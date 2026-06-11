(function () {
    'use strict';

    var grid = null;
    var hoverCard = null;
    var pauseTimer = null;
    var canHover = window.matchMedia('(hover: hover) and (pointer: fine)').matches;
    var mobileLayout = window.matchMedia('(max-width: 767px)').matches;
    var inViewCards = new Set();

    function playCard(card) {
        var video = card.querySelector('.course-card-video');
        if (!video) {
            return;
        }
        window.clearTimeout(pauseTimer);
        card.classList.add('is-video-active');
        if (video.tagName === 'VIDEO') {
            video.muted = true;
            video.playsInline = true;
            video.setAttribute('muted', '');
            video.setAttribute('playsinline', '');

            function startPlayback() {
                var playPromise = video.play();
                if (playPromise && typeof playPromise.catch === 'function') {
                    playPromise.catch(function () {});
                }
            }

            if (video.readyState >= 2) {
                startPlayback();
            } else {
                video.addEventListener('canplay', startPlayback, { once: true });
                video.load();
            }
            return;
        }
        if (video.tagName === 'IFRAME') {
            var src = video.getAttribute('data-video-src');
            if (src && video.src !== src) {
                video.src = src;
            }
        }
    }

    function pauseCard(card) {
        var video = card.querySelector('.course-card-video');
        if (!video) {
            return;
        }
        card.classList.remove('is-video-active');
        if (video.tagName === 'VIDEO') {
            video.pause();
            try {
                video.currentTime = 0;
            } catch (err) {
                /* ignore */
            }
            return;
        }
        if (video.tagName === 'IFRAME') {
            video.removeAttribute('src');
        }
    }

    function schedulePause(card) {
        window.clearTimeout(pauseTimer);
        pauseTimer = window.setTimeout(function () {
            if (hoverCard === card) {
                hoverCard = null;
            }
            pauseCard(card);
        }, 120);
    }

    function bindHoverDelegation() {
        if (!grid || grid.dataset.videoHoverBound === '1') {
            return;
        }
        grid.dataset.videoHoverBound = '1';

        grid.addEventListener('mouseover', function (event) {
            var card = event.target.closest('.course-card--overlay[data-has-video]');
            if (!card || !grid.contains(card)) {
                return;
            }
            if (hoverCard === card) {
                return;
            }
            if (hoverCard) {
                pauseCard(hoverCard);
            }
            hoverCard = card;
            playCard(card);
        });

        grid.addEventListener('mouseout', function (event) {
            var card = event.target.closest('.course-card--overlay[data-has-video]');
            if (!card || hoverCard !== card) {
                return;
            }
            var related = event.relatedTarget;
            if (related && card.contains(related)) {
                return;
            }
            schedulePause(card);
        });
    }

    function bindInView(card) {
        if (card._courseCardVideoObserver) {
            return;
        }
        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting && entry.intersectionRatio >= 0.35) {
                    inViewCards.add(card);
                    playCard(card);
                } else if (inViewCards.has(card)) {
                    inViewCards.delete(card);
                    pauseCard(card);
                }
            });
        }, { threshold: [0, 0.2, 0.35, 0.55, 0.75, 1] });
        observer.observe(card);
        card._courseCardVideoObserver = observer;
    }

    function bindCard(card) {
        if (card.dataset.videoBound === '1') {
            return;
        }
        card.dataset.videoBound = '1';
        if (!canHover || mobileLayout) {
            bindInView(card);
        }
    }

    function initCourseCardVideos(root) {
        grid = document.getElementById('course-grid') || grid;
        var scope = root || document;
        if (scope.matches && scope.matches('.course-card--overlay[data-has-video]')) {
            bindCard(scope);
        }
        scope.querySelectorAll('.course-card--overlay[data-has-video]').forEach(bindCard);
        if (canHover && !mobileLayout) {
            bindHoverDelegation();
        }
    }

    window.initCourseCardVideos = initCourseCardVideos;

    function onReady() {
        initCourseCardVideos();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', onReady);
    } else {
        onReady();
    }
})();
