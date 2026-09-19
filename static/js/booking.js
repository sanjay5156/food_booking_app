// ---------------------------------------------------------------------
// Food Booking dashboard: self-booking calendar, guest booking form,
// preference toggle, and "my bookings" list. No external JS libraries —
// everything is hand-rolled so the app works fully offline on an
// intranet with no internet access.
// ---------------------------------------------------------------------

const MONTH_NAMES = ["January","February","March","April","May","June","July","August","September","October","November","December"];
const DOW = ["Su","Mo","Tu","We","Th","Fr","Sa"];

function pad2(n) { return n.toString().padStart(2, "0"); }
function toISODate(y, m, d) { return `${y}-${pad2(m + 1)}-${pad2(d)}`; }
function todayISO() {
  const t = new Date();
  return toISODate(t.getFullYear(), t.getMonth(), t.getDate());
}

// --------------------------------------------------------- Booking cutoffs
//
// window.MEAL_CUTOFFS (injected by the dashboard template from the admin's
// Settings > Booking Cutoff Times) mirrors models.meal_cutoff_config_for_js()
// on the server, so the browser can compute the same cutoff moment locally
// for any candidate date. The server re-checks every write independently —
// this is purely so the UI can grey out / warn about closed dates live.

function _hhmmToParts(s) {
  const [h, m] = (s || "0:0").split(":").map(n => parseInt(n, 10));
  return { h: h || 0, m: m || 0 };
}

function mealCutoffMoment(mealType, dateISO) {
  const cfg = (window.MEAL_CUTOFFS || {})[mealType];
  if (!cfg || !dateISO) return null;
  if (cfg.type === "before_reference") {
    const { h, m } = _hhmmToParts(cfg.reference_time);
    const ref = new Date(dateISO + "T00:00:00");
    ref.setHours(h, m, 0, 0);
    return new Date(ref.getTime() - (cfg.hours_before || 0) * 3600 * 1000);
  }
  const { h, m } = _hhmmToParts(cfg.cutoff_time);
  const cutoff = new Date(dateISO + "T00:00:00");
  cutoff.setHours(h, m, 0, 0);
  return cutoff;
}

function isCutoffPassed(mealType, dateISO, now) {
  const cutoff = mealCutoffMoment(mealType, dateISO);
  if (!cutoff) return false;
  return (now || new Date()) >= cutoff;
}

function cutoffDescription(mealType) {
  const cfg = (window.MEAL_CUTOFFS || {})[mealType];
  return cfg ? cfg.description : "";
}

// ----------------------------- Conditional meal-type -> food-type dropdown

async function populateFoodTypeDropdown(mealType, foodTypeSelect, itemSelect) {
  foodTypeSelect.innerHTML = "";
  itemSelect.innerHTML = '<option value="">Any / Chef\'s choice</option>';

  if (!mealType) {
    foodTypeSelect.disabled = true;
    itemSelect.disabled = true;
    foodTypeSelect.innerHTML = '<option value="">Select meal type first…</option>';
    return;
  }

  const foodTypes = window.MEAL_TYPE_FOOD_TYPES[mealType] || [];
  foodTypeSelect.disabled = false;
  foodTypeSelect.innerHTML = '<option value="">Select food type…</option>' +
    foodTypes.map(ft => `<option value="${ft}">${ft}</option>`).join("");

  // fetch the item catalog for this meal type once, cache items per food type
  try {
    const res = await fetch(`/api/food-catalog?meal_type=${encodeURIComponent(mealType)}`);
    const data = await res.json();
    foodTypeSelect.dataset.items = JSON.stringify(data.items || {});
  } catch (e) {
    foodTypeSelect.dataset.items = "{}";
  }

  itemSelect.disabled = true;
}

