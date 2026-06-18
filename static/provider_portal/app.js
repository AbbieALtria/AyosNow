const apiBase = "/api/v1";

const state = {
    accessToken: localStorage.getItem("ayosnow_provider_access") || "",
    refreshToken: localStorage.getItem("ayosnow_provider_refresh") || "",
    jobs: [],
    wallet: null,
    payouts: [],
    notifications: [],
    profile: null,
};

function qs(selector) {
    return document.querySelector(selector);
}

function qsa(selector) {
    return Array.from(document.querySelectorAll(selector));
}

function setAlert(message) {
    const alert = qs("#alert");
    alert.textContent = message || "";
    alert.classList.toggle("hidden", !message);
}

function setView(view) {
    qsa("[data-view]").forEach((panel) => panel.classList.toggle("hidden", panel.dataset.view !== view));
    qsa("[data-view-button]").forEach((button) => button.classList.toggle("active", button.dataset.viewButton === view));
    qs("#pageTitle").textContent = view === "login" ? "Provider login" : view === "wallet" ? "Wallet" : view === "profile" ? "Provider profile" : "Assigned jobs";
    setAlert("");
}

function saveTokens(data) {
    state.accessToken = data.access_token;
    state.refreshToken = data.refresh_token;
    localStorage.setItem("ayosnow_provider_access", state.accessToken);
    localStorage.setItem("ayosnow_provider_refresh", state.refreshToken);
    qs("#logoutButton").classList.remove("hidden");
}

function clearTokens() {
    state.accessToken = "";
    state.refreshToken = "";
    localStorage.removeItem("ayosnow_provider_access");
    localStorage.removeItem("ayosnow_provider_refresh");
    qs("#logoutButton").classList.add("hidden");
}

async function api(path, options = {}) {
    const headers = {
        "Content-Type": "application/json",
        ...(options.headers || {}),
    };
    if (state.accessToken && !path.startsWith("/auth/")) {
        headers.Authorization = `Bearer ${state.accessToken}`;
    }
    const response = await fetch(`${apiBase}${path}`, { ...options, headers });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.success === false) {
        throw new Error(payload.error?.message || `Request failed (${response.status})`);
    }
    return payload.data;
}

function serialize(form) {
    return Object.fromEntries(new FormData(form).entries());
}

