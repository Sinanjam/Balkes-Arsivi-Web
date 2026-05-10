(function () {
  const code = "sinanjam";

  function loadVisitorCount() {
    const el = document.getElementById("visitor-count");
    if (!el) return;

    fetch(`https://${code}.goatcounter.com/counter/TOTAL.json`, { cache: "no-store" })
      .then((r) => {
        if (!r.ok) throw new Error("counter not ready");
        return r.json();
      })
      .then((j) => {
        el.textContent = j.count || j.count_unique || "—";
      })
      .catch(() => {
        el.textContent = "Sayaç bekleniyor";
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", loadVisitorCount);
  } else {
    loadVisitorCount();
  }

  setTimeout(loadVisitorCount, 2500);
})();