function wireMealTypeCascade(mealTypeSelect, foodTypeSelect, itemSelect) {
  mealTypeSelect.addEventListener("change", () => {
    populateFoodTypeDropdown(mealTypeSelect.value, foodTypeSelect, itemSelect);
  });

  foodTypeSelect.addEventListener("change", () => {
    const itemsByType = JSON.parse(foodTypeSelect.dataset.items || "{}");
    const items = itemsByType[foodTypeSelect.value] || [];
    itemSelect.innerHTML = '<option value="">Any / Chef\'s choice</option>' +
      items.map(i => `<option value="${i}">${i}</option>`).join("");
    itemSelect.disabled = !foodTypeSelect.value;
  });
}

// ----------------------------------------------------------- Mini calendar
//
// Selection can be built up three ways, and they can be mixed freely in one
// booking: (1) click a date to toggle it on/off; (2) press the mouse button
// down on a date and drag across others to paint a range; (3) click one
// date, then Shift+click another, to select every date in between — like
// picking files in a file manager. Drag and Shift+click both ADD their
// range to whatever is already selected, so gapped/scattered dates plus a
// range can coexist in a single submission.

function datesBetween(iso1, iso2) {
  const [lo, hi] = iso1 <= iso2 ? [iso1, iso2] : [iso2, iso1];
  const out = [];
  let cur = new Date(lo + "T00:00:00");
  const end = new Date(hi + "T00:00:00");
  while (cur <= end) {
    out.push(toISODate(cur.getFullYear(), cur.getMonth(), cur.getDate()));
    cur.setDate(cur.getDate() + 1);
  }
  return out;
}

class MultiSelectCalendar {
  constructor(container) {
    this.container = container;
    this.selected = new Set();
    const now = new Date();
    this.viewYear = now.getFullYear();
    this.viewMonth = now.getMonth();
    this.todayISO = todayISO();
    this.onChange = null;
    this.blockedFn = null; // (iso) => true if the date can't be selected beyond being merely "past"

    // Drag + shift-click range state
    this.anchorDate = null;     // last plain-clicked date, extended by Shift+click
    this.dragging = false;
    this.dragStart = null;
    this.dragCurrent = null;
    this.dragShift = false;

    this._onDocMouseUp = () => this._finishDrag();
    document.addEventListener("mouseup", this._onDocMouseUp);

    this.render();
  }

  destroy() {
    document.removeEventListener("mouseup", this._onDocMouseUp);
  }

  clear() {
    this.selected.clear();
    this.anchorDate = null;
    this.render();
    if (this.onChange) this.onChange();
  }

  // Called whenever the meal type (and therefore the cutoff rule) changes.
  // Drops any already-selected dates that are now past that meal's cutoff,
  // so the summary and submit never disagree with what's on screen.
  setBlockedFn(fn) {
    this.blockedFn = fn || null;
    if (this.blockedFn) {
      Array.from(this.selected).forEach(iso => {
        if (this.blockedFn(iso)) this.selected.delete(iso);
      });
    }
    this.render();
    if (this.onChange) this.onChange();
  }

  _finishDrag() {
    if (!this.dragging) return;
    const start = this.dragStart, current = this.dragCurrent || this.dragStart;
    this.dragging = false;
    const addIfOpen = d => { if (!this.blockedFn || !this.blockedFn(d)) this.selected.add(d); };

    if (this.dragShift && this.anchorDate) {
      // Shift+click: add the whole range from the last anchor to this date.
      datesBetween(this.anchorDate, current).forEach(addIfOpen);
    } else if (start === current) {
      // A plain click with no movement: toggle just that one date.
      if (this.selected.has(start)) this.selected.delete(start);
      else addIfOpen(start);
      this.anchorDate = start;
    } else {
      // A real click-and-drag: add the whole painted range.
      datesBetween(start, current).forEach(addIfOpen);
      this.anchorDate = current;
    }

    this.dragStart = null;
    this.dragCurrent = null;
    this.dragShift = false;
    this.render();
    if (this.onChange) this.onChange();
  }

