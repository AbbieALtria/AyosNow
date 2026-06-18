const apiBase = "/api/v1";

const state = {
    accessToken: localStorage.getItem("ayosnow_ops_access") || "",
    refreshToken: localStorage.getItem("ayosnow_ops_refresh") || "",
    bookings: [],
    complaints: [],
    providers: [],
    payouts: [],
    notifications: [],
    financeSummary: null,
    reconciliation: null,
    providerCache: new Map(),
    filters: {
        dispatch: { q: "", status: "" },
        complaints: { q: "", status: "" },
        providers: { q: "", status: "" },
        payouts: { q: "", status: "" },
    },
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
    qsa("[data-ops-view]").forEach((button) => button.classList.toggle("active", button.dataset.opsView === view));
    qs("#pageTitle").textContent = view === "login" ? "Operations login" : view === "providers" ? "Provider verification" : view === "complaints" ? "Complaints desk" : view === "finance" ? "Finance desk" : "Dispatch queue";
    setAlert("");
}

function saveTokens(data) {
    state.accessToken = data.access_token;
    state.refreshToken = data.refresh_token;
    localStorage.setItem("ayosnow_ops_access", state.accessToken);
    localStorage.setItem("ayosnow_ops_refresh", state.refreshToken);
    qs("#logoutButton").classList.remove("hidden");
}

function clearTokens() {
    state.accessToken = "";
    state.refreshToken = "";
    localStorage.removeItem("ayosnow_ops_access");
    localStorage.removeItem("ayosnow_ops_refresh");
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

function queryString(filters) {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
        if (value) params.set(key, value);
    });
    const query = params.toString();
    return query ? `?${query}` : "";
}

function readFilters(formId) {
    const data = serialize(qs(`#${formId}`));
    return { q: (data.q || "").trim(), status: data.status || "" };
}

