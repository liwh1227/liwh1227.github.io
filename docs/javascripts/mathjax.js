window.MathJax = {
  tex: {
    inlineMath: [["\\(", "\\)"]],
    displayMath: [["$$", "$$"], ["\\[", "\\]"]],
    processEscapes: true,
    processEnvironments: true
  },
  options: {
    ignoreHtmlClass: ".*|",
    processHtmlClass: "arithmatex"
  }
  // 这里不需要配置 fontURL 了，因为 SVG 不需要外部字体
};

document$.subscribe(() => {
  MathJax.typesetPromise()
})