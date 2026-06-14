--- Pandoc filter: adapt the book's display-math conventions to the LaTeX/EPUB paths.
---
--- The book Markdown authors every numbered equation as a top-level LaTeX
--- environment nested inside `$$...$$`, for example:
---
---     $$
---     \begin{equation}
---         y_k = \psi^\top_{k-1}\hat{\Theta} + \xi_k,
---     \end{equation}
---     \tag{3.1}
---     $$
---
--- Pandoc renders display math as `\[...\]`, and a top-level environment
--- (equation/align/gather/multline) opens its own math mode, so nesting it
--- there is invalid LaTeX (`! LaTeX Error: Bad math environment delimiter`).
--- MathJax on the documentation website is lenient and renders the source as
--- written, so we normalize only when building the book.
---
--- Why a filter instead of preprocessing the Markdown text: Pandoc has already
--- parsed the document, so a `Math` element gives us exactly the math content.
--- Code blocks, inline code and prose are different node types and can never be
--- touched -- unlike a regex over the raw Markdown, which would have to re-find
--- the `$$...$$` spans that Pandoc already located.

--- Manual equation labels: `\tag{3.1}` -> `\qquad\text{(3.1)}`.
--- The book uses authored numbers (e.g. "3.1", "5.2"), so amsmath
--- auto-numbering would renumber them incorrectly; a text label renders
--- identically in the PDF and EPUB outputs.
local function rewrite_tags(text)
  return (text:gsub("\\tag%s*{(.-)}", "\\qquad\\text{(%1)}"))
end

--- Drop the `equation`/`equation*` wrapper so its body sits directly in the
--- surrounding display math. The whole wrapper line is removed (including its
--- trailing newline); leaving a blank line inside `\[...\]` would itself be
--- invalid LaTeX ("Missing $ inserted").
local function drop_equation(text)
  text = text:gsub("[ \t]*\\begin%s*{equation%*?}[ \t]*\n?", "")
  text = text:gsub("[ \t]*\\end%s*{equation%*?}[ \t]*\n?", "")
  return text
end

--- Rewrite the remaining top-level environments to their math-mode-safe
--- counterparts, which are valid inside `\[...\]`. Inner environments already
--- valid in math mode (aligned, bmatrix, cases, array, ...) are left untouched.
local SAFE_ENVIRONMENT = {
  align = "aligned",
  gather = "gathered",
  multline = "aligned",
}

local function rewrite_environments(text)
  for source, target in pairs(SAFE_ENVIRONMENT) do
    text = text:gsub("(\\begin%s*){" .. source .. "%*?}", "%1{" .. target .. "}")
    text = text:gsub("(\\end%s*){" .. source .. "%*?}", "%1{" .. target .. "}")
  end
  return text
end

function Math(element)
  -- \tag is rejected by amsmath outside a numbered environment, so it must be
  -- rewritten wherever it appears -- the book uses it in inline math too.
  local text = rewrite_tags(element.text)
  -- The top-level environments only ever wrap display math.
  if element.mathtype == "DisplayMath" then
    text = drop_equation(text)
    text = rewrite_environments(text)
  end
  element.text = text
  return element
end
