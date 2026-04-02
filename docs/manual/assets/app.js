(function () {
  function normalise(text) {
    return String(text || "").toLowerCase();
  }

  function ensureTutorialNav() {
    const nav = document.querySelector(".nav");
    if (!nav || nav.querySelector("[data-nav='tutorial']")) return;
    const link = document.createElement("a");
    link.setAttribute("data-nav", "tutorial");
    link.setAttribute("href", "tutorial.html");
    link.textContent = "Tutorial";
    const apisLink = nav.querySelector("[data-nav='apis']");
    if (apisLink) {
      nav.insertBefore(link, apisLink);
    } else {
      nav.appendChild(link);
    }
  }

  function setActiveNav() {
    const page = document.body.getAttribute("data-page");
    document.querySelectorAll("[data-nav]").forEach((link) => {
      if (link.getAttribute("data-nav") === page) {
        link.classList.add("active");
      }
    });
  }

  function wireSearchForms() {
    document.querySelectorAll(".search-form").forEach((form) => {
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        const input = form.querySelector("input[name='q']");
        const q = input ? input.value.trim() : "";
        const target = form.getAttribute("data-search-target") || "search.html";
        window.location.href = target + (q ? ("?q=" + encodeURIComponent(q)) : "");
      });
    });
  }

  function renderSearchResults() {
    const container = document.getElementById("searchResults");
    if (!container || !window.MANUAL_SEARCH_INDEX) return;
    const params = new URLSearchParams(window.location.search);
    const query = (params.get("q") || "").trim();
    const display = document.getElementById("searchQuery");
    if (display) display.textContent = query || "all pages";
    if (!query) {
      container.innerHTML = "<div class='search-result'><h3>Type a search term</h3><p>Try widget names, API endpoints, MCP tools, or workflow names such as <code>Run Analysis</code>.</p></div>";
      return;
    }
    const q = normalise(query);
    const results = window.MANUAL_SEARCH_INDEX.filter((item) => {
      return [item.title, item.keywords, item.body].some((field) => normalise(field).includes(q));
    });
    if (!results.length) {
      container.innerHTML = "<div class='search-result'><h3>No matches</h3><p>Try broader terms such as <code>controller</code>, <code>MCP</code>, <code>profile</code>, <code>precision</code>, or <code>optimisation</code>.</p></div>";
      return;
    }
    container.innerHTML = results.map((item) => (
      "<article class='search-result'>" +
      "<div class='kicker'>" + item.section + "</div>" +
      "<h3><a href='" + item.url + "'>" + item.title + "</a></h3>" +
      "<p>" + item.body + "</p>" +
      "</article>"
    )).join("");
  }

  document.addEventListener("DOMContentLoaded", function () {
    ensureTutorialNav();
    setActiveNav();
    wireSearchForms();
    renderSearchResults();
  });
})();
