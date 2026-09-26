"use strict";

// Batch mode: the browser sends each label to /api/verify with a small concurrency limit.
// This avoids a single huge upload (300 photos can be close to 1 GB), gives real progress, isolates
// failures to one label, and keeps the server stateless.

(() => {
  const $ = (id) => document.getElementById(id);
  const { escapeHtml, badgeHtml, fieldRowsHtml } = window.labelUi;

  const CONCURRENCY = 3; // stays under typical API rate limits (~50 requests/min)
  const MAX_ATTEMPTS = 3;
  const REQUIRED_COLUMNS = ["filename", "brand_name", "class_type", "net_contents"];
  const FIELD_COLUMNS = ["beverage_type", "brand_name", "class_type", "alcohol_content", "net_contents",
    "bottler_name_address", "country_of_origin"];
  const SORT_ORDER = { fail: 0, error: 1, review: 2, pass: 3 };

  let results = [];
  let abort = null;

  // --- CSV ------------------------------------------------------------------

  function parseCsv(text) {
    const rows = [];
    let row = [], field = "", quoted = false;
    text = text.replace(/^﻿/, ""); // Excel adds a byte-order mark
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      if (quoted) {
        if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
        else if (c === '"') quoted = false;
        else field += c;
      } else if (c === '"') quoted = true;
      else if (c === ",") { row.push(field); field = ""; }
      else if (c === "\n" || c === "\r") {
        if (c === "\r" && text[i + 1] === "\n") i++;
        row.push(field); rows.push(row); row = []; field = "";
      } else field += c;
    }
    if (field || row.length) { row.push(field); rows.push(row); }
    return rows.filter((r) => r.some((v) => v.trim()));
  }

  function readApplications(text) {
    const [header, ...rows] = parseCsv(text);
    if (!header) throw new Error("The spreadsheet is empty.");
    const cols = header.map((h) => h.trim().toLowerCase().replace(/[\s/]+/g, "_"));
    const missing = REQUIRED_COLUMNS.filter((c) => !cols.includes(c));
    if (missing.length) {
      throw new Error(`The spreadsheet is missing these columns: ${missing.join(", ")}. Download the template to see the expected format.`);
    }
    return rows.map((r) => Object.fromEntries(cols.map((c, i) => [c, (r[i] || "").trim()])));
  }

  // --- Running ----------------------------------------------------------------

  const sleep = (ms) => new Promise((res) => setTimeout(res, ms));

  async function verifyOne(job, signal) {
    const started = performance.now();
    for (let attempt = 1; ; attempt++) {
      const fd = new FormData();
      fd.append("image", job.file);
      FIELD_COLUMNS.forEach((c) => fd.append(c, c === "beverage_type" ? (job.app[c] || "spirits").toLowerCase() : job.app[c] || ""));
      try {
        const res = await fetch("/api/verify", { method: "POST", body: fd, signal });
        const body = await res.json().catch(() => ({}));
        if (res.ok) return { ...job, status: body.overall, result: body, seconds: (performance.now() - started) / 1000 };
        const detail = typeof body.detail === "string" ? body.detail : `Server error (${res.status}).`;
        const retryable = res.status === 429 || res.status >= 500;
        if (!retryable || attempt >= MAX_ATTEMPTS) return { ...job, status: "error", error: detail };
      } catch (err) {
        if (signal.aborted) throw err;
        if (attempt >= MAX_ATTEMPTS) return { ...job, status: "error", error: "Couldn't reach the server." };
      }
      await sleep(2000 * 2 ** (attempt - 1)); // 2s, 4s backoff
    }
  }

  async function runBatch(jobs) {
    abort = new AbortController();
    results = [];
    let next = 0;
    const startedAt = performance.now();
    showProgress(0, jobs.length, startedAt);

    async function worker() {
      while (next < jobs.length && !abort.signal.aborted) {
        const job = jobs[next++];
        try {
          results.push(await verifyOne(job, abort.signal));
        } catch {
          return; // cancelled
        }
        showProgress(results.length, jobs.length, startedAt);
        renderBatchResults();
      }
    }
    await Promise.all(Array.from({ length: Math.min(CONCURRENCY, jobs.length) }, worker));
    finish(jobs.length);
  }

  // --- Display ----------------------------------------------------------------

  function showProgress(done, total, startedAt) {
    $("batch-progress").hidden = false;
    $("batch-progress-bar").max = total;
    $("batch-progress-bar").value = done;
    let eta = "";
    if (done > 0 && done < total) {
      const perLabel = (performance.now() - startedAt) / done;
      const mins = Math.ceil((perLabel * (total - done)) / 60000);
      eta = ` · about ${mins} minute${mins === 1 ? "" : "s"} left`;
    }
    $("batch-progress-text").textContent = `Checked ${done} of ${total} labels${eta}`;
  }

  function finish(total) {
    const cancelled = abort.signal.aborted;
    $("batch-progress-text").textContent = cancelled
      ? `Stopped. Checked ${results.length} of ${total} labels.`
      : `Done. Checked all ${total} labels.`;
    $("batch-cancel").hidden = true;
    $("batch-submit").disabled = false;
    renderBatchResults();
  }

  function firstProblem(r) {
    if (r.status === "error") return r.error;
    const bad = r.result.fields.find((f) => f.status === "fail") || r.result.fields.find((f) => f.status === "review");
    return bad ? `${bad.label}: ${bad.message}` : r.result.summary;
  }

  function renderBatchResults() {
    $("batch-results").hidden = false;
    const count = (s) => results.filter((r) => r.status === s).length;
    $("batch-tally").innerHTML = [
      ["pass", "✓", "Match"], ["review", "!", "Needs a check"], ["fail", "✗", "Problem"], ["error", "?", "Couldn't check"],
    ].map(([s, icon, word]) => `<div class="tally-item ${s}"><span class="tally-num">${count(s)}</span>
      <span><span aria-hidden="true">${icon}</span> ${word}</span></div>`).join("");

    const sorted = [...results].sort((a, b) => SORT_ORDER[a.status] - SORT_ORDER[b.status] || a.name.localeCompare(b.name));
    $("batch-list").innerHTML = sorted.map((r) => `
      <details class="batch-item ${r.status}">
        <summary>
          ${r.status === "error" ? '<span class="badge fail"><span aria-hidden="true">?</span> Error</span>' : badgeHtml(r.status)}
          <span class="batch-name">${escapeHtml(r.name)}</span>
          <span class="batch-reason">${escapeHtml(r.app.brand_name || "")}: ${escapeHtml(firstProblem(r))}</span>
        </summary>
        ${r.status === "error" ? "" : `<table class="result-table"><thead><tr><th scope="col">Item</th><th scope="col">Result</th>
          <th scope="col">Application says</th><th scope="col">Label says</th></tr></thead>
          <tbody>${fieldRowsHtml(r.result.fields)}</tbody></table>`}
      </details>`).join("");
  }

  function csvCell(v) {
    const s = String(v ?? "");
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  }

  function downloadCsv() {
    const header = ["filename", "brand_name", "result", "issues", "seconds"];
    const lines = [...results]
      .sort((a, b) => SORT_ORDER[a.status] - SORT_ORDER[b.status])
      .map((r) => {
        const issues = r.status === "error" ? r.error
          : r.result.fields.filter((f) => f.status === "fail" || f.status === "review").map((f) => `${f.label}: ${f.message}`).join(" | ");
        return [r.name, r.app.brand_name, r.status === "review" ? "needs review" : r.status, issues, r.seconds ? r.seconds.toFixed(1) : ""];
      });
    const csv = [header, ...lines].map((l) => l.map(csvCell).join(",")).join("\r\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    a.download = `label-results-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
  }

  // --- Wiring -------------------------------------------------------------------

  function setMessage(id, msg) {
    $(id).textContent = msg || "";
    $(id).hidden = !msg;
  }

  $("batch-images").addEventListener("change", () => {
    const n = $("batch-images").files.length;
    $("batch-images-text").innerHTML = n
      ? `<strong>${n} image${n === 1 ? "" : "s"} selected</strong><br>Click to choose different images`
      : "<strong>Click here to choose label images</strong><br>You can select many at once, or drag them here";
  });

  const dz = $("batch-dropzone");
  ["dragenter", "dragover"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("dragover"); }));
  ["dragleave", "drop"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("dragover"); }));
  dz.addEventListener("drop", (e) => {
    if (e.dataTransfer.files.length) {
      $("batch-images").files = e.dataTransfer.files;
      $("batch-images").dispatchEvent(new Event("change"));
    }
  });

  $("batch-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    setMessage("batch-error", "");
    setMessage("batch-warning", "");
    const images = [...$("batch-images").files];
    const csvFile = $("batch-csv").files[0];
    if (!images.length || !csvFile) {
      setMessage("batch-error", `Please choose ${!images.length ? "the label images" : ""}${!images.length && !csvFile ? " and " : ""}${!csvFile ? "the application spreadsheet" : ""}.`);
      return;
    }

    let apps;
    try {
      apps = readApplications(await csvFile.text());
    } catch (err) {
      setMessage("batch-error", err.message);
      return;
    }

    const byName = new Map(images.map((f) => [f.name.toLowerCase(), f]));
    const jobs = [], noImage = [];
    for (const app of apps) {
      const file = byName.get(app.filename.toLowerCase());
      if (file) { jobs.push({ name: file.name, file, app }); byName.delete(app.filename.toLowerCase()); }
      else noImage.push(app.filename || "(blank filename)");
    }
    const noRow = [...byName.values()].map((f) => f.name);
    if (!jobs.length) {
      setMessage("batch-error", "None of the image file names match the filename column in the spreadsheet.");
      return;
    }
    const warn = [];
    if (noImage.length) warn.push(`${noImage.length} spreadsheet row(s) have no matching image and will be skipped: ${noImage.slice(0, 5).join(", ")}${noImage.length > 5 ? "…" : ""}.`);
    if (noRow.length) warn.push(`${noRow.length} image(s) have no spreadsheet row and will be skipped: ${noRow.slice(0, 5).join(", ")}${noRow.length > 5 ? "…" : ""}.`);
    setMessage("batch-warning", warn.join(" "));

    $("batch-submit").disabled = true;
    $("batch-cancel").hidden = false;
    await runBatch(jobs);
  });

  $("batch-cancel").addEventListener("click", () => abort && abort.abort());
  $("batch-download").addEventListener("click", downloadCsv);
  $("batch-again").addEventListener("click", () => {
    $("batch-form").reset();
    $("batch-images").dispatchEvent(new Event("change"));
    ["batch-results", "batch-progress"].forEach((id) => { $(id).hidden = true; });
    setMessage("batch-warning", "");
    results = [];
  });
})();