function setResultCount(selector, count, noun) {
    qs(selector).textContent = `${count} ${noun}${count === 1 ? "" : "s"}`;
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

async function loadNotifications() {
    state.notifications = await api("/notifications");
    renderNotifications();
}

function renderNotifications() {
    const panel = qs("#notificationPanel");
    const list = qs("#notificationList");
    panel.classList.toggle("hidden", !state.accessToken);
    if (!state.notifications.length) {
        list.innerHTML = '<div class="empty slim">No notifications yet.</div>';
        return;
    }
    list.innerHTML = state.notifications.slice(0, 6).map((item) => `
        <article class="notification-item ${item.is_read ? "" : "unread"}">
            <div>
                <strong>${item.title}</strong>
                <span>${item.message}</span>
            </div>
            <time>${new Date(item.created_at).toLocaleString()}</time>
        </article>
    `).join("");
}

async function loadApprovedProviders(serviceItemId) {
    if (state.providerCache.has(serviceItemId)) {
        return state.providerCache.get(serviceItemId);
    }
    const providers = await api(`/admin/providers/approved?service_item_id=${serviceItemId}`);
    state.providerCache.set(serviceItemId, providers);
    return providers;
}

async function loadQueue() {
    state.bookings = await api(`/admin/dispatch/queue${queryString(state.filters.dispatch)}`);
    qs("#pendingCount").textContent = state.bookings.length;
    const providerLists = await Promise.all(state.bookings.map((booking) => loadApprovedProviders(booking.service_item)));
    const uniqueProviderIds = new Set(providerLists.flat().map((provider) => provider.id));
    qs("#providerCount").textContent = uniqueProviderIds.size;
    renderQueue(providerLists);
}

async function loadComplaints() {
    state.complaints = await api(`/admin/complaints${queryString(state.filters.complaints)}`);
    const open = state.complaints.filter((complaint) => !["resolved", "rejected"].includes(complaint.status));
    qs("#complaintCount").textContent = open.length;
    renderComplaints();
}

async function loadProviders() {
    state.providers = await api(`/admin/providers${queryString(state.filters.providers)}`);
    renderProviders();
}

async function loadFinance() {
    const [summary, payouts, reconciliation] = await Promise.all([
        api("/admin/finance/summary"),
        api(`/admin/payouts${queryString(state.filters.payouts)}`),
        api("/admin/finance/reconciliation"),
    ]);
    state.financeSummary = summary;
    state.payouts = payouts;
    state.reconciliation = reconciliation;
    qs("#payoutCount").textContent = payouts.filter((payout) => ["requested", "under_review", "approved"].includes(payout.status)).length;
    renderFinance();
}

async function updateComplaint(complaint, status, resolution, financialImpact) {
    await api(`/admin/complaints/${complaint.id}/update`, {
        method: "POST",
        body: JSON.stringify({
            status,
            resolution,
            financial_impact: financialImpact || "0",
        }),
    });
    await Promise.all([loadComplaints(), loadNotifications()]);
}

async function updateProvider(provider, status, reason) {
    await api(`/admin/providers/${provider.id}/verification`, {
        method: "POST",
        body: JSON.stringify({ status, reason }),
    });
    state.providerCache.clear();
    await Promise.all([loadProviders(), loadQueue(), loadNotifications()]);
}

async function updatePayout(payout, status, payoutReference, financeReason) {
    await api(`/admin/payouts/${payout.id}/update`, {
        method: "POST",
        body: JSON.stringify({
            status,
            payout_reference: payoutReference,
            finance_reason: financeReason,
        }),
    });
    await Promise.all([loadFinance(), loadNotifications()]);
}

function renderQueue(providerLists = []) {
    const list = qs("#queueList");
    setResultCount("#dispatchResultCount", state.bookings.length, "booking");
    if (!state.bookings.length) {
        list.innerHTML = '<div class="empty">No pending dispatch bookings. Create a customer booking, then refresh.</div>';
        return;
    }
    const template = qs("#bookingTemplate");
    list.innerHTML = "";
    state.bookings.forEach((booking, index) => {
        const providers = providerLists[index] || [];
        const node = template.content.firstElementChild.cloneNode(true);
        node.querySelector(".status-pill").textContent = booking.status.replaceAll("_", " ");
        node.querySelector("h4").textContent = booking.service_snapshot?.name || `Booking ${booking.id}`;
        node.querySelector(".booking-meta").textContent = `${booking.address_snapshot?.line1 || "No address"} - ${new Date(booking.requested_schedule).toLocaleString()} - ${booking.id}`;

        const select = node.querySelector('select[name="provider_id"]');
        select.innerHTML = providers.length
            ? providers.map((provider) => `<option value="${provider.id}">${provider.display_name} - ${provider.city_name}</option>`).join("")
            : '<option value="">No eligible providers</option>';
        select.disabled = !providers.length;

        node.querySelector(".assign-form").addEventListener("submit", async (event) => {
            event.preventDefault();
            try {
                const data = serialize(event.currentTarget);
                if (!data.provider_id) throw new Error("No eligible provider is available for this booking.");
                await api("/admin/dispatch/assign", {
                    method: "POST",
                    body: JSON.stringify({
                        booking_id: booking.id,
                        provider_id: data.provider_id,
                        reason: data.reason,
                    }),
                });
                await Promise.all([loadQueue(), loadNotifications()]);
            } catch (error) {
                setAlert(error.message);
            }
        });

        node.querySelector(".simulate-button").addEventListener("click", async () => {
            try {
                const result = await api("/admin/payments/simulate-capture", {
                    method: "POST",
                    body: JSON.stringify({ booking_id: booking.id }),
                });
                await loadNotifications();
                setAlert(`Payment ${result.status} for ${result.payment_id}`);
            } catch (error) {
                setAlert(error.message);
            }
        });

        node.querySelector(".timeline-button").addEventListener("click", async () => {
            try {
                const target = node.querySelector(".timeline-list");
                const events = await api(`/bookings/${booking.id}/timeline`);
                target.innerHTML = formatTimeline(events);
                target.classList.toggle("hidden");
            } catch (error) {
                setAlert(error.message);
            }
        });

        list.appendChild(node);
    });
}

function renderComplaints() {
    const list = qs("#complaintsList");
    setResultCount("#complaintResultCount", state.complaints.length, "complaint");
    if (!state.complaints.length) {
        list.innerHTML = '<div class="empty">No complaints yet.</div>';
        return;
    }
    const template = qs("#complaintTemplate");
    list.innerHTML = "";
    state.complaints.forEach((complaint) => {
        const node = template.content.firstElementChild.cloneNode(true);
        node.querySelector(".status-pill").textContent = complaint.status.replaceAll("_", " ");
        node.querySelector("h4").textContent = complaint.service_name || `Complaint ${complaint.id}`;
        node.querySelector(".booking-meta").textContent = `${complaint.category} - ${complaint.customer_name} - Booking ${complaint.booking} - ${complaint.description}`;
        const form = node.querySelector(".complaint-form");
        form.status.value = complaint.status;
        form.financial_impact.value = complaint.financial_impact || "0";
        form.resolution.value = complaint.resolution || "";
        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            try {
                const data = serialize(event.currentTarget);
                await updateComplaint(complaint, data.status, data.resolution, data.financial_impact || "0");
                setAlert("Complaint updated.");
            } catch (error) {
                setAlert(error.message);
            }
        });
        node.querySelectorAll(".quick-complaint-button").forEach((button) => {
            button.addEventListener("click", async () => {
                try {
                    await updateComplaint(complaint, button.dataset.complaintStatus, form.resolution.value || "Quick update", form.financial_impact.value || "0");
                    setAlert("Complaint updated.");
                } catch (error) {
                    setAlert(error.message);
                }
            });
        });
        node.querySelector(".timeline-button").addEventListener("click", async () => {
            try {
                const target = node.querySelector(".timeline-list");
                const events = await api(`/complaints/${complaint.id}/timeline`);
                target.innerHTML = formatTimeline(events);
                target.classList.toggle("hidden");
            } catch (error) {
                setAlert(error.message);
            }
        });
        list.appendChild(node);
    });
}

