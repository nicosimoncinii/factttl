# FactTTL interface decisions

The interface explains a source check beside the exact reference being checked.
Its main audience is a person reading an AI answer, not a developer inspecting
verification records. The supplied Anthropic frontend-design skill informed the
choices below.

- Palette: ink `#193b61`, paper `#f5f8fc`, clear blue `#2764a5`, supported green
  `#177a59`, unresolved amber `#9a6208`, contradictory red `#b6373e`.
- Typography: Georgia for the configuration headline, Segoe UI for controls
  and evidence. Fonts stay local; no external font request is needed.
- Layout: each reference carries its own compact indicator. Opening it brings
  a focused evidence sheet with a conclusion, observed values, source and time.
  It never opens a mixed list of unrelated link checks.
- Wording: 'Disponibilità', 'Prezzo letto', 'La notizia è stata verificata?'.
  Internal field names and raw English provider reasons are not primary copy.
- Configuration: connection state comes first, country/language second, manual
  connection details are advanced controls.
- Region is chosen explicitly; no precise location is inferred or requested.
  Country preferences do not establish an account's delivery destination.
- Source availability is distinct from factual support. A dated article is not
  automatically false, and a fetched article is not automatically verified.

Native dialog keyboard handling, visible focus, responsive width and reduced
motion are required. Status includes words and a symbol, so color is never the
only signal.
