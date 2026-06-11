(function () {
    'use strict';

    function clamp(value, min, max) {
        return Math.min(max, Math.max(min, value));
    }

    function readNumber(input, fallback) {
        if (!input) {
            return fallback;
        }
        var value = parseInt(input.value, 10);
        return Number.isFinite(value) ? value : fallback;
    }

    function applyPreviewState(root, x, y, zoom) {
        var img = root.querySelector('[data-preview-img]');
        var focus = root.querySelector('[data-preview-focus]');
        var stage = root.querySelector('[data-preview-stage]');
        var viewport = root.querySelector('[data-preview-viewport]');
        var scale = clamp(zoom, 100, 200) / 100;
        if (stage) {
            stage.style.setProperty('--preview-zoom', String(scale));
            if (viewport) {
                var rect = viewport.getBoundingClientRect();
                var pad = Math.ceil(Math.max(rect.width, rect.height) * (scale - 1));
                stage.style.padding = pad > 0 ? pad + 'px' : '0';
            }
        }
        if (img) {
            img.style.objectPosition = x + '% ' + y + '%';
            img.style.transform = 'scale(' + scale + ')';
            img.style.transformOrigin = x + '% ' + y + '%';
        }
        if (focus) {
            focus.style.left = x + '%';
            focus.style.top = y + '%';
            focus.style.transform = 'translate(-50%, -50%)';
        }
    }

    function syncInputs(xInput, yInput, zoomInput, x, y, zoom) {
        if (xInput) {
            xInput.value = String(x);
        }
        if (yInput) {
            yInput.value = String(y);
        }
        if (zoomInput) {
            zoomInput.value = String(zoom);
        }
    }

    function refreshCourseCardPreview() {
        var root = document.getElementById('course-card-admin-preview');
        if (!root || typeof root._courseCardPreviewUpdate !== 'function') {
            return;
        }
        root._courseCardPreviewUpdate();
    }

    function initCourseCardPreview() {
        var root = document.getElementById('course-card-admin-preview');
        if (!root || root.dataset.previewBound === '1') {
            refreshCourseCardPreview();
            return;
        }

        var xInput = document.getElementById('id_card_image_focus_x');
        var yInput = document.getElementById('id_card_image_focus_y');
        var zoomInput = document.getElementById('id_card_image_zoom');
        var frame = root.querySelector('[data-preview-frame]');
        var viewport = root.querySelector('[data-preview-viewport]');
        var focus = root.querySelector('[data-preview-focus]');
        var dragging = false;

        function currentState() {
            return {
                x: readNumber(xInput, parseInt(root.dataset.focusX || '50', 10)),
                y: readNumber(yInput, parseInt(root.dataset.focusY || '50', 10)),
                zoom: readNumber(zoomInput, parseInt(root.dataset.zoom || '100', 10)),
            };
        }

        function updateFromInputs() {
            var state = currentState();
            applyPreviewState(root, state.x, state.y, state.zoom);
        }

        function setFromPoint(clientX, clientY) {
            var target = viewport || frame;
            if (!target) {
                return;
            }
            var rect = target.getBoundingClientRect();
            if (!rect.width || !rect.height) {
                return;
            }
            var x = clamp(Math.round(((clientX - rect.left) / rect.width) * 100), 0, 100);
            var y = clamp(Math.round(((clientY - rect.top) / rect.height) * 100), 0, 100);
            var state = currentState();
            syncInputs(xInput, yInput, zoomInput, x, y, state.zoom);
            applyPreviewState(root, x, y, state.zoom);
        }

        [xInput, yInput, zoomInput].forEach(function (input) {
            if (!input) {
                return;
            }
            input.addEventListener('input', updateFromInputs);
            input.addEventListener('change', updateFromInputs);
        });

        if (focus) {
            focus.addEventListener('pointerdown', function (event) {
                dragging = true;
                focus.setPointerCapture(event.pointerId);
                event.preventDefault();
            });
            focus.addEventListener('pointermove', function (event) {
                if (!dragging) {
                    return;
                }
                setFromPoint(event.clientX, event.clientY);
            });
            focus.addEventListener('pointerup', function (event) {
                dragging = false;
                try {
                    focus.releasePointerCapture(event.pointerId);
                } catch (err) {
                    /* ignore */
                }
            });
        }

        if (frame) {
            frame.addEventListener('pointerdown', function (event) {
                if (event.target === focus || focus.contains(event.target)) {
                    return;
                }
                setFromPoint(event.clientX, event.clientY);
            });
        }

        root._courseCardPreviewUpdate = updateFromInputs;
        root.dataset.previewBound = '1';
        updateFromInputs();
    }

    function bindCourseCardPreview() {
        initCourseCardPreview();
        window.addEventListener('resize', refreshCourseCardPreview);
        document.addEventListener('shown.bs.tab', refreshCourseCardPreview);
        document.addEventListener('click', function (event) {
            var tab = event.target.closest('[data-toggle="tab"], [data-bs-toggle="tab"]');
            if (!tab) {
                return;
            }
            window.setTimeout(refreshCourseCardPreview, 50);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bindCourseCardPreview);
    } else {
        bindCourseCardPreview();
    }
})();
