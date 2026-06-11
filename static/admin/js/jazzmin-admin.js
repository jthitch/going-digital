(function ($) {
    'use strict';

    /**
     * Jazzmin persists sidebar state in a jazzy_menu cookie. A stale "closed"
     * value collapses the sidebar on load. Default to expanded (AdminLTE 4).
     */
    function defaultSidebarOpen() {
        document.cookie = 'jazzy_menu=open; path=/; SameSite=Strict';
        $('body').removeClass('sidebar-collapse').addClass('sidebar-open');
    }

    $(document).ready(function () {
        if ($('body').hasClass('no-sidebar') || !$('#jazzy-sidebar').length) {
            return;
        }

        defaultSidebarOpen();
    });
})(jQuery);
