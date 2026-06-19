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

  const previewEl = document.getElementById(`preview-${type}`);
  const dropEl = document.getElementById(`drop-${type}`);

  if (type === "mockup" && file.type === "application/pdf") {
    document.getElementById("img-mockup").classList.add("hidden");
    document.getElementById("pdf-mockup-name").textContent = file.name;
    document.getElementById("pdf-mockup-indicator").classList.remove("hidden");
    previewEl.classList.remove("hidden");
    dropEl.classList.add("hidden");
    updateCompareBtn();
  } else {
    const reader = new FileReader();
    reader.onload = (e) => {
      const imgEl = document.getElementById(`img-${type}`);
      imgEl.src = e.target.result;
      imgEl.classList.remove("hidden");
      if (type === "mockup") {
        document.getElementById("pdf-mockup-indicator").classList.add("hidden");
      }
      previewEl.classList.remove("hidden");
      dropEl.classList.add("hidden");
      updateCompareBtn();
    };
    reader.readAsDataURL(file);
  }
}

function clearImage(type) {
  state[type === "mockup" ? "mockupFile" : "photoFile"] = null;
  const imgEl = document.getElementById(`img-${type}`);
  imgEl.src = "";
  imgEl.classList.remove("hidden");
  if (type === "mockup") {
    document.getElementById("pdf-mockup-indicator").classList.add("hidden");
    document.getElementById("input-mockup").value = "";
  } else {
    document.getElementById("input-camera").value = "";
    document.getElementById("input-gallery").value = "";
  }
  document.getElementById(`preview-${type}`).classList.add("hidden");
  document.getElementById(`drop-${type}`).classList.remove("hidden");
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
    letterform_accuracy: "Letterform accuracy",
    text_spelling:       "Spelling & accents",
    spine_quality:       "Spine quality",
    color_matching:      "Color matching",
    face_detail:         "Face detail",
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
  const sbsMockup = document.getElementById("sbs-mockup");
  const sbsMockupPdf = document.getElementById("sbs-mockup-pdf");
  if (state.mockupFile && state.mockupFile.type === "application/pdf") {
    sbsMockup.classList.add("hidden");
    sbsMockupPdf.textContent = state.mockupFile.name;
    sbsMockupPdf.classList.remove("hidden");
  } else {
    sbsMockup.src = document.getElementById("img-mockup").src;
    sbsMockup.classList.remove("hidden");
    sbsMockupPdf.classList.add("hidden");
  }
  document.getElementById("sbs-photo").src = document.getElementById("img-photo").src;

  // Annotated photo + numbered issues
  const annotatedWrap = document.getElementById("annotated-wrap");
  const annotationsLayer = document.getElementById("annotations-layer");
  const numberedList = document.getElementById("issues-numbered-list");
  annotationsLayer.innerHTML = "";
  numberedList.innerHTML = "";

  if (data.issues && data.issues.length > 0) {
    document.getElementById("annotated-photo").src = document.getElementById("img-photo").src;
    data.issues.forEach((issue, i) => {
      const num = i + 1;
      const text = typeof issue === "string" ? issue : issue.text;
      const x = typeof issue === "object" && issue.x != null ? issue.x : null;
      const y = typeof issue === "object" && issue.y != null ? issue.y : null;

      numberedList.innerHTML += `<li>${text}</li>`;

      if (x !== null && y !== null) {
        const marker = document.createElement("div");
        marker.className = "annotation-marker";
        marker.style.left = `${x}%`;
        marker.style.top = `${y}%`;
        marker.textContent = num;
        annotationsLayer.appendChild(marker);
      }
    });
    annotatedWrap.classList.remove("hidden");
  } else {
    annotatedWrap.classList.add("hidden");
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
    const imgEl = document.getElementById(`img-${t}`);
    imgEl.src = "";
    imgEl.classList.remove("hidden");
    document.getElementById(`preview-${t}`).classList.add("hidden");
    document.getElementById(`drop-${t}`).classList.remove("hidden");
  });
  document.getElementById("pdf-mockup-indicator").classList.add("hidden");
  document.getElementById("sbs-mockup-pdf").classList.add("hidden");
  document.getElementById("annotated-wrap").classList.add("hidden");
  document.getElementById("annotations-layer").innerHTML = "";
  document.getElementById("issues-numbered-list").innerHTML = "";
  document.getElementById("strengths-wrap").classList.add("hidden");
  document.getElementById("input-mockup").value = "";
  document.getElementById("input-camera").value = "";
  document.getElementById("input-gallery").value = "";
  document.getElementById("results").classList.add("hidden");
  document.getElementById("btn-compare").classList.remove("hidden");
  updateCompareBtn();
  window.scrollTo({ top: 0, behavior: "smooth" });
}