  // Lightweight visual update used while a drag is in progress: toggles the
  // "selected" class on the existing calendar-day nodes in place, without
  // rebuilding the DOM (see the comment in the mousedown handler for why).
  _applyPreview() {
    let previewSet = null;
    if (this.dragging && !this.dragShift) {
      previewSet = new Set(datesBetween(this.dragStart, this.dragCurrent || this.dragStart));
    }
    this.container.querySelectorAll(".calendar-day:not(.blank)").forEach(cell => {
      const iso = cell.dataset.date;
      const isSelected = this.selected.has(iso) || (previewSet && previewSet.has(iso));
      cell.classList.toggle("selected", !!isSelected);
    });
  }

  render() {
    const y = this.viewYear, m = this.viewMonth;
    const firstDow = new Date(y, m, 1).getDay();
    const daysInMonth = new Date(y, m + 1, 0).getDate();

    let previewSet = null;
    if (this.dragging && !this.dragShift) {
      previewSet = new Set(datesBetween(this.dragStart, this.dragCurrent || this.dragStart));
    }

    let html = `<div class="calendar-header">
      <button type="button" data-nav="-1">&larr;</button>
      <strong>${MONTH_NAMES[m]} ${y}</strong>
      <button type="button" data-nav="1">&rarr;</button>
    </div>`;
    html += '<div class="calendar-grid">';
    DOW.forEach(d => html += `<div class="dow">${d}</div>`);
    for (let i = 0; i < firstDow; i++) html += '<div class="calendar-day blank"></div>';
    for (let d = 1; d <= daysInMonth; d++) {
      const iso = toISODate(y, m, d);
      const isPast = iso < this.todayISO;
      const isToday = iso === this.todayISO;
      const isBlocked = !isPast && this.blockedFn && this.blockedFn(iso);
      const isSelected = this.selected.has(iso) || (previewSet && previewSet.has(iso));
      const classes = ["calendar-day"];
      if (isPast) classes.push("past");
      if (isBlocked) classes.push("blocked");
      if (isToday) classes.push("today");
      if (isSelected) classes.push("selected");
      html += `<div class="${classes.join(" ")}" data-date="${iso}" title="${isBlocked ? "Booking cutoff has passed for this date" : ""}">${d}</div>`;
    }
    html += "</div>";
    this.container.innerHTML = html;

    this.container.querySelectorAll("[data-nav]").forEach(btn => {
      btn.addEventListener("click", () => {
        this.viewMonth += parseInt(btn.dataset.nav, 10);
        if (this.viewMonth < 0) { this.viewMonth = 11; this.viewYear--; }
        if (this.viewMonth > 11) { this.viewMonth = 0; this.viewYear++; }
        this.render();
      });
    });

    this.container.querySelectorAll(".calendar-day:not(.blank):not(.past):not(.blocked)").forEach(cell => {
      cell.addEventListener("mousedown", (e) => {
        e.preventDefault(); // avoid the browser trying to text-select while dragging
        const iso = cell.dataset.date;
        this.dragging = true;
        this.dragStart = iso;
        this.dragCurrent = iso;
        this.dragShift = e.shiftKey;
        // Note: deliberately NOT calling this.render() here (and not from
        // mouseenter below either, while a drag is live). Replacing the DOM
        // node currently under the mouse — via innerHTML — mid-gesture
        // confuses the browser's implicit mouse-capture / hover recalculation
        // and can prevent the document-level mouseup listener from firing
        // (or, worse, trigger a mouseenter/render feedback loop as each
        // rebuilt node re-triggers hover under a stationary pointer). Instead
        // we just toggle the "selected" class on the existing nodes directly.
        this._applyPreview();
      });
      cell.addEventListener("mouseenter", () => {
        if (!this.dragging) return;
        this.dragCurrent = cell.dataset.date;
        this._applyPreview();
      });
      // Touch devices synthesize mousedown/mouseup for a tap without ever
      // firing mouseenter, so dragCurrent stays equal to dragStart and
      // _finishDrag treats it as a plain single-date toggle — tapping just
      // works, it simply doesn't support drag-painting on a touchscreen.
    });
  }

  getSelectedDates() {
    return Array.from(this.selected).sort();
  }
}

