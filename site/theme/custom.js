(function () {
  if (location.pathname.endsWith("print.html")) return;

  function splitBookTitle() {
    var title = document.querySelector(".menu-title");
    if (!title || title.dataset.split) return;
    var text = title.textContent.trim();
    var index = text.indexOf(". ");
    if (index === -1) return;
    title.textContent = text.slice(0, index);
    var lineBreak = document.createElement("br");
    var subtitle = document.createElement("span");
    subtitle.className = "book-subtitle";
    subtitle.textContent = text.slice(index + 2);
    title.appendChild(lineBreak);
    title.appendChild(subtitle);
    title.dataset.split = "1";
  }

  function rootPrefix() {
    return typeof path_to_root === "string" ? path_to_root : "";
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, function (ch) {
      return {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      }[ch];
    });
  }

  function makeSnippet(text, index, queryLength) {
    var start = Math.max(0, index - 70);
    var end = Math.min(text.length, index + queryLength + 130);
    var before = text.slice(start, index);
    var match = text.slice(index, index + queryLength);
    var after = text.slice(index + queryLength, end);
    return (
      (start > 0 ? "… " : "") +
      escapeHtml(before) +
      "<mark>" +
      escapeHtml(match) +
      "</mark>" +
      escapeHtml(after) +
      (end < text.length ? " …" : "")
    );
  }

  function mountSearch() {
    var sidebar = document.querySelector(".sidebar-scrollbox");
    if (!sidebar) return;

    var box = document.createElement("div");
    box.className = "book-search";
    box.innerHTML =
      '<input type="search" id="book-search-input" ' +
      'placeholder="Поиск по книге…" autocomplete="off" spellcheck="false" ' +
      'aria-label="Поиск по книге">' +
      '<div class="book-search-results" hidden></div>';
    sidebar.insertBefore(box, sidebar.firstChild);

    var input = box.querySelector("#book-search-input");
    var results = box.querySelector(".book-search-results");
    var searchData = null;
    var searchLoading = false;
    var timer = null;

    function loadData(callback) {
      if (searchData) {
        callback();
        return;
      }
      if (searchLoading) return;
      searchLoading = true;
      if (window.bookSearchData) {
        searchData = window.bookSearchData;
        searchLoading = false;
        callback();
        return;
      }
      var script = document.createElement("script");
      script.src = rootPrefix() + "search-data.js";
      script.onload = function () {
        searchData = window.bookSearchData || [];
        searchLoading = false;
        callback();
      };
      script.onerror = function () {
        searchLoading = false;
        results.hidden = false;
        results.innerHTML =
          '<p class="book-search-empty">Поиск временно недоступен.</p>';
      };
      document.head.appendChild(script);
    }

    function runSearch() {
      var query = input.value.trim();
      if (query.length < 2) {
        results.hidden = true;
        results.innerHTML = "";
        return;
      }
      var lower = query.toLowerCase();
      loadData(function () {
        var found = [];
        var limit = 50;
        for (var i = 0; i < searchData.length; i++) {
          var item = searchData[i];
          var text = item.text || "";
          var index = text.toLowerCase().indexOf(lower);
          var titleMatch =
            (item.title || "").toLowerCase().indexOf(lower) !== -1;
          if (index !== -1 || titleMatch) {
            found.push({ item: item, index: index });
            if (found.length >= limit) break;
          }
        }
        results.hidden = false;
        if (!found.length) {
          results.innerHTML =
            '<p class="book-search-empty">Ничего не найдено.</p>';
          return;
        }
        var html =
          '<p class="book-search-count">Найдено: ' +
          found.length +
          "</p><ul>";
        for (var j = 0; j < found.length; j++) {
          var entry = found[j];
          var snippet;
          if (entry.index !== -1) {
            snippet = makeSnippet(
              entry.item.text,
              entry.index,
              lower.length
            );
          } else {
            snippet =
              escapeHtml(entry.item.text.slice(0, 160)) +
              (entry.item.text.length > 160 ? " …" : "");
          }
          html +=
            '<li><a href="' +
            rootPrefix() +
            escapeHtml(entry.item.url) +
            '"><span class="book-search-title">' +
            escapeHtml(entry.item.title) +
            '</span><span class="book-search-snippet">' +
            snippet +
            "</span></a></li>";
        }
        html += "</ul>";
        results.innerHTML = html;
      });
    }

    input.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(runSearch, 120);
    });

    input.addEventListener("focus", function () {
      if (input.value.trim().length >= 2) runSearch();
    });

    input.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        input.value = "";
        results.hidden = true;
        input.blur();
      }
      if (event.key === "Enter") {
        var first = results.querySelector("a");
        if (first) {
          event.preventDefault();
          window.location.href = first.href;
        }
      }
    });

    document.addEventListener("keydown", function (event) {
      if (
        event.key === "/" &&
        !/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName)
      ) {
        event.preventDefault();
        input.focus();
      }
    });

    document.addEventListener("click", function (event) {
      if (!box.contains(event.target)) results.hidden = true;
    });
  }

  function mount() {
    var main = document.querySelector("main");
    if (!main) return;
    var heading = document.createElement("h2");
    heading.textContent = "Комментарии";
    var container = document.createElement("div");
    container.id = "artalk-comments";
    main.appendChild(heading);
    main.appendChild(container);

    var link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "https://comments.spkenny.ru/dist/Artalk.css";
    document.head.appendChild(link);

    var script = document.createElement("script");
    script.src = "https://comments.spkenny.ru/dist/Artalk.js";
    script.onload = function () {
      var artalk = Artalk.init({
        el: "#artalk-comments",
        server: "https://comments.spkenny.ru",
        site: "Интернат",
        pageKey: location.pathname,
        pageTitle: document.title,
        locale: "ru"
      });
      function isDark() {
        var classList = document.documentElement.classList;
        return classList.contains("coal") || classList.contains("navy") || classList.contains("ayu");
      }
      function apply() {
        artalk.setDarkMode(isDark());
      }
      apply();
      new MutationObserver(apply).observe(document.documentElement, {
        attributes: true,
        attributeFilter: ["class"]
      });
    };
    document.body.appendChild(script);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      splitBookTitle();
      mountSearch();
      mount();
    });
  } else {
    splitBookTitle();
    mountSearch();
    mount();
  }
})();