function renderProviders() {
    const list = qs("#providersList");
    setResultCount("#providerResultCount", state.providers.length, "provider");
    if (!state.providers.length) {
        list.innerHTML = '<div class="empty">No provider applications yet.</div>';
        return;
    }
    const template = qs("#providerTemplate");
    list.innerHTML = "";
    state.providers.forEach((provider) => {
        const node = template.content.firstElementChild.cloneNode(true);
        node.querySelector(".status-pill").textContent = provider.verification_status.replaceAll("_", " ");
        node.querySelector("h4").textContent = provider.display_name;
        node.querySelector(".booking-meta").textContent = `${provider.provider_type} - ${provider.city_name} - services: ${(provider.service_names || []).join(", ") || "none"} - coverage: ${(provider.coverage_city_names || []).join(", ") || "none"} - docs: ${provider.document_count} - bank: ${provider.has_bank_account ? "yes" : "no"}`;
        const form = node.querySelector(".provider-form");
        form.status.value = provider.verification_status;
        form.reason.value = provider.verification_reason || "";
        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            try {
                const data = serialize(event.currentTarget);
                await updateProvider(provider, data.status, data.reason);
                setAlert("Provider verification updated.");
            } catch (error) {
                setAlert(error.message);
            }
        });
        node.querySelectorAll(".quick-provider-button").forEach((button) => {
            button.addEventListener("click", async () => {
                try {
                    await updateProvider(provider, button.dataset.providerStatus, form.reason.value || "Quick verification update");
                    setAlert("Provider verification updated.");
                } catch (error) {
                    setAlert(error.message);
                }
            });
        });
        node.querySelector(".timeline-button").addEventListener("click", async () => {
            try {
                const target = node.querySelector(".timeline-list");
                const events = await api(`/providers/${provider.id}/timeline`);
                target.innerHTML = formatTimeline(events);
                target.classList.toggle("hidden");
            } catch (error) {
                setAlert(error.message);
            }
        });
        list.appendChild(node);
    });
}

function renderFinance() {
    const summary = state.financeSummary || {};
    qs("#capturedRevenue").textContent = money(summary.captured_revenue);
    qs("#providerEarnings").textContent = money(summary.provider_earnings);
    qs("#requestedPayouts").textContent = money(summary.payout_requested);
    qs("#releasedPayouts").textContent = money(summary.payout_released);
    qs("#walletAvailable").textContent = money(summary.wallet_available);
    qs("#walletHeld").textContent = money(summary.wallet_held);
    const reconciliationList = qs("#reconciliationList");
    const providerRows = state.reconciliation?.providers || [];
    if (!providerRows.length) {
        reconciliationList.innerHTML = '<div class="empty">No provider wallet rows yet.</div>';
    } else {
        reconciliationList.innerHTML = providerRows.map((provider) => `
            <article class="booking-card reconciliation-card">
                <div class="booking-main">
                    <span class="status-pill">${provider.active_payouts} active payouts</span>
                    <h4>${provider.provider_name}</h4>
                    <p class="booking-meta">Ledger entries: ${provider.ledger_entries}</p>
                </div>
                <div class="reconciliation-values">
                    <strong>${money(provider.available_balance)}</strong>
                    <span>available</span>
                    <strong>${money(provider.held_balance)}</strong>
                    <span>held</span>
                </div>
            </article>
        `).join("");
    }
    const list = qs("#payoutsList");
    setResultCount("#payoutResultCount", state.payouts.length, "payout");
    if (!state.payouts.length) {
        list.innerHTML = '<div class="empty">No payout requests yet.</div>';
        return;
    }
    const template = qs("#payoutTemplate");
    list.innerHTML = "";
    state.payouts.forEach((payout) => {
        const node = template.content.firstElementChild.cloneNode(true);
        node.querySelector(".status-pill").textContent = payout.status.replaceAll("_", " ");
        node.querySelector("h4").textContent = `${payout.provider_name} - ${money(payout.requested_amount, payout.currency)}`;
        node.querySelector(".booking-meta").textContent = `${payout.provider_notes || "No provider note"} - ${new Date(payout.created_at).toLocaleString()}`;
        const form = node.querySelector(".payout-form");
        form.status.value = payout.status;
        form.payout_reference.value = payout.payout_reference || "";
        form.finance_reason.value = payout.finance_reason || "";
        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            try {
                const data = serialize(event.currentTarget);
                await updatePayout(payout, data.status, data.payout_reference, data.finance_reason);
                setAlert("Payout updated.");
            } catch (error) {
                setAlert(error.message);
            }
        });
        node.querySelectorAll(".quick-payout-button").forEach((button) => {
            button.addEventListener("click", async () => {
                try {
                    await updatePayout(payout, button.dataset.payoutStatus, form.payout_reference.value || "", form.finance_reason.value || "Quick finance update");
                    setAlert("Payout updated.");
                } catch (error) {
                    setAlert(error.message);
                }
            });
        });
        node.querySelector(".timeline-button").addEventListener("click", async () => {
            try {
                const target = node.querySelector(".timeline-list");
                const events = await api(`/payouts/${payout.id}/timeline`);
                target.innerHTML = formatTimeline(events);
                target.classList.toggle("hidden");
            } catch (error) {
                setAlert(error.message);
            }
        });
        list.appendChild(node);
    });
}

