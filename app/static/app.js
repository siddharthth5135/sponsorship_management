(function () {
  const searchInputs = document.querySelectorAll("[data-list-search]");
  searchInputs.forEach((input) => {
    const target = document.querySelector(input.dataset.listSearch);
    if (!target) return;
    input.addEventListener("input", () => {
      const q = input.value.trim().toLowerCase();
      target.querySelectorAll("[data-searchable]").forEach((row) => {
        const text = row.getAttribute("data-searchable") || "";
        row.hidden = q.length > 0 && !text.toLowerCase().includes(q);
      });
    });
  });

  document.querySelectorAll("[data-toggle]").forEach((btn) => {
    const panel = document.querySelector(btn.dataset.toggle);
    if (!panel) return;
    btn.addEventListener("click", () => {
      panel.classList.toggle("is-open");
      btn.setAttribute("aria-expanded", panel.classList.contains("is-open"));
    });
  });

  document.querySelectorAll("[data-copy]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const src = document.querySelector(btn.dataset.copy);
      if (!src) return;
      try {
        await navigator.clipboard.writeText(src.innerText);
        const old = btn.textContent;
        btn.textContent = "Copied";
        setTimeout(() => (btn.textContent = old), 1500);
      } catch (e) {
        window.getSelection().selectAllChildren(src);
      }
    });
  });

  document.querySelectorAll("[data-filter-chip]").forEach((chip) => {
    chip.addEventListener("click", () => {
      const group = chip.closest("[data-filter-group]");
      const list = document.querySelector(group?.dataset.filterGroup);
      const filter = chip.dataset.filterChip;
      if (!list) return;
      group.querySelectorAll("[data-filter-chip]").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      list.querySelectorAll("[data-quality]").forEach((row) => {
        const q = row.getAttribute("data-quality");
        row.hidden = filter !== "all" && q !== filter;
      });
    });
  });

  const menuBtn = document.getElementById("menu-toggle");
  const menuClose = document.getElementById("menu-close");
  const scrim = document.getElementById("nav-scrim");
  const closeNav = () => {
    document.body.classList.remove("nav-open");
    if (scrim) scrim.hidden = true;
    document.body.style.overflow = "";
  };
  const openNav = () => {
    document.body.classList.add("nav-open");
    if (scrim) scrim.hidden = false;
    document.body.style.overflow = "hidden";
  };
  if (menuBtn) {
    menuBtn.addEventListener("click", () => {
      if (document.body.classList.contains("nav-open")) closeNav();
      else openNav();
    });
  }
  if (menuClose) menuClose.addEventListener("click", closeNav);
  if (scrim) scrim.addEventListener("click", closeNav);
  document.querySelectorAll(".sidebar a").forEach((a) => a.addEventListener("click", closeNav));
  window.addEventListener("resize", () => {
    if (window.innerWidth > 960) closeNav();
  });
})();
