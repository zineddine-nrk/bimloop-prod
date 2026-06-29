/**
 * Layout partagé : sidebar + topbar injectés dans toutes les pages.
 *
 * Usage dans une page :
 *   <body>
 *     <div id="appShell"></div>          // marqueur où injecter sidebar/topbar
 *     <div id="appPage">...contenu...</div>
 *     <script src="/static/assets/layout.js"></script>
 *     <script>
 *       AppLayout.mount({
 *         active: "extraction",          // clé de l'item actif
 *         eyebrow: "Workspace",
 *         title: "Extraction de données",
 *         actions: `<button class="btn btn-primary">...</button>` // optionnel
 *       });
 *     </script>
 *   </body>
 */
(function () {
    "use strict";

    const NAV = [
        { key: "extraction", label: "Extraction",   icon: "file-search",      href: "/" },
        { key: "tracking",   label: "Tracking",     icon: "map-pin",          href: "/tracker" },
        { key: "viewer",     label: "3D Viewer",    icon: "box",              href: "/viewer3d" },
    ];

    const NAV_BOTTOM = [
        { key: "settings",   label: "Settings",     icon: "settings",         href: "/settings" },
    ];

    function userSectionHtml() {
        return `
            <div class="app-sidebar-user" id="appSidebarUser">
                <div class="app-sidebar-user-avatar">
                    <i data-lucide="user"></i>
                </div>
                <div class="app-sidebar-user-info">
                    <span class="app-sidebar-user-email" id="appUserEmail">...</span>
                </div>
                <button class="app-sidebar-user-logout" id="appLogoutBtn" title="Déconnexion">
                    <i data-lucide="log-out"></i>
                </button>
            </div>`;
    }

    function navHtml(items, activeKey) {
        return items.map(item => `
            <a href="${item.href}" class="app-nav-link ${item.key === activeKey ? "is-active" : ""}" data-nav="${item.key}">
                <i data-lucide="${item.icon}"></i>
                <span>${item.label}</span>
                ${item.badge ? `<span class="nav-badge">${item.badge}</span>` : ""}
            </a>
        `).join("");
    }

    function sidebarHtml(activeKey) {
        return `
        <aside class="app-sidebar" id="appSidebar">
            <div class="app-sidebar-header">
                <div class="app-sidebar-logo">
                    <i data-lucide="building-2"></i>
                </div>
                <div class="app-sidebar-brand">
                    <span class="app-sidebar-brand-name">IFC Analyzer</span>
                    <span class="app-sidebar-brand-sub">BIM Platform</span>
                </div>
            </div>
            <nav class="app-sidebar-nav">
                <div class="app-sidebar-section-label">Workspace</div>
                ${navHtml(NAV, activeKey)}
                <div class="app-sidebar-section-label" style="margin-top: 16px;">Configuration</div>
                ${navHtml(NAV_BOTTOM, activeKey)}
            </nav>
            <div class="app-sidebar-footer">
                ${userSectionHtml()}
            </div>
        </aside>`;
    }

    function topbarHtml({ eyebrow, title, actions }) {
        return `
        <header class="app-topbar">
            <div class="app-topbar-title">
                ${eyebrow ? `<span class="app-topbar-eyebrow">${eyebrow}</span>` : ""}
                <span class="app-topbar-h1">${title || ""}</span>
            </div>
            <div class="app-topbar-actions" id="appTopbarActions">
                ${actions || ""}
            </div>
        </header>`;
    }

    /**
     * Monte la sidebar + topbar dans la page.
     * @param {{active: string, eyebrow?: string, title?: string, actions?: string}} opts
     */
    function mount(opts = {}) {
        const { active = "", eyebrow = "", title = "", actions = "" } = opts;

        // Le shell wrap le body : on cherche un élément #appShell
        // sinon on enveloppe automatiquement le contenu actuel.
        let shell = document.getElementById("appShell");
        if (!shell) {
            // Auto-wrap : prend le contenu actuel du body et l'enveloppe dans la coquille
            const existingChildren = Array.from(document.body.children).filter(
                c => c.tagName !== "SCRIPT"
            );
            shell = document.createElement("div");
            shell.id = "appShell";
            shell.className = "app-shell";

            const content = document.createElement("div");
            content.className = "app-content";

            const page = document.createElement("main");
            page.className = "app-page";
            page.id = "appPage";

            existingChildren.forEach(c => page.appendChild(c));
            content.appendChild(page);

            shell.innerHTML = sidebarHtml(active);
            shell.appendChild(content);
            // Insertion topbar avant le main
            const topbarWrap = document.createElement("div");
            topbarWrap.innerHTML = topbarHtml({ eyebrow, title, actions });
            content.insertBefore(topbarWrap.firstElementChild, page);

            document.body.insertBefore(shell, document.body.firstChild);
        } else {
            // Mode manuel : l'utilisateur a déjà la structure shell
            shell.classList.add("app-shell");
            const sidebarTpl = document.createElement("div");
            sidebarTpl.innerHTML = sidebarHtml(active);
            shell.insertBefore(sidebarTpl.firstElementChild, shell.firstChild);

            const content = shell.querySelector(".app-content") || shell.children[1];
            if (content) {
                const topbarTpl = document.createElement("div");
                topbarTpl.innerHTML = topbarHtml({ eyebrow, title, actions });
                content.insertBefore(topbarTpl.firstElementChild, content.firstChild);
            }
        }

        // Refresh icons Lucide si dispo
        if (window.lucide) window.lucide.createIcons();

        // Charger infos utilisateur
        fetchUserInfo();

        // Brancher le bouton logout
        setupLogout();
    }

    async function fetchUserInfo() {
        try {
            const res = await fetch("/api/auth/me");
            if (!res.ok) return;
            const user = await res.json();
            const emailEl = document.getElementById("appUserEmail");
            if (emailEl) {
                emailEl.textContent = user.email;
                emailEl.title = user.role === "admin" ? "Admin" : "Utilisateur";
            }
        } catch (_) {}
    }

    function setupLogout() {
        const btn = document.getElementById("appLogoutBtn");
        if (btn) {
            btn.addEventListener("click", () => {
                if (window.logout) window.logout();
            });
        }
    }

    /** Met à jour les actions de la topbar dynamiquement */
    function setActions(html) {
        const slot = document.getElementById("appTopbarActions");
        if (slot) {
            slot.innerHTML = html;
            if (window.lucide) window.lucide.createIcons();
        }
    }

    window.AppLayout = { mount, setActions };
})();