async function afterLogin() {
    await Promise.all([loadQueue(), loadProviders(), loadComplaints(), loadFinance(), loadNotifications()]);
    setView("dispatch");
}

function bindEvents() {
    qs("#loginForm").addEventListener("submit", async (event) => {
        event.preventDefault();
        try {
            const result = await api("/auth/login", {
                method: "POST",
                body: JSON.stringify({ ...serialize(event.currentTarget), user_type: "admin" }),
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

    qs("#refreshButton").addEventListener("click", async () => {
        try {
            await Promise.all([loadQueue(), loadNotifications()]);
        } catch (error) {
            setAlert(error.message);
        }
    });

    qs("#refreshComplaintsButton").addEventListener("click", async () => {
        try {
            await Promise.all([loadComplaints(), loadNotifications()]);
        } catch (error) {
            setAlert(error.message);
        }
    });

    qs("#refreshProvidersButton").addEventListener("click", async () => {
        try {
            await Promise.all([loadProviders(), loadNotifications()]);
        } catch (error) {
            setAlert(error.message);
        }
    });

    qs("#refreshFinanceButton").addEventListener("click", async () => {
        try {
            await Promise.all([loadFinance(), loadNotifications()]);
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

    qs("#dispatchFilters").addEventListener("submit", async (event) => {
        event.preventDefault();
        try {
            state.filters.dispatch = readFilters("dispatchFilters");
            await loadQueue();
        } catch (error) {
            setAlert(error.message);
        }
    });

    qs("#complaintFilters").addEventListener("submit", async (event) => {
        event.preventDefault();
        try {
            state.filters.complaints = readFilters("complaintFilters");
            await loadComplaints();
        } catch (error) {
            setAlert(error.message);
        }
    });

    qs("#providerFilters").addEventListener("submit", async (event) => {
        event.preventDefault();
        try {
            state.filters.providers = readFilters("providerFilters");
            await loadProviders();
        } catch (error) {
            setAlert(error.message);
        }
    });

    qs("#payoutFilters").addEventListener("submit", async (event) => {
        event.preventDefault();
        try {
            state.filters.payouts = readFilters("payoutFilters");
            await loadFinance();
        } catch (error) {
            setAlert(error.message);
        }
    });

    qsa("[data-clear-filters]").forEach((button) => {
        button.addEventListener("click", async () => {
            const form = qs(`#${button.dataset.clearFilters}`);
            form.reset();
            try {
                if (button.dataset.clearFilters === "dispatchFilters") {
                    state.filters.dispatch = readFilters("dispatchFilters");
                    await loadQueue();
                }
                if (button.dataset.clearFilters === "complaintFilters") {
                    state.filters.complaints = readFilters("complaintFilters");
                    await loadComplaints();
                }
                if (button.dataset.clearFilters === "providerFilters") {
                    state.filters.providers = readFilters("providerFilters");
                    await loadProviders();
                }
                if (button.dataset.clearFilters === "payoutFilters") {
                    state.filters.payouts = readFilters("payoutFilters");
                    await loadFinance();
                }
            } catch (error) {
                setAlert(error.message);
            }
        });
    });

    qsa("[data-ops-view]").forEach((button) => {
        button.addEventListener("click", async () => {
            if (!state.accessToken) return setView("login");
            try {
                if (button.dataset.opsView === "dispatch") await loadQueue();
                if (button.dataset.opsView === "providers") await loadProviders();
                if (button.dataset.opsView === "complaints") await loadComplaints();
                if (button.dataset.opsView === "finance") await loadFinance();
                await loadNotifications();
                setView(button.dataset.opsView);
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
