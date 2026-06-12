# Templates

A `template` element generates child elements from a
[Jinja2](https://jinja.palletsprojects.com/) template instead of
hand-writing them. Two motivating cases:

- **Repetition in place** — a 4×3 thumbnail grid is one loop, not
  twelve hand-positioned elements.
- **Reuse with parameters** — a banner/title/subtitle scaffold lives in
  one file and is instantiated wherever needed, varying only a few
  declared parameters.

Plain `.slide.json` and `.deck.json` files are **never**
Jinja-processed — templating lives only in places that announce it.

## Inline templates

For short, one-off generation, put the Jinja text directly in the
element's `template` field. It must render to a JSON5 **array of
elements**:

```json5
{
  template: "[ {% for i in range(4) %} { image: \"thumbs/t{{ i }}.png\", position: [{{ 5 + i * 24 }}, 10], width: 20, height: \"auto\" }, {% endfor %} ]",
}
```

JSON5's tolerance of trailing commas makes loop-generated arrays
painless. Inline templates are one JSON5 string, so anything long or
reused belongs in a template file instead.

## Template files

A reusable template lives in a `*.elements.json.j2` file and may open
with a **front-matter** block — a JSON5 object between two `---` lines
— declaring its parameter contract. Note the syntax: unlike the
`---`-delimited front-matter convention elsewhere, this block is
**JSON5, not YAML** (one syntax across the whole format); writing YAML
here is caught with a pointed error:

```jinja
---
{
  description: "Colored banner with title and optional subtitle.",
  params: {
    title:    { type: "string", required: true },
    subtitle: { type: "string", default: "" },
    accent:   { type: "string", default: "#5EB083" },
  },
}
---
[
  { name: "banner", html: "<div style=\"width:100%;height:100%;background:{{ accent }}\"></div>",
    position: [0, 0], width: 100, height: 100 },
  { name: "title", markdown: "## {{ title }}", position: [3, 33], anchor: [0, 50],
    width: 80, color: "#ffffff" },
  {% if subtitle %}
  { name: "subtitle", markdown: "### {{ subtitle }}", position: [3, 66], anchor: [0, 50],
    width: 80, color: "#ffffff" },
  {% endif %}
]
```

Instantiate it with `template_file` + `with`:

```json5
{
  name: "header",
  template_file: "../templates/section_header.elements.json.j2",
  with: { title: "Building the stack", subtitle: "Details (1/2)" },
  position: [0, 5], width: 100, height: 15,
}
```

`scrolly schema template <path>` prints a template's contract; the
`with:` block is validated against it **before** rendering — missing
or misspelled params are precise errors, not mysteries in rendered
text.

## Slide factories

Templating also works at whole-slide granularity. A **factory** is a
`*.slide.json.j2` template rendering a complete slide object (title,
scroll behavior, elements); a **template-slide stub** is a regular
`.slide.json` file whose top level holds just the instantiation:

```json5
// slides/detail-1.slide.json — the whole file
{
  template_file: "../factories/chapter.slide.json.j2",
  with: { heading: "Building the stack", part: "1/2" },
}
```

The deck file never changes — it keeps pointing at `.slide.json`
sources and stays a pure navigation manifest. Layout lives once in the
factory; each stub holds only what varies. Front-matter params,
validation, and `scrolly expand` work exactly as for element
templates. A stub may contain nothing besides `template_file` and
`with` — every slide field comes from the factory. Suffixes declare
the render target: factories end in `.slide.json.j2`, element
templates in `.elements.json.j2`; mixing them up is a build error.

File references in a factory's output (asset paths, `*_file` fields)
resolve against the **factory's** directory.

## How an instantiation behaves

An expanded template becomes a [container](../concepts/elements.md#containers)
holding the rendered children: the element's box re-coordinates the
children (defaults: the full slide), its substrate fields animate the
group as a unit, and a `name` dot-prefixes the children's names so the
same template can be instantiated twice on one slide.

## Variables and parameters

A template's variables come from its `with:` block plus front-matter
defaults — nothing else. Values can be any JSON value, including
nested arrays and objects; Jinja iterates them naturally
(`{% for team in teams %} … {{ team.name }}`). Declared `type:`s check
the top level only (`string`, `number`, `integer`, `boolean`, `array`,
`object`); structure inside `array` / `object` values is the caller's
responsibility — a mismatch surfaces as a strict-undefined render
error naming the template.

## Debugging

Rendering is strict and the errors are numbered: Jinja syntax (E801,
which also reminds you of `{% raw %}…{% endraw %}` for literal `{{`),
undefined variables (E802), invalid rendered output (E803, with an
excerpt), param mismatches (E804), other render failures (E805).

When the rendered text itself is the question, expand it:

```sh
scrolly expand deck.deck.json --slide detail-1
```

This renders each template instantiation on the slide with its actual
`with:` values and prints the post-Jinja, pre-validation text. There
is no hypothetical-render mode: to explore a template, write a small
example slide and expand it.

## Paths

`template_file` paths resolve relative to the file they appear in;
`{% include %}` / `{% import %}` inside a template file resolve within
that file's directory tree. Asset and `*_file` references inside the
rendered output resolve relative to the **template file** (inline
templates: the slide file). Everything stays subject to the deck-root
confinement rule (see [Working with assets](assets.md)).
