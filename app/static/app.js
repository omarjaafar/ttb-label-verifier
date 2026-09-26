"use strict";

const $ = (id) => document.getElementById(id);
const form = $("verify-form");
const imageInput = $("image");
const dropzone = $("dropzone");

const STATUS = {
  pass: { icon: "✓", word: "Match", title: "Label matches" },
  review: { icon: "!", word: "Check", title: "Needs a quick check" },
  fail: { icon: "✗", word: "Problem", title: "Problem found" },
  "n/a": { icon: "–", word: "Not checked", title: "" },
};

// --- Image picking & preview ----------------------------------------------

function showPreview(file) {
  const preview = $("preview");
  if (!file) { preview.hidden = true; return; }
  preview.src = URL.createObjectURL(file);
  preview.hidden = false;
  $("dropzone-text").innerHTML = `<strong>${escapeHtml(file.name)}</strong><br>Click to choose a different photo`;
}

imageInput.addEventListener("change", () => showPreview(imageInput.files[0]));

["dragenter", "dragover"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.add("dragover"); }));
["dragleave", "drop"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.remove("dragover"); }));
dropzone.addEventListener("drop", (e) => {
  if (e.dataTransfer.files.length) {
    imageInput.files = e.dataTransfer.files;
    showPreview(imageInput.files[0]);
  }
});

// ABV is optional for wine/beer.
form.querySelectorAll('input[name="beverage_type"]').forEach((r) =>
  r.addEventListener("change", () => {
    $("abv-hint").textContent = r.value === "spirits" ? "(required for spirits)" : "(optional for wine and beer)";
  }));

// --- Submit -----------------------------------------------------------------

function showError(msg) {
  const box = $("form-error");
  box.textContent = msg;
  box.hidden = !msg;
  if (msg) box.scrollIntoView({ behavior: "smooth", block: "center" });
}

function validate() {
  const missing = [];
  form.querySelectorAll("input[required]").forEach((el) => {
    const empty = el.type === "file" ? !el.files.length : !el.value.trim();
    el.setAttribute("aria-invalid", empty ? "true" : "false");
    if (empty) missing.push(el.type === "file" ? "label image" : el.closest("label").firstChild.textContent.trim().toLowerCase());
  });
  const bev = form.querySelector('input[name="beverage_type"]:checked').value;
  const abv = form.querySelector('input[name="alcohol_content"]');
  if (bev === "spirits" && !abv.value.trim()) missing.push("alcohol content");
  return missing;
}

function setLoading(on) {
  $("submit").disabled = on;
  $("submit").textContent = on ? "Checking…" : "Check label";
  $("loading").hidden = !on;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  showError("");
  const missing = validate();
  if (missing.length) {
    showError(`Please fill in: ${missing.join(", ")}.`);
    return;
  }

  setLoading(true);
  try {
    const res = await fetch("/api/verify", { method: "POST", body: new FormData(form) });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = typeof body.detail === "string" ? body.detail : "Something went wrong. Please try again.";
      throw new Error(detail);
    }
    renderResults(body);
  } catch (err) {
    showError(err.message === "Failed to fetch" ? "Couldn't reach the server. Check your connection and try again." : err.message);
  } finally {
    setLoading(false);
  }
});

// --- Results ------------------------------------------------------------------

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function renderResults(r) {
  const s = STATUS[r.overall];
  const verdict = $("verdict");
  verdict.className = `verdict ${r.overall}`;
  verdict.innerHTML = `<span class="icon" aria-hidden="true">${s.icon}</span>
    <div><h2>${s.title}</h2><p>${escapeHtml(r.summary)}</p></div>`;

  $("result-rows").innerHTML = r.fields.map((f) => {
    const st = STATUS[f.status];
    const cls = f.status === "n/a" ? "na" : f.status;
    return `<tr>
      <td class="item">${escapeHtml(f.label)}<span class="note">${escapeHtml(f.message)}</span></td>
      <td data-label="Result"><span class="badge ${cls}"><span aria-hidden="true">${st.icon}</span> ${st.word}</span></td>
      <td data-label="Application" class="value">${escapeHtml(f.expected ?? "—")}</td>
      <td data-label="Label" class="value">${escapeHtml(f.found ?? "—")}</td>
    </tr>`;
  }).join("");
  $("result-rows").closest("table").hidden = r.fields.length === 0;

  $("meta").textContent = `Checked in ${(r.elapsed_ms / 1000).toFixed(1)} seconds using ${r.provider === "ocr" ? "offline text recognition" : "AI vision"}.`;
  $("results").hidden = false;
  verdict.focus();
  verdict.scrollIntoView({ behavior: "smooth", block: "start" });
}

$("again").addEventListener("click", () => {
  form.reset();
  showPreview(null);
  $("dropzone-text").innerHTML = "<strong>Click here to choose a photo</strong><br>or drag and drop it here (JPG or PNG)";
  $("results").hidden = true;
  window.scrollTo({ top: 0, behavior: "smooth" });
  imageInput.focus();
});
