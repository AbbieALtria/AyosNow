const apiBase = "/api/v1";

const state = {
    accessToken: localStorage.getItem("ayosnow_access") || "",
    refreshToken: localStorage.getItem("ayosnow_refresh") || "",
    customer: null,
    addresses: [],
    bookings: [],
    categories: [],
    notifications: [],
    selectedService: null,
    selectedAddress: null,
    complaintBookingId: null,
    booking: null,
    otpToken: "",
};

const stepTitles = {
    auth: "Sign in or create account",
    service: "Choose a service",
    address: "Confirm service address",
    schedule: "Schedule the visit",
    confirm: "Booking request created",
    history: "My bookings",
    complaint: "Report issue",
};

const icons = {
    fixed: '<svg viewBox="0 0 24 24"><path d="M7 3h10a2 2 0 0 1 2 2v14l-4-2-3 2-3-2-4 2V5a2 2 0 0 1 2-2Zm2 5h6V6H9v2Zm0 4h6v-2H9v2Zm0 4h4v-2H9v2Z"/></svg>',
    estimated: '<svg viewBox="0 0 24 24"><path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2Zm1 11h4v2h-6V6h2v7Z"/></svg>',
    quote_required: '<svg viewBox="0 0 24 24"><path d="M4 4h16v12H7l-3 3V4Zm4 4v2h8V8H8Zm0 4v2h5v-2H8Z"/></svg>',
    address: '<svg viewBox="0 0 24 24"><path d="M12 2a7 7 0 0 0-7 7c0 5.2 7 13 7 13s7-7.8 7-13a7 7 0 0 0-7-7Zm0 9.5A2.5 2.5 0 1 1 12 6a2.5 2.5 0 0 1 0 5.5Z"/></svg>',
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

function setStep(step) {
    qsa("[data-step]").forEach((panel) => panel.classList.toggle("hidden", panel.dataset.step !== step));
    qsa("[data-progress]").forEach((item) => item.classList.toggle("active", item.dataset.progress === step));
    qs("#screenTitle").textContent = stepTitles[step];
    setAlert("");
}

function saveTokens(data) {
    state.accessToken = data.access_token;
    state.refreshToken = data.refresh_token;
    localStorage.setItem("ayosnow_access", state.accessToken);
    localStorage.setItem("ayosnow_refresh", state.refreshToken);
    qs("#logoutButton").classList.remove("hidden");
    qs("#bookViewButton").classList.remove("hidden");
    qs("#historyViewButton").classList.remove("hidden");
}

function clearTokens() {
    state.accessToken = "";
    state.refreshToken = "";
    localStorage.removeItem("ayosnow_access");
    localStorage.removeItem("ayosnow_refresh");
    qs("#logoutButton").classList.add("hidden");
    qs("#bookViewButton").classList.add("hidden");
    qs("#historyViewButton").classList.add("hidden");
}

async function api(path, options = {}) {
    const headers = {
        "Content-Type": "application/json",
        ...(options.headers || {}),
    };
    const publicAuthPath = path.startsWith("/auth/");
    if (state.accessToken && !publicAuthPath) {
        headers.Authorization = `Bearer ${state.accessToken}`;
    }
    const response = await fetch(`${apiBase}${path}`, {
        ...options,
        headers,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.success === false) {
        const message = payload.error?.message || `Request failed (${response.status})`;
        throw new Error(message);
    }
    return payload.data;
}

function serialize(form) {
    return Object.fromEntries(new FormData(form).entries());
}

async function loadCustomer() {
    const data = await api("/customers/me");
    state.customer = data.customer;
    state.addresses = data.addresses || [];
}

async function loadServices() {
    state.categories = await api("/services/categories");
}

async function loadBookings() {
    state.bookings = await api("/customers/bookings");
}

async function loadNotifications() {
    state.notifications = await api("/notifications");
    renderNotifications();
}

function renderServices() {
    const grid = qs("#serviceGrid");
    const items = state.categories.flatMap((category) =>
        (category.items || []).map((item) => ({ ...item, categoryName: category.name }))
    );
    grid.innerHTML = items.map((item) => `
        <button class="option-card" type="button" data-service-id="${item.id}">
            <span class="option-icon" aria-hidden="true">${icons[item.pricing_model] || icons.estimated}</span>
            <span>
                <span class="option-title">${item.name}</span>
                <span class="option-meta">${item.categoryName} · ${item.pricing_model.replace("_", " ")} · PHP ${item.base_price || "Quote"}</span>
            </span>
        </button>
    `).join("");
    qsa("[data-service-id]").forEach((button) => {
        button.addEventListener("click", () => {
            qsa("[data-service-id]").forEach((card) => card.classList.remove("selected"));
            button.classList.add("selected");
            state.selectedService = items.find((item) => item.id === button.dataset.serviceId);
            setTimeout(() => setStep("address"), 180);
        });
    });
}

function renderAddresses() {
    const list = qs("#addressList");
    const active = state.addresses.filter((address) => address.is_active);
    if (!active.length) {
        list.innerHTML = '<div class="alert">Add an address to continue.</div>';
        return;
    }
    list.innerHTML = active.map((address) => `
        <button class="option-card" type="button" data-address-id="${address.id}">
            <span class="option-icon" aria-hidden="true">${icons.address}</span>
            <span>
                <span class="option-title">${address.label}</span>
                <span class="option-meta">${address.line1}${address.landmark ? ` · ${address.landmark}` : ""}</span>
            </span>
        </button>
    `).join("");
    qsa("[data-address-id]").forEach((button) => {
        button.addEventListener("click", () => {
            qsa("[data-address-id]").forEach((card) => card.classList.remove("selected"));
            button.classList.add("selected");
            state.selectedAddress = active.find((address) => address.id === button.dataset.addressId);
            setTimeout(() => setStep("schedule"), 180);
        });
    });
}

function setDefaultSchedule() {
    const input = qs('[name="requested_schedule"]');
    const date = new Date(Date.now() + 24 * 60 * 60 * 1000);
    date.setMinutes(0, 0, 0);
    input.value = date.toISOString().slice(0, 16);
}

function renderBookingResult() {
    qs("#bookingSummary").textContent = `${state.selectedService.name} is waiting for dispatch.`;
    qs("#bookingDetails").innerHTML = `
        <dt>Booking ID</dt><dd>${state.booking.id}</dd>
        <dt>Status</dt><dd>${state.booking.status.replaceAll("_", " ")}</dd>
        <dt>Address</dt><dd>${state.selectedAddress.line1}</dd>
        <dt>Schedule</dt><dd>${new Date(state.booking.requested_schedule).toLocaleString()}</dd>
    `;
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
            <span>${event.actor ? `${event.actor} · ` : ""}${new Date(event.created_at).toLocaleString()}</span>
        </article>
    `).join("");
}

function renderHistory() {
    const list = qs("#historyList");
    if (!state.bookings.length) {
        list.innerHTML = '<div class="empty">No bookings yet. Create your first service request from the Book view.</div>';
        return;
    }
    list.innerHTML = state.bookings.map((booking) => {
        const serviceName = booking.service_snapshot?.name || "Service booking";
        const address = booking.address_snapshot?.line1 || "Address snapshot unavailable";
        const provider = booking.latest_provider_name || "Waiting for provider";
        const assignment = booking.latest_assignment_status || "not assigned";
        const payment = booking.latest_payment_status || "no payment";
        const complaint = booking.open_complaint_status || "no complaint";
        return `
            <article class="booking-card">
                <div>
                    <h4>${serviceName}</h4>
                    <p>${address} · ${new Date(booking.requested_schedule).toLocaleString()}</p>
                    <p>Provider: ${provider}</p>
                    <p>Booking ID: ${booking.id}</p>
                    <button class="secondary report-button" type="button" data-report-booking="${booking.id}">Report issue</button>
                    <button class="ghost report-button" type="button" data-booking-timeline="${booking.id}">View timeline</button>
                </div>
                <div class="status-stack">
                    <span class="status-pill">${booking.status.replaceAll("_", " ")}</span>
                    <span class="status-pill">${assignment.replaceAll("_", " ")}</span>
                    <span class="status-pill payment">${payment.replaceAll("_", " ")}</span>
                    <span class="status-pill">${complaint.replaceAll("_", " ")}</span>
                </div>
                <div class="timeline-list hidden" data-timeline-for="${booking.id}"></div>
            </article>
        `;
    }).join("");
    qsa("[data-report-booking]").forEach((button) => {
        button.addEventListener("click", () => {
            state.complaintBookingId = button.dataset.reportBooking;
            qs("#complaintTitle").textContent = `Report issue for booking ${state.complaintBookingId}`;
            qs("#complaintForm").reset();
            setStep("complaint");
        });
    });
    qsa("[data-booking-timeline]").forEach((button) => {
        button.addEventListener("click", async () => {
            try {
                const target = qs(`[data-timeline-for="${button.dataset.bookingTimeline}"]`);
                const events = await api(`/bookings/${button.dataset.bookingTimeline}/timeline`);
                target.innerHTML = formatTimeline(events);
                target.classList.toggle("hidden");
            } catch (error) {
                setAlert(error.message);
            }
        });
    });
}

async function afterAuth() {
    await Promise.all([loadCustomer(), loadServices(), loadNotifications()]);
    renderServices();
    renderAddresses();
    setDefaultSchedule();
    setStep("service");
}

function bindAuthTabs() {
    qsa("[data-auth-tab]").forEach((button) => {
        button.addEventListener("click", () => {
            qsa("[data-auth-tab]").forEach((tab) => tab.classList.remove("active"));
            button.classList.add("active");
            qs("#loginForm").classList.toggle("hidden", button.dataset.authTab !== "login");
            qs("#registerForm").classList.toggle("hidden", button.dataset.authTab !== "register");
            qs("#otpForm").classList.add("hidden");
            setAlert("");
        });
    });
}

function bindForms() {
    qs("#loginForm").addEventListener("submit", async (event) => {
        event.preventDefault();
        try {
            const data = serialize(event.currentTarget);
            const result = await api("/auth/login", {
                method: "POST",
                body: JSON.stringify({ ...data, user_type: "customer" }),
            });
            saveTokens(result);
            await afterAuth();
        } catch (error) {
            setAlert(error.message);
        }
    });

    qs("#registerForm").addEventListener("submit", async (event) => {
        event.preventDefault();
        try {
            const result = await api("/auth/customer/register", {
                method: "POST",
                body: JSON.stringify(serialize(event.currentTarget)),
            });
            state.otpToken = result.otp_token;
            if (result.dev_otp) {
                qs('#otpForm input[name="otp_code"]').value = result.dev_otp;
            }
            qs("#registerForm").classList.add("hidden");
            qs("#otpForm").classList.remove("hidden");
            setAlert("Enter the development OTP code to continue.");
        } catch (error) {
            setAlert(error.message);
        }
    });

    qs("#otpForm").addEventListener("submit", async (event) => {
        event.preventDefault();
        try {
            const result = await api("/auth/otp/verify", {
                method: "POST",
                body: JSON.stringify({
                    otp_token: state.otpToken,
                    otp_code: serialize(event.currentTarget).otp_code,
                }),
            });
            saveTokens(result);
            await afterAuth();
        } catch (error) {
            setAlert(error.message);
        }
    });

    qs("#addressForm").addEventListener("submit", async (event) => {
        event.preventDefault();
        try {
            const data = serialize(event.currentTarget);
            const cityId = state.addresses[0]?.city || state.addresses[0]?.city_id;
            const regionId = state.addresses[0]?.region || state.addresses[0]?.region_id;
            if (!cityId || !regionId) {
                throw new Error("Use the demo account first, or add launch city selection in admin.");
            }
            await api("/customers/addresses", {
                method: "POST",
                body: JSON.stringify({ ...data, city: cityId, region: regionId }),
            });
            await loadCustomer();
            renderAddresses();
            event.currentTarget.reset();
        } catch (error) {
            setAlert(error.message);
        }
    });

    qs("#bookingForm").addEventListener("submit", async (event) => {
        event.preventDefault();
        try {
            if (!state.selectedService || !state.selectedAddress) {
                throw new Error("Select a service and address first.");
            }
            const data = serialize(event.currentTarget);
            state.booking = await api("/bookings", {
                method: "POST",
                headers: { "Idempotency-Key": `booking-${crypto.randomUUID()}` },
                body: JSON.stringify({
                    service_item_id: state.selectedService.id,
                    customer_address_id: state.selectedAddress.id,
                    requested_schedule: new Date(data.requested_schedule).toISOString(),
                    description: data.description,
                }),
            });
            renderBookingResult();
            setStep("confirm");
        } catch (error) {
            setAlert(error.message);
        }
    });
}

function bindActions() {
    qsa("[data-back]").forEach((button) => {
        button.addEventListener("click", () => setStep(button.dataset.back));
    });

    qs("#logoutButton").addEventListener("click", () => {
        clearTokens();
        state.customer = null;
        state.addresses = [];
        state.booking = null;
        state.notifications = [];
        renderNotifications();
        setStep("auth");
    });

    qs("#newBookingButton").addEventListener("click", async () => {
        state.booking = null;
        state.selectedService = null;
        state.selectedAddress = null;
        await afterAuth();
    });

    qs("#viewHistoryButton").addEventListener("click", async () => {
        try {
            await loadBookings();
            await loadNotifications();
            renderHistory();
            setStep("history");
        } catch (error) {
            setAlert(error.message);
        }
    });

    qs("#historyViewButton").addEventListener("click", async () => {
        try {
            await loadBookings();
            await loadNotifications();
            renderHistory();
            setStep("history");
        } catch (error) {
            setAlert(error.message);
        }
    });

    qs("#bookViewButton").addEventListener("click", async () => {
        state.booking = null;
        state.selectedService = null;
        state.selectedAddress = null;
        await afterAuth();
    });

    qs("#refreshHistoryButton").addEventListener("click", async () => {
        try {
            await loadBookings();
            await loadNotifications();
            renderHistory();
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

    qs("#cancelComplaintButton").addEventListener("click", async () => {
        await loadBookings();
        renderHistory();
        setStep("history");
    });

    qs("#complaintForm").addEventListener("submit", async (event) => {
        event.preventDefault();
        try {
            const data = serialize(event.currentTarget);
            await api("/complaints", {
                method: "POST",
                body: JSON.stringify({
                    booking_id: state.complaintBookingId,
                    category: data.category,
                    description: data.description,
                }),
            });
            await loadBookings();
            renderHistory();
            setStep("history");
            setAlert("Complaint submitted. Operations can now review it.");
        } catch (error) {
            setAlert(error.message);
        }
    });

    qs("#checkoutButton").addEventListener("click", async () => {
        try {
            const checkout = await api("/payments/checkout", {
                method: "POST",
                headers: { "Idempotency-Key": `payment-${crypto.randomUUID()}` },
                body: JSON.stringify({ booking_id: state.booking.id, payment_method: "gcash" }),
            });
            setAlert(`Checkout created: ${checkout.status}`);
            await loadBookings();
        } catch (error) {
            setAlert(error.message);
        }
    });
}

async function init() {
    bindAuthTabs();
    bindForms();
    bindActions();
    qs("#logoutButton").classList.toggle("hidden", !state.accessToken);
    if (state.accessToken) {
        try {
            await afterAuth();
        } catch {
            clearTokens();
            setStep("auth");
        }
    } else {
        setStep("auth");
    }
}

init();
