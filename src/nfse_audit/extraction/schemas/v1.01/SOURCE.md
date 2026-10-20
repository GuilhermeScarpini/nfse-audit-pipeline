# Official NFS-e schemas — layout v1.01

Copied unmodified from the official package published by the Sistema Nacional NFS-e:

- Package: `NFSe-ESQUEMAS_XSD-v1.01-20260209`
- URL: https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/documentacao-atual/nfse-esquemas_xsd-v1-01-20260209.zip
- Package SHA-256: `e7935cbd9470527c6cc32984c1b2263e614183bf0139ce2733eaaed2de9a8072`
- Retrieved: 2026-10-20

| File | SHA-256 |
|---|---|
| DPS_v1.01.xsd | `fe45e5250a48e519aba89fc6a472863b8e602ed957778fb64692804933a00d0c` |
| NFSe_v1.01.xsd | `af0bd2d8c50acba3d9c3f3f515426eca083b3f66e3211ce8dd48a7cf101818b8` |
| tiposComplexos_v1.01.xsd | `e8e09d525574cc224ca6d1f8d8eb0366043ab2a3aa8d0d234058e6244d60e371` |
| tiposSimples_v1.01.xsd | `830ea116c34d7310699e34b214b7214a65f7e5d3b1f09aeaa702f7e3f4283b17` |
| xmldsig-core-schema.xsd | `49848f732663aecb618d72ad6130c5c3240f0a10f3a1a8544b7d48a6c726046f` |

The files are never edited. Three adaptations are applied **in memory** when the
schema is loaded (see `nfse_audit/extraction/schema.py`):

1. `TSCNPJ` accepts alphanumeric CNPJ (`[0-9A-Z]{12}[0-9]{2}`). Alphanumeric CNPJ
   has been in production since 2026-08-10, but the published v1.01 schema still
   says `[0-9]{14}`.
2. `ds:Signature` in `TCNFSe` becomes optional. Synthetic documents are
   deliberately unsigned: they are test data (`tpAmb=2`), not fiscal documents.
3. `TSSerieDPS` pattern `^0{0,4}\d{1,5}$` loses its `^`/`$`. XSD patterns are
   implicitly anchored and those characters are literals in XSD regex, so a
   conforming validator (libxml2) rejects every series. Lenient validators that
   treat them as anchors (e.g. .NET) accept the same values as the fixed pattern.
