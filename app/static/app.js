"use strict";

// ---------------------------------------------------------------------------
// Localization (EN/FR). UI chrome uses [data-i18n]; dynamic strings use STR[].
// ---------------------------------------------------------------------------
const I18N = {
  en: {
    language: "Language",
    highVisibility: "High-visibility / screen-reader mode",
    yourContext: "Your context",
    whereNow: "Where are you now?",
    whereGo: "Where do you want to go?",
    accessNeeds: "Accessibility needs",
    needWheelchair: "Wheelchair / step-free",
    needVisual: "Low vision / screen reader",
    needHearing: "Deaf / hard of hearing",
    ticketSection: "Ticket section (optional)",
    minutesToKickoff: "Minutes to kick-off",
    question: "Ask a question (optional)",
    questionHint: "Free text is treated as data only and never as instructions.",
    getHelp: "Get help",
    assistance: "Assistance",
    placeholder: "Fill in your context and select “Get help”. Your answer appears here.",
    grounding:
      "Answers are grounded in verified stadium data — the assistant never invents facilities.",
  },
  es: {
    language: "Idioma",
    highVisibility: "Modo alto contraste / lector de pantalla",
    yourContext: "Su contexto",
    whereNow: "¿Dónde se encuentra ahora?",
    whereGo: "¿A dónde quiere ir?",
    accessNeeds: "Necesidades de accesibilidad",
    needWheelchair: "Silla de ruedas / sin escalones",
    needVisual: "Baja visión / lector de pantalla",
    needHearing: "Sordo / con dificultad auditiva",
    ticketSection: "Sección del billete (opcional)",
    minutesToKickoff: "Minutos para el inicio",
    question: "Haga una pregunta (opcional)",
    questionHint: "El texto libre se trata solo como datos, nunca como instrucciones.",
    getHelp: "Obtener ayuda",
    assistance: "Asistencia",
    placeholder: "Complete su contexto y seleccione «Obtener ayuda». Su respuesta aparecerá aquí.",
    grounding:
      "Las respuestas se basan en datos verificados del estadio: el asistente nunca inventa instalaciones.",
  },
  fr: {
    language: "Langue",
    highVisibility: "Mode haute visibilité / lecteur d'écran",
    yourContext: "Votre contexte",
    whereNow: "Où êtes-vous actuellement ?",
    whereGo: "Où souhaitez-vous aller ?",
    accessNeeds: "Besoins d'accessibilité",
    needWheelchair: "Fauteuil roulant / sans marches",
    needVisual: "Basse vision / lecteur d'écran",
    needHearing: "Sourd / malentendant",
    ticketSection: "Section du billet (facultatif)",
    minutesToKickoff: "Minutes avant le coup d'envoi",
    question: "Posez une question (facultatif)",
    questionHint: "Le texte libre est traité comme des données, jamais comme des instructions.",
    getHelp: "Obtenir de l'aide",
    assistance: "Assistance",
    placeholder:
      "Renseignez votre contexte et choisissez « Obtenir de l'aide ». Votre réponse apparaîtra ici.",
    grounding:
      "Les réponses s'appuient sur des données vérifiées — l'assistant n'invente aucune installation.",
  },
};

const INTENT_LABELS = {
  en: {
    restroom: "Restroom", gate: "Entry gate", seat: "My seat", exit: "Exit",
    first_aid: "First aid", concession: "Food & drink", guest_services: "Guest services",
    water: "Water refill", sensory_room: "Sensory room",
  },
  es: {
    restroom: "Aseos", gate: "Puerta de entrada", seat: "Mi asiento", exit: "Salida",
    first_aid: "Primeros auxilios", concession: "Comida y bebida", guest_services: "Atención al aficionado",
    water: "Fuente de agua", sensory_room: "Sala sensorial",
  },
  fr: {
    restroom: "Toilettes", gate: "Porte d'entrée", seat: "Ma place", exit: "Sortie",
    first_aid: "Premiers secours", concession: "Restauration", guest_services: "Accueil",
    water: "Point d'eau", sensory_room: "Salle sensorielle",
  },
};

