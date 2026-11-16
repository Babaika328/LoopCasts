// Company fields only show when the box is ticked. Without JavaScript they stay visible.
(function () {
  var box = document.getElementById('is_company');
  var fields = document.getElementById('company-fields');
  if (!box || !fields) { return; }
  function sync() { fields.hidden = !box.checked; }
  box.addEventListener('change', sync);
  sync();
})();