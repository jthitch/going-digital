(function ($) {
    'use strict';

    /**
     * Jazzmin persists sidebar state in a jazzy_menu cookie. A stale "closed"
     * value makes staging render with sidebar-collapse while local often does not.
     * Default to an expanded sidebar on each page load.
     */
    function defaultSidebarOpen() {
        document.cookie = 'jazzy_menu=open; path=/; SameSite=Strict';
        $('body').removeClass('sidebar-collapse');
    }

    $(document).ready(function () {
        if ($('body').hasClass('no-sidebar') || !$('#jazzy-sidebar').length) {
            return;
        }

        defaultSidebarOpen();
    });
})(jQuery);
