(function () {
  "use strict";

  function isEditableInput(el) {
    if (!el || !el.tagName) {
      return false;
    }

    if (el.isContentEditable) {
      return false;
    }

    if (el.tagName !== "INPUT") {
      return false;
    }

    var inputType = (el.type || "").toLowerCase();
    return ![
      "button",
      "submit",
      "reset",
      "checkbox",
      "radio",
      "file",
    ].includes(inputType);
  }

  document.addEventListener("keydown", function (event) {
    if (event.key !== "Enter") {
      return;
    }

    if (
      event.defaultPrevented ||
      event.repeat ||
      event.isComposing ||
      event.shiftKey ||
      event.ctrlKey ||
      event.altKey ||
      event.metaKey
    ) {
      return;
    }

    if (!isEditableInput(document.activeElement)) {
      return;
    }

    var solveButton = document.getElementById("btn-solve");
    if (!solveButton || solveButton.disabled) {
      return;
    }

    event.preventDefault();
    solveButton.click();
  });
})();