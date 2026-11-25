// The "Print or save as PDF" button on the invoice page.
(function () {
  var button = document.getElementById('print-invoice');
  if (!button) { return; }
  button.addEventListener('click', function (event) { event.preventDefault(); window.print(); });
})();