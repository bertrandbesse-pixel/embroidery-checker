/* ── STATE ────────────────────────────────── */
const state = { mockupFile: null, photoFile: null };

/* ── IMAGE INPUTS ─────────────────────────── */
document.getElementById("input-mockup").addEventListener("change", (e) => {
  handleFile(e.target.files[0], "mockup");
});
document.getElementById("input-camera").addEventListener("change", (e) => {
  handleFile(e.target.files[0], "photo");
});
document.getElementById("input-gallery").addEventListener("change", (e) => {
  handleFile(e.target.files[0], "photo");
});

function handleFile(file, type) {
  if (!file) return;
  state[type === "mockup" ? "mockupFile" : "photoFile"] = file;
  const reader = new FileReader();
  reader.onload = (e) => {
    document.getElementById(`img-${type}`).src = e.target.result;
    document.getElementById(`preview-${type}`).classList.remove("hidden");
    document.getElementById(`drop-${type}`).classList.add("hidden");
    updateCompareBtn();
  };
  reader.readAsDataURL(file);
}

function clearImage(type) {
  state[type === "mockup" ? "mockupFile" : "photoFile"] = null;
  document.getElementById(`img-${type}`).src = "";
  document.getElementById(`preview-${type}`).classList.add("hidden");
  document.getElementById(`drop-${type}`).classList.remove("hidden");
  document.getElementById(`input-${type === "mockup" ? "mockup" : "camera"}`).value = "";
  document.getElementById(`input-${type === "photo" ? "gallery" : "mockup"}`).value = "";
  updateCompareBtn();
}

function updateCompareBtn() {
  document.getElementById("btn-compare").disabled = !(state.mockupFile && state.photoFile);
}

/* ── COMPARE ──────────────────────────────── */
document.getElementById("btn-compare").addEventListener("click", async () => {
  document.getElementById("btn-compare").classList.add("hidden");
  document.getElementById("results").classList.add("hidden");
  document.getElementById("loading").classList.remove("hidden");

  const form = new FormData();
  form.append("mockup", state.mockupFile);
  form.append("photo", state.photoFile);

  try {
    const res = await fetch("/api/compare", { method: "POST", body: form });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    renderResults(data);
  } catch (err) {
    alert("Analysis failed. Please try again.\n\n" + err.message);
    document.getElementById("btn-compare").classList.remove("hidden");
  } finally {
    document.getElementById("loading").classList.add("hidden");
  }
});

/* ── RENDER RESULTS ───────────────────────── */
function renderResults(data) {
  const verdict = data.verdict.toLowerCase().replace("needs review", "review").replace(" ", "-");
  const verdictClass = verdict === "approved" ? "approved" : verdict === "rejected" ? "rejected" : "review";
  const icons = { approved: "✅", review: "⚠️", rejected: "❌" };
  const labels = { approved: "Approved", review: "Needs Review", rejected: "Rejected" };

  // Verdict banner
  const banner = document.getElementById("verdict-banner");
  banner.className = `verdict-banner ${verdictClass}`;
  document.getElementById("verdict-icon").textContent = icons[verdictClass];
  document.getElementById("verdict-label").textContent = labels[verdictClass];
  document.getElementById("verdict-reason").textContent = data.verdict_reason;

  // Score ring animation
  const score = data.overall_score;
  const circumference = 326.7;
  const offset = circumference - (score / 100) * circumference;
  const ring = document.getElementById("ring-fill");
  ring.className = `ring-fill ${verdictClass}`;
  setTimeout(() => { ring.style.strokeDashoffset = offset; }, 50);

  // Score description
  const descMap = { approved: "The embroidery meets quality standards.", review: "Minor adjustments may be required.", rejected: "Significant rework needed before approval." };
  document.getElementById("score-desc").textContent = descMap[verdictClass];

  // Animate score number
  let current = 0;
  const step = score / 40;
  const scoreEl = document.getElementById("score-number");
  const interval = setInterval(() => {
    current = Math.min(current + step, score);
    scoreEl.textContent = Math.round(current);
    if (current >= score) clearInterval(interval);
  }, 25);

  // Dimension bars
  const dimNames = {
    composition: "Composition",
    text_accuracy: "Text accuracy",
    color_matching: "Color matching",
    detail_quality: "Detail quality",
    edge_definition: "Edge definition",
  };
  const dimList = document.getElementById("dim-list");
  dimList.innerHTML = "";
  for (const [key, label] of Object.entries(dimNames)) {
    const d = data.dimensions[key];
    if (!d) continue;
    const colorClass = d.score >= 80 ? "high" : d.score >= 60 ? "mid" : "low";
    dimList.innerHTML += `
      <div class="dim-item">
        <div class="dim-header">
          <span class="dim-name">${label}</span>
          <span class="dim-score">${d.score}%</span>
        </div>
        <div class="dim-bar-bg">
          <div class="dim-bar-fill ${colorClass}" style="width:0%" data-target="${d.score}%"></div>
        </div>
        <div class="dim-comment">${d.comment}</div>
      </div>`;
  }
  // Animate bars
  setTimeout(() => {
    dimList.querySelectorAll(".dim-bar-fill").forEach((bar) => {
      bar.style.width = bar.dataset.target;
    });
  }, 100);

  // Side-by-side
  document.getElementById("sbs-mockup").src = document.getElementById("img-mockup").src;
  document.getElementById("sbs-photo").src = document.getElementById("img-photo").src;

  // Issues
  const issuesList = document.getElementById("issues-list");
  issuesList.innerHTML = "";
  if (data.issues && data.issues.length > 0) {
    data.issues.forEach((issue) => {
      issuesList.innerHTML += `<li>${issue}</li>`;
    });
    document.getElementById("issues-wrap").classList.remove("hidden");
  } else {
    document.getElementById("issues-wrap").classList.add("hidden");
  }

  // Strengths
  const strengthsList = document.getElementById("strengths-list");
  strengthsList.innerHTML = "";
  if (data.strengths && data.strengths.length > 0) {
    data.strengths.forEach((s) => {
      strengthsList.innerHTML += `<li>${s}</li>`;
    });
    document.getElementById("strengths-wrap").classList.remove("hidden");
  } else {
    document.getElementById("strengths-wrap").classList.add("hidden");
  }

  document.getElementById("results").classList.remove("hidden");
  document.getElementById("results").scrollIntoView({ behavior: "smooth" });
}

/* ── RESET ────────────────────────────────── */
function resetAll() {
  state.mockupFile = null;
  state.photoFile = null;
  ["mockup", "photo"].forEach((t) => {
    document.getElementById(`img-${t}`).src = "";
    document.getElementById(`preview-${t}`).classList.add("hidden");
    document.getElementById(`drop-${t}`).classList.remove("hidden");
  });
  document.getElementById("input-mockup").value = "";
  document.getElementById("input-camera").value = "";
  document.getElementById("input-gallery").value = "";
  document.getElementById("results").classList.add("hidden");
  document.getElementById("btn-compare").classList.remove("hidden");
  updateCompareBtn();
  window.scrollTo({ top: 0, behavior: "smooth" });
}
