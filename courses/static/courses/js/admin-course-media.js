(function() {
    'use strict';

    function toggleMediaFields(row) {
        var mediaTypeSelect = row.querySelector('select[id*="media_type"]');
        if (!mediaTypeSelect) return;

        var mediaType = mediaTypeSelect.value;
        var imageCell = row.querySelector('.field-image');
        var videoFileCell = row.querySelector('.field-video_file');
        var videoUrlCell = row.querySelector('.field-video_url');

        if (mediaType === 'image') {
            if (imageCell) imageCell.style.display = '';
            if (videoFileCell) videoFileCell.style.display = 'none';
            if (videoUrlCell) videoUrlCell.style.display = 'none';
        } else if (mediaType === 'video') {
            if (imageCell) imageCell.style.display = 'none';
            if (videoFileCell) videoFileCell.style.display = '';
            if (videoUrlCell) videoUrlCell.style.display = '';
        } else {
            if (imageCell) imageCell.style.display = '';
            if (videoFileCell) videoFileCell.style.display = '';
            if (videoUrlCell) videoUrlCell.style.display = '';
        }
    }

    function initCourseMediaInline() {
        document.querySelectorAll('tr.form-row').forEach(function(row) {
            var mediaTypeSelect = row.querySelector('select[id*="media_type"]');
            if (!mediaTypeSelect) return;

            toggleMediaFields(row);
            if (!mediaTypeSelect.dataset.listenerAdded) {
                mediaTypeSelect.dataset.listenerAdded = 'true';
                mediaTypeSelect.addEventListener('change', function() {
                    toggleMediaFields(row);
                });
            }
        });
    }

    function setupMutationObserver() {
        var container = document.getElementById('content');
        if (!container) return;

        var observer = new MutationObserver(function() {
            initCourseMediaInline();
        });
        observer.observe(container, { childList: true, subtree: true });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            initCourseMediaInline();
            setupMutationObserver();
        });
    } else {
        initCourseMediaInline();
        setupMutationObserver();
    }
})();
