(function () {
    "use strict";

    const TOKEN_KEY = "ifc_auth_token";

    function getToken() {
        try {
            return localStorage.getItem(TOKEN_KEY);
        } catch (_) {
            return null;
        }
    }

    function setToken(token) {
        try {
            const prev = localStorage.getItem(TOKEN_KEY);
            localStorage.setItem(TOKEN_KEY, token);
            if (prev && prev !== token) {
                clearExtractionCache();
            }
        } catch (_) {
            // localStorage unavailable
        }
    }

    function clearToken() {
        try {
            localStorage.removeItem(TOKEN_KEY);
        } catch (_) {
            // localStorage unavailable
        }
    }

    function isAuthPage() {
        return (document.body && document.body.dataset.auth === "public")
            || window.location.pathname === "/login";
    }

    function loginUrl() {
        const next = encodeURIComponent(window.location.pathname + window.location.search);
        return `/login?next=${next}`;
    }

    function redirectToLogin() {
        if (isAuthPage()) return;
        window.location.href = loginUrl();
    }

    function ensureAuth() {
        if (!getToken()) {
            redirectToLogin();
        }
    }

    function isApiUrl(input) {
        if (!input) return false;
        if (typeof input === "string") {
            if (input.startsWith("/api")) return true;
            try {
                const url = new URL(input, window.location.origin);
                return url.origin === window.location.origin && url.pathname.startsWith("/api");
            } catch (_) {
                return false;
            }
        }
        if (input instanceof Request) {
            return isApiUrl(input.url);
        }
        return false;
    }

    const nativeFetch = window.fetch.bind(window);

    async function authFetch(input, init = {}) {
        let nextInit = init;
        if (isApiUrl(input)) {
            const headers = new Headers(init.headers || (input instanceof Request ? input.headers : undefined));
            const token = getToken();
            if (token && !headers.has("Authorization")) {
                headers.set("Authorization", `Bearer ${token}`);
            }
            nextInit = { ...init, headers };
        }
        const res = await nativeFetch(input, nextInit);
        if (res.status === 401 && !isAuthPage()) {
            clearToken();
            redirectToLogin();
        }
        return res;
    }

    function clearExtractionCache() {
        try {
            const req = indexedDB.deleteDatabase("ifc_analyzer_db");
            req.onsuccess = () => {};
            req.onerror = () => {};
        } catch (_) {}
    }

    window.authFetch = authFetch;
    window.getAuthToken = getToken;
    window.setAuthToken = setToken;
    window.clearAuthToken = clearToken;
    window.logout = function () {
        clearToken();
        clearExtractionCache();
        redirectToLogin();
    };
    window.fetch = authFetch;

    if (!isAuthPage()) {
        ensureAuth();
    }
})();