const STR = {
  en: {
    crowd: "Crowd", accessible: "Step-free / accessible", route: "Route", mode: "Mode",
    low: "low", medium: "moderate", high: "high",
    standard: "Standard", screen_reader: "Screen-reader optimized", captioned: "Visual signage",
    reqFailed: "Sorry, something went wrong. Please try again.",
    invalid: "Please check your inputs and try again.",
    rateLimited: "Too many requests — please wait a moment and try again.",
  },
  es: {
    crowd: "Afluencia", accessible: "Sin escalones / accesible", route: "Ruta", mode: "Modo",
    low: "baja", medium: "moderada", high: "alta",
    standard: "Estándar", screen_reader: "Optimizado para lector de pantalla", captioned: "Señalización visual",
    reqFailed: "Lo sentimos, algo salió mal. Inténtelo de nuevo.",
    invalid: "Compruebe sus datos e inténtelo de nuevo.",
    rateLimited: "Demasiadas solicitudes: espere un momento e inténtelo de nuevo.",
  },
  fr: {
    crowd: "Affluence", accessible: "Sans marches / accessible", route: "Itinéraire", mode: "Mode",
    low: "faible", medium: "modérée", high: "élevée",
    standard: "Standard", screen_reader: "Optimisé lecteur d'écran", captioned: "Signalétique visuelle",
    reqFailed: "Désolé, une erreur est survenue. Réessayez.",
    invalid: "Veuillez vérifier vos saisies et réessayer.",
    rateLimited: "Trop de requêtes — patientez un instant puis réessayez.",
  },
};

const DOTS = { low: "●○○", medium: "●●○", high: "●●●" };

// ---------------------------------------------------------------------------
// State + element refs
// ---------------------------------------------------------------------------
let currentLang = "en";
const $ = (id) => document.getElementById(id);

function t(dict) {
  return dict[currentLang] || dict.en;
}

// ---------------------------------------------------------------------------
// Bootstrapping
// ---------------------------------------------------------------------------
async function init() {
  applyLanguage("en");
  bindEvents();
  await loadStadium();
}

function bindEvents() {
  $("language").addEventListener("change", (e) => applyLanguage(e.target.value));
  $("contrast-toggle").addEventListener("click", toggleContrast);
  $("assist-form").addEventListener("submit", onSubmit);
}

async function loadStadium() {
  try {
    const res = await fetch("/api/stadium");
    if (!res.ok) throw new Error("stadium metadata unavailable");
    const data = await res.json();
    window.__stadium = data; // keep zone/facility maps for re-localization on language change
    window.__intents = data.intents;
    renderLocationOptions();
    refreshIntentOptions(data.intents);
    const s = data.stadium;
    $("stadium-meta").textContent = `${s.name} · ${s.fifa_name} · ${s.city}`;
  } catch (err) {
    $("stadium-meta").textContent = "";
    renderError(t(STR).reqFailed);
  }
}

function populateSelect(select, pairs) {
  select.innerHTML = "";
  for (const [value, label] of pairs) {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = label;
    select.appendChild(opt);
  }
}

function refreshIntentOptions(intents) {
  const labels = INTENT_LABELS[currentLang] || INTENT_LABELS.en;
  const select = $("destination_intent");
  const previous = select.value;
  populateSelect(select, intents.map((i) => [i, labels[i] || i]));
  if (previous) select.value = previous;
}

function renderLocationOptions() {
  const data = window.__stadium;
  if (!data) return;
  const select = $("current_location");
  const previous = select.value;
  populateSelect(
    select,
    data.zones.map((z) => [z.id, (z.name && (z.name[currentLang] || z.name.en)) || z.id])
  );
  if (previous) select.value = previous;
}

// ---------------------------------------------------------------------------
// Language + theme
// ---------------------------------------------------------------------------
function applyLanguage(lang) {
  currentLang = lang in I18N ? lang : "en";
  document.documentElement.lang = currentLang; // update <html lang> for a11y
  $("language").value = currentLang;
  const dict = I18N[currentLang];
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (dict[key]) el.textContent = dict[key];
  });
  if (window.__intents) refreshIntentOptions(window.__intents);
  renderLocationOptions();
}

