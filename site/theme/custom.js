(function () {
  if (location.pathname.endsWith("print.html")) return;

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
      var darkThemes = ["coal", "navy", "ayu"];
      function apply() {
        artalk.setDarkMode(
          darkThemes.indexOf(document.documentElement.className) !== -1
        );
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
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();
