# Direct paragraph editing

The default editor now uses direct, automatically saved paragraph editing. See [the current guide](EDITOR_GUIDE.md). There is no separate word popup, Save button or persistent underline. Following words shift right and wrap onto subsequent lines at the original font size. Paragraphs grow downward into available space, preserving a usable original embedded font and colour where supported. The actual original encoded characters are removed before the replacement vector object is written.

The earlier `replace-word` and `replace-readable` API operations remain available for compatibility. Their word-range and free-space text-box behaviours are not the default inline UI. Nested text and many decorative/font-subset cases now have true removal/reconstruction paths with font notices. Outlined artwork and complex scripts still have limits. Image text still requires OCR.