function toggleContrast() {
  const btn = $("contrast-toggle");
  const on = btn.getAttribute("aria-pressed") !== "true";
  btn.setAttribute("aria-pressed", String(on));
  document.body.classList.toggle("hi-vis", on);
  // High-visibility mode maps to the visual accessibility path server-side.
  const visual = document.querySelector('input[name="need"][value="visual"]');
  if (visual) visual.checked = on;
}

// ---------------------------------------------------------------------------
// Submit + render
// ---------------------------------------------------------------------------
function collectContext() {
  const needs = Array.from(document.querySelectorAll('input[name="need"]:checked')).map(
    (el) => el.value
  );
  const ticket = $("ticket_section").value.trim();
  const question = $("question").value.trim();
  const payload = {
    language: $("language").value,
    current_location: $("current_location").value,
    destination_intent: $("destination_intent").value,
    accessibility_needs: needs.length ? needs : ["none"],
    minutes_to_kickoff: parseInt($("minutes_to_kickoff").value, 10),
  };
  if (ticket) payload.ticket_section = ticket;
  if (question) payload.question = question;
  return payload;
}

async function onSubmit(event) {
  event.preventDefault();
  const result = $("result");
  result.setAttribute("aria-busy", "true");
  try {
    const res = await fetch("/api/assist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(collectContext()),
    });
    if (res.status === 422) return renderError(t(STR).invalid);
    if (res.status === 429) return renderError(t(STR).rateLimited);
    if (!res.ok) return renderError(t(STR).reqFailed);
    renderResult(await res.json());
  } catch (err) {
    renderError(t(STR).reqFailed);
  } finally {
    result.setAttribute("aria-busy", "false");
  }
}

function badge(text, cls) {
  const span = document.createElement("span");
  span.className = "badge" + (cls ? " " + cls : "");
  span.textContent = text;
  return span;
}

function renderResult(data) {
  const s = STR[currentLang] || STR.en;
  const result = $("result");
  result.innerHTML = "";

  const answer = document.createElement("p");
  answer.className = "answer";
  answer.textContent = data.answer;
  result.appendChild(answer);

  // Metadata badges (facility, crowd with shape + text, accessibility).
  const grid = document.createElement("div");
  grid.className = "meta-grid";

  grid.appendChild(badge(data.facility.name));

  const crowdBadge = badge("", "crowd-" + data.crowd_level);
  const dots = document.createElement("span");
  dots.className = "dots";
  dots.setAttribute("aria-hidden", "true");
  dots.textContent = DOTS[data.crowd_level] || "";
  crowdBadge.appendChild(dots);
  const crowdText = document.createElement("span");
  crowdText.textContent = `${s.crowd}: ${s[data.crowd_level]}`;
  crowdBadge.appendChild(crowdText);
  grid.appendChild(crowdBadge);

  if (data.facility.accessible) grid.appendChild(badge("♿ " + s.accessible));
  grid.appendChild(badge(`${s.mode}: ${s[data.accessibility_mode] || data.accessibility_mode}`));
  result.appendChild(grid);

  if (data.urgency) result.appendChild(notice(data.urgency, true));
  if (data.alternatives_note) result.appendChild(notice(data.alternatives_note, false));

  if (data.route_steps && data.route_steps.length) {
    const heading = document.createElement("h3");
    heading.textContent = s.route;
    result.appendChild(heading);
    const ol = document.createElement("ol");
    ol.className = "route-steps";
    for (const step of data.route_steps) {
      const li = document.createElement("li");
      li.textContent = step.instruction;
      const means = document.createElement("span");
      means.className = "step-means";
      means.textContent = step.means;
      li.appendChild(means);
      ol.appendChild(li);
    }
    result.appendChild(ol);
  }
}

function notice(text, urgent) {
  const div = document.createElement("div");
  div.className = "notice" + (urgent ? " urgent" : "");
  div.textContent = text;
  return div;
}

function renderError(message) {
  const result = $("result");
  result.innerHTML = "";
  const p = document.createElement("p");
  p.className = "error";
  p.setAttribute("role", "alert");
  p.textContent = message;
  result.appendChild(p);
}

document.addEventListener("DOMContentLoaded", init);
