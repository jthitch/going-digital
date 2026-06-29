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

    function bgSizeForZoom(zoom) {
        var zoomPct = clamp(zoom, 100, 200);
        var imageSize = zoomPct <= 100 ? 'cover' : zoomPct + '%';
        return '100% 100%, ' + imageSize;
    }

    function previewInputs(root) {
        var variant = root.dataset.variant;
        if (variant === 'mobile') {
            return {
                xInput: document.getElementById('id_mobile_focus_x'),
                yInput: document.getElementById('id_mobile_focus_y'),
                zoomInput: document.getElementById('id_mobile_zoom'),
            };
        }
        return {
            xInput: document.getElementById('id_desktop_focus_x'),
            yInput: document.getElementById('id_desktop_focus_y'),
            zoomInput: document.getElementById('id_desktop_zoom'),
        };
    }

    function imageUrlFor(root) {
        return root.dataset.imageUrl || root.dataset.defaultImageUrl || '';
    }

    function applyPreviewState(root, x, y, zoom) {
        var panel = root.querySelector('[data-preview-viewport]');
        var focus = root.querySelector('[data-preview-focus]');
        var url = imageUrlFor(root);
        if (panel) {
            panel.style.setProperty('--newsletter-preview-bg', url ? "url('" + url + "')" : 'none');
            panel.style.backgroundPosition = x + '% ' + y + '%';
            panel.style.backgroundSize = bgSizeForZoom(zoom);
        }
        if (focus) {
            focus.style.left = x + '%';
            focus.style.top = y + '%';
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

    function refreshAllPreviews() {
        document.querySelectorAll('.newsletter-admin-preview').forEach(function (root) {
            if (typeof root._newsletterPreviewUpdate === 'function') {
                root._newsletterPreviewUpdate();
            }
        });
    }

    function initNewsletterPreview(root) {
        if (!root || root.dataset.previewBound === '1') {
            if (root && typeof root._newsletterPreviewUpdate === 'function') {
                root._newsletterPreviewUpdate();
            }
            return;
        }

        var inputs = previewInputs(root);
        var xInput = inputs.xInput;
        var yInput = inputs.yInput;
        var zoomInput = inputs.zoomInput;
        var frame = root.querySelector('[data-preview-frame]');
        var panel = root.querySelector('[data-preview-viewport]');
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
            var target = panel || frame;
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

        function startDrag(event) {
            dragging = true;
            if (frame && frame.setPointerCapture) {
                frame.setPointerCapture(event.pointerId);
            }
            setFromPoint(event.clientX, event.clientY);
            event.preventDefault();
        }

        function moveDrag(event) {
            if (!dragging) {
                return;
            }
            setFromPoint(event.clientX, event.clientY);
        }

        function endDrag(event) {
            if (!dragging) {
                return;
            }
            dragging = false;
            if (frame && frame.releasePointerCapture) {
                try {
                    frame.releasePointerCapture(event.pointerId);
                } catch (err) {
                    /* ignore */
                }
            }
        }

        if (focus) {
            focus.addEventListener('pointerdown', function (event) {
                dragging = true;
                focus.setPointerCapture(event.pointerId);
                event.preventDefault();
                event.stopPropagation();
            });
            focus.addEventListener('pointermove', moveDrag);
            focus.addEventListener('pointerup', endDrag);
            focus.addEventListener('pointercancel', endDrag);
        }

        if (frame) {
            frame.addEventListener('pointerdown', function (event) {
                if (focus && (event.target === focus || focus.contains(event.target))) {
                    return;
                }
                startDrag(event);
            });
            frame.addEventListener('pointermove', moveDrag);
            frame.addEventListener('pointerup', endDrag);
            frame.addEventListener('pointercancel', endDrag);
        }

        root._newsletterPreviewUpdate = updateFromInputs;
        root.dataset.previewBound = '1';
        updateFromInputs();
    }

    function bindImageUpload() {
        var imageInput = document.getElementById('id_image');
        if (!imageInput || imageInput.dataset.newsletterPreviewBound === '1') {
            return;
        }
        imageInput.dataset.newsletterPreviewBound = '1';
        imageInput.addEventListener('change', function () {
            var file = imageInput.files && imageInput.files[0];
            document.querySelectorAll('.newsletter-admin-preview').forEach(function (root) {
                if (file) {
                    if (root._newsletterPreviewObjectUrl) {
                        URL.revokeObjectURL(root._newsletterPreviewObjectUrl);
                    }
                    var objectUrl = URL.createObjectURL(file);
                    root._newsletterPreviewObjectUrl = objectUrl;
                    root.dataset.imageUrl = objectUrl;
                } else {
                    root.dataset.imageUrl = root.dataset.defaultImageUrl || '';
                }
                if (typeof root._newsletterPreviewUpdate === 'function') {
                    root._newsletterPreviewUpdate();
                }
            });
        });
    }

    function initNewsletterModalAdmin() {
        document.querySelectorAll('.newsletter-admin-preview').forEach(initNewsletterPreview);
        bindImageUpload();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initNewsletterModalAdmin);
    } else {
        initNewsletterModalAdmin();
    }

    window.addEventListener('resize', refreshAllPreviews);
})();