function formatDateList(dates) {
  if (dates.length === 0) return "No dates selected.";
  if (dates.length <= 6) return `${dates.length} date(s) selected: ${dates.join(", ")}`;
  return `${dates.length} date(s) selected: ${dates[0]} … ${dates[dates.length - 1]} (and others)`;
}

// --------------------------------------------------------------------- Init

document.addEventListener("DOMContentLoaded", () => {
  // --- Preference toggle ---
  if (window.IS_EMPLOYEE && window.CURRENT_EMPLOYEE) {
    const vegRadio = document.querySelector('#pref-toggle input[value="Veg"]');
    const nvRadio = document.querySelector('#pref-toggle input[value="Non-Veg"]');
    const vegLabel = document.getElementById("pref-veg-label");
    const nvLabel = document.getElementById("pref-nonveg-label");
    const status = document.getElementById("pref-status");

    function syncPrefUI(pref) {
      vegRadio.checked = pref === "Veg";
      nvRadio.checked = pref === "Non-Veg";
      vegLabel.classList.toggle("active", pref === "Veg");
      nvLabel.classList.toggle("active", pref === "Non-Veg");
    }
    syncPrefUI(window.CURRENT_EMPLOYEE.food_preference);

    [vegRadio, nvRadio].forEach(r => r.addEventListener("change", async () => {
      const pref = r.value;
      const res = await fetch("/api/my-preference", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ food_preference: pref }),
      });
      const data = await res.json();
      if (res.ok) {
        syncPrefUI(pref);
        status.textContent = `Preference updated to ${pref}. This will now apply continuously.`;
      } else {
        status.textContent = data.error || "Could not update preference.";
      }
    }));
  }

  // --- Self booking ---
  let selfCal = null;
  if (window.IS_EMPLOYEE) {
    const selfMealType = document.getElementById("self-meal-type");
    const selfFoodType = document.getElementById("self-food-type");
    const selfItem = document.getElementById("self-item-name");
    const selfCutoffNote = document.getElementById("self-cutoff-note");
    wireMealTypeCascade(selfMealType, selfFoodType, selfItem);

    selfCal = new MultiSelectCalendar(document.getElementById("self-calendar"));
    const summary = document.getElementById("self-selected-summary");
    selfCal.onChange = () => { summary.textContent = formatDateList(selfCal.getSelectedDates()); };

    selfMealType.addEventListener("change", () => {
      const mealType = selfMealType.value;
      selfCutoffNote.textContent = mealType ? cutoffDescription(mealType) : "";
      selfCal.setBlockedFn(mealType ? (iso => isCutoffPassed(mealType, iso)) : null);
    });

    document.getElementById("self-clear-btn").addEventListener("click", () => selfCal.clear());

    document.getElementById("self-book-btn").addEventListener("click", async () => {
      const dates = selfCal.getSelectedDates();
      const mealType = selfMealType.value;
      const foodType = selfFoodType.value;
      const itemName = selfItem.value;

      if (dates.length === 0) { alert("Please select at least one date."); return; }
      if (!mealType) { alert("Please select a meal type."); return; }
      if (!foodType) { alert("Please select a food type."); return; }

      const res = await fetch("/api/book/self", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dates, meal_type: mealType, food_type: foodType, item_name: itemName }),
      });
      const data = await res.json();
      if (res.ok) {
        alert(`Booked ${mealType} (${foodType}) for ${data.count} date(s).`);
        selfCal.clear();
        loadMyBookings();
      } else {
        alert(data.error || "Booking failed.");
      }
    });
  }

  // --- Guest booking ---
  const guestMealType = document.getElementById("guest-meal-type");
  const guestFoodType = document.getElementById("guest-food-type");
  const guestItem = document.getElementById("guest-item-name");
  const guestCutoffNote = document.getElementById("guest-cutoff-note");
  wireMealTypeCascade(guestMealType, guestFoodType, guestItem);

  const guestDate = document.getElementById("guest-date");
  guestDate.value = todayISO();
  if (window.CURRENT_EMPLOYEE) {
    document.getElementById("guest-department").value = window.CURRENT_EMPLOYEE.department;
  }

  function refreshGuestCutoffNote() {
    const mealType = guestMealType.value;
    if (!mealType) { guestCutoffNote.textContent = ""; return; }
    const base = cutoffDescription(mealType);
    if (guestDate.value && isCutoffPassed(mealType, guestDate.value)) {
      guestCutoffNote.textContent = `${base} Booking has already closed for ${guestDate.value}.`;
      guestCutoffNote.style.color = "#a5432f";
    } else {
      guestCutoffNote.textContent = base;
      guestCutoffNote.style.color = "";
    }
  }
  guestMealType.addEventListener("change", refreshGuestCutoffNote);
  guestDate.addEventListener("change", refreshGuestCutoffNote);

  document.getElementById("guest-book-btn").addEventListener("click", async () => {
    const payload = {
      booking_date: guestDate.value,
      plant: document.getElementById("guest-plant").value,
      meal_type: guestMealType.value,
      food_type: guestFoodType.value,
      item_name: guestItem.value,
      quantity: document.getElementById("guest-quantity").value,
      department: document.getElementById("guest-department").value,
      guest_classification: document.getElementById("guest-classification").value,
      guest_note: document.getElementById("guest-note").value,
    };
    if (!payload.booking_date) { alert("Please select a date."); return; }
    if (!payload.plant) { alert("Please select which plant this guest is for."); return; }
    if (!payload.meal_type) { alert("Please select a meal type."); return; }
    if (!payload.food_type) { alert("Please select a food type."); return; }
    if (!payload.guest_classification) { alert("Please specify the guest type."); return; }
    if (isCutoffPassed(payload.meal_type, payload.booking_date) &&
        !confirm(`${cutoffDescription(payload.meal_type)} It looks like this has already closed for ${payload.booking_date} — try anyway? (Admin accounts can still book past the cutoff; the server will reject this if you're not an admin.)`)) {
      return;
    }

    const res = await fetch("/api/book/guest", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (res.ok) {
      alert(`Booked ${payload.quantity} ${payload.meal_type} meal(s) for guests.`);
      document.getElementById("guest-classification").value = "";
      document.getElementById("guest-note").value = "";
      document.getElementById("guest-quantity").value = 1;
      loadMyBookings();
    } else {
      alert(data.error || "Booking failed.");
    }
  });

  // --- My bookings table ---
  window.loadMyBookings = async function loadMyBookings() {
    const tbody = document.querySelector("#my-bookings-table tbody");
    const res = await fetch("/api/my-bookings");
    const rows = await res.json();
    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="10" class="help-text">No bookings yet.</td></tr>';
      return;
    }
    tbody.innerHTML = rows.map(b => {
      const typeTagClass = b.food_type === "Veg" ? "veg" : (b.food_type === "Non-Veg" ? "nonveg" : "snacks");
      const targetTagClass = b.target === "Self" ? "self" : "guest";
      return `<tr>
        <td>${b.booking_date}</td>
        <td>${b.meal_type}</td>
        <td><span class="tag ${typeTagClass}">${b.food_type}</span></td>
        <td>${b.item_name || "—"}</td>
        <td><span class="tag ${targetTagClass}">${b.target}</span></td>
        <td>${b.quantity}</td>
        <td>${b.department}</td>
        <td>${b.plant || "—"}</td>
        <td>${b.guest_classification || "—"}</td>
        <td><button class="btn small secondary" data-cancel="${b.id}">Cancel</button></td>
      </tr>`;
    }).join("");

    tbody.querySelectorAll("[data-cancel]").forEach(btn => {
      btn.addEventListener("click", async () => {
        if (!confirm("Cancel this booking?")) return;
        await fetch(`/api/book/${btn.dataset.cancel}/cancel`, { method: "POST" });
        loadMyBookings();
      });
    });
  };

  loadMyBookings();
});
