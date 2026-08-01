function setLang(lang) {
  document.body.className = 'lang-' + lang;
  ['ja','en','it'].forEach(function(l) {
    var btn = document.getElementById('btn-' + l);
    if (btn) btn.classList.toggle('active', l === lang);
  });
}
