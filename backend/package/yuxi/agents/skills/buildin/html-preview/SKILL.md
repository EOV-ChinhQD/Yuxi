---
name: html-preview
description: "Use Markdown `html:preview` fences to output lightweight static HTML/CSS visualizations. Use when plain Markdown cannot clearly express numeric comparisons, hierarchies, processes, timelines, key metrics, or layout sketches, or when the user explicitly asks for an HTML preview visualization. Do not use when asking for HTML source code, tutorial examples, or copyable code."
---

# HTML Preview

Use Markdown as the main body of the answer. Only add a static
`html:preview` component when visualization clearly lowers comprehension cost;
when headings, lists, tables, or code blocks are already clear enough, keep
using plain Markdown.

Output in the following order:

1. Write conclusions and necessary explanations in plain Markdown first.
2. Write the opening fence ```` ```html:preview ```` flush left. The fence may have at most 3 leading spaces, otherwise the frontend treats it as source code.
3. Inside the fence, write self-contained static `<style>` and semantic HTML.
4. Write the closing fence ```` ``` ```` flush left.
5. After the fence, supplement background, risks, full details, and sources in plain Markdown.

## Content boundaries

- Output only static HTML/CSS. Do not write JavaScript, and do not use forms, iframes, objects, or embeds.
- You may reference public, stable, login-free HTTPS images or fonts, but core information must remain readable when external links fail.
- Do not reference intranet URLs, temporary addresses, authenticated resources, or links containing user credentials.
- Do not treat the component as a full page or body container; do not build navbars, footers, login states, complex buttons, marketing heroes, or multi-screen pages.
- Do not put long narratives, full reports, long tables, or long lists inside the component. Put background, reasoning, risks, details, and sources in plain Markdown.
- When the user asks for HTML source code, tutorial examples, or copyable code, use a plain `html` code block, not `html:preview`.

## Layout constraints

- Design for the default `800px × 360px` size and allow the container width to vary; the frontend displays up to `700px` high, scrolling inside the preview beyond that.
- Stay responsive with `max-width: 100%`, `box-sizing: border-box`, flexible grids, wrapping, and moderate spacing.
- Do not hardcode the overall canvas height. Core information should be readable at the default size without scrolling; reduce content when it does not fit.
- Show at most 1 short title, 3–5 key metrics, or one short comparison set. With more than 6 data items, summarize as trends, ranges, outliers, or Top 3.
- Use short labels, numbers, units, status words, and very short notes; keep each note under ~20 characters.
- The outer layer already provides rounded corners, borders, and clipping. Do not add another card shell, page background, large radius, shadow, thick border, or extra margin to the outermost layer.
- Stay restrained and readable, preferring compact metric groups, summary tables, comparison bars, status tags, timelines, or simple relationship diagrams.

## Failure handling

If the content cannot be expressed within the static, safety, and length boundaries above, fall back to plain Markdown and state the limitation explicitly. Do not output broken fences, inaccessible resources, or previews that require scripts to understand.
