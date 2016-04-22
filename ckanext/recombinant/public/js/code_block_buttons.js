(function($){
    var codeBtnSelector = ".btn-code-lang";

    wb.doc.on("click", codeBtnSelector, function() {
      var codeBlockClass = "code-block",
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
    });
})(jQuery);
