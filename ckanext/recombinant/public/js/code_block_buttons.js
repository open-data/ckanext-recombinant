function langBtnFn() {
  var codeBlockClass = "code-block", 
    codeBtnSelector = ".btn-code-lang",
    $codeBlock = $("." + codeBlockClass),
    $codeBtn = $(codeBtnSelector),
    lang = this.className.match(/lang\-[^\s]*/)[0];
  if (lang) {
    $codeBlock
      .removeClass()
      .addClass(codeBlockClass + " " + lang);
    $codeBtn.removeClass("active");
    $(this).addClass("active");
  }
};
