// Re-initialize Mermaid diagrams when the Material theme palette toggles
document.addEventListener("DOMContentLoaded", function () {
  var observer = new MutationObserver(function () {
    if (typeof mermaid !== "undefined") {
      mermaid.initialize({
        startOnLoad: false,
        theme:
          document.body.getAttribute("data-md-color-scheme") === "slate"
            ? "dark"
            : "default",
      });
      mermaid.init(undefined, document.querySelectorAll(".mermaid"));
    }
  });

  observer.observe(document.body, {
    attributes: true,
    attributeFilter: ["data-md-color-scheme"],
  });
});
