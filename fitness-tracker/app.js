// =====================================================================
// Fitness Tracker
// All data is stored in the browser's localStorage, so it stays there
// after you close the page (on this browser/device only).
// =====================================================================

// ---------- 1. Loading and saving data ----------

// Read a saved value; if nothing is saved yet, use the fallback.
function load(key, fallback) {
  try {
    const saved = localStorage.getItem(key);
    return saved ? JSON.parse(saved) : fallback;
  } catch {
    return fallback;
  }
}

function save(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Storage can be blocked (e.g. private mode). The app still works, it just won't remember.
  }
}

// The app's state: everything we know about the user's progress.
let workouts = load("workouts", []);   // [{ id, date, exercise, type, sets, reps, weight, minutes, notes }]
let weighIns = load("weighIns", []);   // [{ id, date, kg }]
let weeklyGoal = load("weeklyGoal", 3);


// ---------- 2. Date helpers ----------

// Turn a Date into "YYYY-MM-DD" (the format date inputs use), in local time.
function toDateString(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function today() {
  return toDateString(new Date());
}

// Go back or forward a number of days from a "YYYY-MM-DD" string.
function addDays(dateString, days) {
  const date = new Date(dateString + "T00:00:00");
  date.setDate(date.getDate() + days);
  return toDateString(date);
}

// The Monday that starts the week containing the given date.
function startOfWeek(dateString) {
  const date = new Date(dateString + "T00:00:00");
  const dayOfWeek = (date.getDay() + 6) % 7; // Monday = 0 ... Sunday = 6
  return addDays(dateString, -dayOfWeek);
}

// "2026-10-03" -> "Sat, Oct 3"
function prettyDate(dateString) {
  const date = new Date(dateString + "T00:00:00");
  return date.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}


// ---------- 3. Stats ----------

function workoutsThisWeek() {
  const monday = startOfWeek(today());
  return workouts.filter(w => w.date >= monday && w.date <= today());
}

// How many days in a row (ending today, or yesterday) had at least one workout.
function currentStreak() {
  const daysWithWorkouts = new Set(workouts.map(w => w.date));
  let day = today();
  // If you haven't trained yet today, the streak can still continue from yesterday.
  if (!daysWithWorkouts.has(day)) day = addDays(day, -1);

  let streak = 0;
  while (daysWithWorkouts.has(day)) {
    streak++;
    day = addDays(day, -1);
  }
  return streak;
}


// ---------- 4. Drawing the page ----------

const $ = id => document.getElementById(id);

function renderStats() {
  const thisWeek = workoutsThisWeek();
  const minutes = thisWeek.reduce((total, w) => total + (Number(w.minutes) || 0), 0);

  $("stat-week").textContent = thisWeek.length;
  $("stat-minutes").textContent = minutes;
  $("stat-streak").textContent = currentStreak();

  // Weekly goal progress bar
  $("goal-input").value = weeklyGoal;
  $("goal-text").textContent = `${thisWeek.length} of ${weeklyGoal}`;
  const percent = Math.min(100, (thisWeek.length / weeklyGoal) * 100);
  $("goal-bar").style.width = percent + "%";

  // Bar chart: number of workouts on each of the last 7 days
  const days = [];
  for (let i = 6; i >= 0; i--) days.push(addDays(today(), -i));
  const counts = days.map(d => workouts.filter(w => w.date === d).length);
  const max = Math.max(1, ...counts);

  $("week-chart").innerHTML = days.map((d, i) => {
    const height = (counts[i] / max) * 85;
    const label = new Date(d + "T00:00:00").toLocaleDateString(undefined, { weekday: "short" });
    return `
      <div class="day" title="${counts[i]} workout(s) on ${prettyDate(d)}">
        <div class="day-bar ${counts[i] === 0 ? "zero" : ""}" style="height:${height}%"></div>
        <span>${label}</span>
      </div>`;
  }).join("");
}

// Protect against HTML in user input (e.g. someone typing "<b>" as an exercise name).
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function renderWorkouts() {
  // Newest first
  const sorted = [...workouts].sort((a, b) => b.date.localeCompare(a.date) || b.id - a.id);

  $("workout-list").innerHTML = sorted.map(w => {
    const details = [];
    if (w.type === "strength" && w.sets && w.reps) details.push(`${w.sets} × ${w.reps}`);
    if (w.weight) details.push(`${w.weight} kg`);
    if (w.minutes) details.push(`${w.minutes} min`);
    if (w.notes) details.push(escapeHtml(w.notes));

    return `
      <li>
        <div>
          <div class="item-title">${escapeHtml(w.exercise)}<span class="tag">${w.type}</span></div>
          <div class="item-meta">${prettyDate(w.date)}${details.length ? " · " + details.join(" · ") : ""}</div>
        </div>
        <button class="delete-btn" data-workout="${w.id}">Delete</button>
      </li>`;
  }).join("");

  $("workout-empty").hidden = workouts.length > 0;
}

function renderWeight() {
  const sorted = [...weighIns].sort((a, b) => a.date.localeCompare(b.date));

  // List, newest first
  $("weight-list").innerHTML = [...sorted].reverse().map(entry => `
    <li>
      <div>
        <div class="item-title">${entry.kg} kg</div>
        <div class="item-meta">${prettyDate(entry.date)}</div>
      </div>
      <button class="delete-btn" data-weight="${entry.id}">Delete</button>
    </li>`).join("");

  $("weight-empty").hidden = weighIns.length > 0;

  // Line chart (needs at least 2 points to draw a line)
  const chart = $("weight-chart");
  chart.style.display = sorted.length >= 2 ? "block" : "none";
  if (sorted.length < 2) return;

  const values = sorted.map(e => e.kg);
  const min = Math.min(...values) - 1;
  const max = Math.max(...values) + 1;
  const points = sorted.map((e, i) => {
    const x = 10 + (i / (sorted.length - 1)) * 580;
    const y = 190 - ((e.kg - min) / (max - min)) * 180;
    return [x, y];
  });

  chart.innerHTML =
    `<polyline points="${points.map(p => p.join(",")).join(" ")}" />` +
    points.map(([x, y]) => `<circle cx="${x}" cy="${y}" r="4" />`).join("");
}

function renderAll() {
  renderStats();
  renderWorkouts();
  renderWeight();
}


// ---------- 5. Reacting to the user ----------

// Show the sets/reps/weight fields only for strength workouts.
function updateTypeFields() {
  const type = document.querySelector('input[name="w-type"]:checked').value;
  $("strength-fields").hidden = type !== "strength";
}
document.querySelectorAll('input[name="w-type"]').forEach(radio =>
  radio.addEventListener("change", updateTypeFields)
);

$("workout-form").addEventListener("submit", event => {
  event.preventDefault(); // stop the page from reloading

  const type = document.querySelector('input[name="w-type"]:checked').value;
  workouts.push({
    id: Date.now(),
    date: $("w-date").value,
    exercise: $("w-exercise").value.trim(),
    type,
    sets: type === "strength" ? Number($("w-sets").value) || null : null,
    reps: type === "strength" ? Number($("w-reps").value) || null : null,
    weight: type === "strength" ? Number($("w-weight").value) || null : null,
    minutes: Number($("w-minutes").value) || null,
    notes: $("w-notes").value.trim(),
  });
  save("workouts", workouts);

  // Clear the form but keep the date, so logging several exercises is quick.
  const date = $("w-date").value;
  event.target.reset();
  $("w-date").value = date;
  updateTypeFields();
  renderAll();
});

$("weight-form").addEventListener("submit", event => {
  event.preventDefault();
  const date = $("bw-date").value;
  const kg = Number($("bw-value").value);

  // One weigh-in per day: replace it if that day already has one.
  weighIns = weighIns.filter(e => e.date !== date);
  weighIns.push({ id: Date.now(), date, kg });
  save("weighIns", weighIns);

  $("bw-value").value = "";
  renderWeight();
});

$("goal-input").addEventListener("change", () => {
  const value = Number($("goal-input").value);
  if (value >= 1) {
    weeklyGoal = value;
    save("weeklyGoal", weeklyGoal);
  }
  renderStats();
});

// One click listener for all the Delete buttons.
document.addEventListener("click", event => {
  const button = event.target.closest(".delete-btn");
  if (!button) return;

  if (button.dataset.workout) {
    workouts = workouts.filter(w => w.id !== Number(button.dataset.workout));
    save("workouts", workouts);
  } else if (button.dataset.weight) {
    weighIns = weighIns.filter(e => e.id !== Number(button.dataset.weight));
    save("weighIns", weighIns);
  }
  renderAll();
});


// ---------- 6. Start ----------

$("w-date").value = today();
$("bw-date").value = today();
updateTypeFields();
renderAll();