function money(value, currency = "PHP") {
    return `${currency} ${Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

async function loadJobs() {
    state.jobs = await api("/providers/jobs");
    renderJobs();
}

async function loadWallet() {
    const [wallet, payouts] = await Promise.all([
        api("/providers/wallet"),
        api("/providers/payouts/history"),
    ]);
    state.wallet = wallet;
    state.payouts = payouts;
    renderWallet();
}

async function loadNotifications() {
    state.notifications = await api("/notifications");
    renderNotifications();
}

async function loadProfile() {
    state.profile = await api("/providers/me");
    renderProfile();
}

function renderNotifications() {
    const panel = qs("#notificationPanel");
    const list = qs("#notificationList");
    panel.classList.toggle("hidden", !state.accessToken);
    if (!state.notifications.length) {
        list.innerHTML = '<div class="empty slim">No notifications yet.</div>';
        return;
    }
    list.innerHTML = state.notifications.slice(0, 5).map((item) => `
        <article class="notification-item ${item.is_read ? "" : "unread"}">
            <div>
                <strong>${item.title}</strong>
                <span>${item.message}</span>
            </div>
            <time>${new Date(item.created_at).toLocaleString()}</time>
        </article>
    `).join("");
}

function formatTimeline(events) {
    if (!events.length) return '<div class="empty slim">No timeline events yet.</div>';
    return events.map((event) => `
        <article class="timeline-item">
            <strong>${event.title}</strong>
            <span>${event.actor ? `${event.actor} - ` : ""}${new Date(event.created_at).toLocaleString()}</span>
        </article>
    `).join("");
}

async function renderProfile() {
    const profile = state.profile;
    if (!profile) return;
    qs("#profileSummary").innerHTML = `
        <article class="profile-card">
            <span class="status-pill">${profile.verification_status.replaceAll("_", " ")}</span>
            <h4>${profile.display_name}</h4>
            <p>${profile.provider_type} - ${profile.city_name}</p>
            <p>Services: ${(profile.service_names || []).join(", ") || "None yet"}</p>
            <p>Coverage: ${(profile.coverage_city_names || []).join(", ") || "None yet"}</p>
            <p>Documents: ${profile.document_count} - Bank details: ${profile.has_bank_account ? "on file" : "missing"}</p>
            ${profile.verification_reason ? `<p>Latest note: ${profile.verification_reason}</p>` : ""}
        </article>
    `;
    const timeline = await api(`/providers/${profile.id}/timeline`);
    qs("#profileTimeline").innerHTML = formatTimeline(timeline);
}

function renderJobs() {
    const list = qs("#jobsList");
    if (!state.jobs.length) {
        list.innerHTML = '<div class="empty">No assigned jobs yet. Dispatch a booking from admin, then refresh.</div>';
        return;
    }
    const template = qs("#jobTemplate");
    list.innerHTML = "";
    state.jobs.forEach((job) => {
        const node = template.content.firstElementChild.cloneNode(true);
        const complaintText = job.open_complaint_status ? ` - complaint: ${job.open_complaint_status.replaceAll("_", " ")}` : "";
        node.querySelector(".status-pill").textContent = job.status.replaceAll("_", " ");
        node.querySelector("h4").textContent = job.service_name || `Booking ${job.booking}`;
        node.querySelector(".job-meta").textContent = `Booking ${job.booking} - ${job.booking_status.replaceAll("_", " ")}${complaintText} - Assignment ${job.id}`;
        const acceptButton = node.querySelector(".accept-button");
        const completeButton = node.querySelector(".complete-button");
        const timelineButton = node.querySelector(".timeline-button");
        const timelineList = node.querySelector(".timeline-list");
        const completionForm = node.querySelector(".completion-form");

        acceptButton.disabled = job.status !== "assigned";
        completeButton.disabled = job.status !== "accepted";
        acceptButton.classList.toggle("hidden", job.status !== "assigned");
        completeButton.classList.toggle("hidden", job.status !== "accepted");

        acceptButton.addEventListener("click", async () => {
            try {
                await api(`/providers/jobs/${job.id}/accept`, { method: "POST" });
                await Promise.all([loadJobs(), loadNotifications()]);
            } catch (error) {
                setAlert(error.message);
            }
        });

        completeButton.addEventListener("click", () => {
            completionForm.classList.toggle("hidden");
        });

        timelineButton.addEventListener("click", async () => {
            try {
                const events = await api(`/bookings/${job.booking}/timeline`);
                timelineList.innerHTML = formatTimeline(events);
                timelineList.classList.toggle("hidden");
            } catch (error) {
                setAlert(error.message);
            }
        });

        completionForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            try {
                await api(`/providers/jobs/${job.id}/complete`, {
                    method: "POST",
                    body: JSON.stringify({
                        completion_notes: serialize(event.currentTarget).completion_notes,
                        evidence_urls: [],
                    }),
                });
                await Promise.all([loadJobs(), loadWallet(), loadNotifications()]);
            } catch (error) {
                setAlert(error.message);
            }
        });

        list.appendChild(node);
    });
}

function renderWallet() {
    if (!state.wallet) return;
    qs("#availableBalance").textContent = money(state.wallet.available_balance, state.wallet.currency);
    qs("#heldBalance").textContent = money(state.wallet.held_balance, state.wallet.currency);
    const payoutList = qs("#payoutList");
    if (!state.payouts.length) {
        payoutList.innerHTML = '<div class="empty">No payout requests yet.</div>';
    } else {
        payoutList.innerHTML = state.payouts.map((payout) => `
            <article class="ledger-row">
                <div>
                    <strong>${payout.status.replaceAll("_", " ")}</strong>
                    <span>${payout.provider_notes || "No note"} - ${new Date(payout.created_at).toLocaleString()}</span>
                    <button class="ghost mini-button payout-timeline-button" type="button" data-payout-timeline="${payout.id}">Timeline</button>
                </div>
                <strong>${money(payout.requested_amount, payout.currency)}</strong>
                <div class="timeline-list hidden" data-payout-timeline-for="${payout.id}"></div>
            </article>
        `).join("");
        qsa("[data-payout-timeline]").forEach((button) => {
            button.addEventListener("click", async () => {
                try {
                    const target = qs(`[data-payout-timeline-for="${button.dataset.payoutTimeline}"]`);
                    const events = await api(`/payouts/${button.dataset.payoutTimeline}/timeline`);
                    target.innerHTML = formatTimeline(events);
                    target.classList.toggle("hidden");
                } catch (error) {
                    setAlert(error.message);
                }
            });
        });
    }
    const list = qs("#ledgerList");
    const entries = state.wallet.recent_entries || [];
    if (!entries.length) {
        list.innerHTML = '<div class="empty">No wallet entries yet.</div>';
        return;
    }
    list.innerHTML = entries.map((entry) => `
        <article class="ledger-row">
            <div>
                <strong>${entry.entry_type.replaceAll("_", " ")}</strong>
                <span>${entry.direction} - ${new Date(entry.created_at).toLocaleString()}</span>
            </div>
            <strong>${money(entry.amount, entry.currency)}</strong>
        </article>
    `).join("");
}

async function afterLogin() {
    await Promise.all([loadProfile(), loadJobs(), loadWallet(), loadNotifications()]);
    setView("profile");
}

function bindEvents() {
    qs("#loginForm").addEventListener("submit", async (event) => {
        event.preventDefault();
        try {
            const data = serialize(event.currentTarget);
            const result = await api("/auth/login", {
                method: "POST",
                body: JSON.stringify({ ...data, user_type: "provider" }),
            });
            saveTokens(result);
            await afterLogin();
        } catch (error) {
            setAlert(error.message);
        }
    });

    qs("#logoutButton").addEventListener("click", () => {
        clearTokens();
        state.notifications = [];
        renderNotifications();
        setView("login");
    });

    qs("#refreshJobsButton").addEventListener("click", async () => {
        try {
            await Promise.all([loadJobs(), loadNotifications()]);
        } catch (error) {
            setAlert(error.message);
        }
    });

    qs("#refreshWalletButton").addEventListener("click", async () => {
        try {
            await Promise.all([loadWallet(), loadNotifications()]);
        } catch (error) {
            setAlert(error.message);
        }
    });

    qs("#refreshProfileButton").addEventListener("click", async () => {
        try {
            await Promise.all([loadProfile(), loadNotifications()]);
        } catch (error) {
            setAlert(error.message);
        }
    });

    qs("#refreshNotificationsButton").addEventListener("click", async () => {
        try {
            await loadNotifications();
        } catch (error) {
            setAlert(error.message);
        }
    });

    qs("#payoutForm").addEventListener("submit", async (event) => {
        event.preventDefault();
        try {
            const data = serialize(event.currentTarget);
            await api("/providers/payouts", {
                method: "POST",
                headers: { "Idempotency-Key": `payout-${crypto.randomUUID()}` },
                body: JSON.stringify({ amount: data.amount, notes: data.notes || "" }),
            });
            event.currentTarget.reset();
            await Promise.all([loadWallet(), loadNotifications()]);
            setAlert("Payout request submitted.");
        } catch (error) {
            setAlert(error.message);
        }
    });

    qsa("[data-view-button]").forEach((button) => {
        button.addEventListener("click", async () => {
            if (!state.accessToken) return setView("login");
            try {
                if (button.dataset.viewButton === "jobs") await loadJobs();
                if (button.dataset.viewButton === "wallet") await loadWallet();
                if (button.dataset.viewButton === "profile") await loadProfile();
                await loadNotifications();
                setView(button.dataset.viewButton);
            } catch (error) {
                setAlert(error.message);
            }
        });
    });
}

async function init() {
    bindEvents();
    qs("#logoutButton").classList.toggle("hidden", !state.accessToken);
    if (state.accessToken) {
        try {
            await afterLogin();
        } catch {
            clearTokens();
            setView("login");
        }
    } else {
        setView("login");
    }
}

init();
