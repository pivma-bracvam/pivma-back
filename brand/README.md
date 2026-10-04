# pi*VMA — pacote de marca

Plataforma Inteligente de Validação de Métodos Alternativos. Material extraído e organizado a partir de `source/Guia_de_estilos.pdf`.

| Quero… | Abra |
|---|---|
| Entender todas as decisões de design | [`DESIGN.md`](DESIGN.md) |
| Ver o manual de marca visual | [`manual/index.html`](manual/index.html) (duplo clique; funciona offline) |
| Usar cores/fontes no código | [`tokens/tokens.css`](tokens/tokens.css), [`fonts/fonts.css`](fonts/fonts.css), [`tokens/tailwind.preset.js`](tokens/tailwind.preset.js) |
| Logotipo | `assets/logo/svg/` (SVG) e `assets/logo/png/` |
| Ícones e símbolos (A, estrela, check, X) | `assets/symbols/svg/` |
| Favicon / PWA / ícone de app | `assets/favicon/` e `assets/app-icons/` |

## Uso rápido numa aplicação web

```html
<link rel="stylesheet" href="/brand/fonts/fonts.css">
<link rel="stylesheet" href="/brand/tokens/tokens.css">
<body style="background:var(--color-bg);color:var(--color-text);font-family:var(--font-body)">
  <img src="/brand/assets/logo/svg/pivma-logo-green.svg" alt="pi*VMA" height="32">
  <h1 style="font-family:var(--font-heading);font-weight:600">Título</h1>
</body>
```

## Origem dos arquivos

- **Extraídos do guia** (fiéis ao PDF): `pivma-logo-multicolor`, `-gray`, `-lime`, `-lime-institucional`; símbolos; `app-icon-gray-1…4`; formas em `patterns/`; `partners/`.
- **Derivados** (propostas a partir da paleta, não constam no guia): `pivma-logo-green`, `pivma-logo-paper`, `app-icon-green|blue|lime`, todos os favicons/PWA, tokens semânticos, escala tipográfica e componentes. Estão sinalizados como **[derivado]** no `DESIGN.md`.

## Pontos a confirmar com a equipe de marca

1. **Qual azul é o oficial**: `#025ecc` (página de paleta) ou `#0167f7` (usado no fundo, nas etiquetas e no ponto do logotipo).
2. **Logotipos de BraCVAM e Fiocruz** (`assets/partners/`): foram extraídos da página 1 do guia, em lima; para outros usos peça os arquivos oficiais.
3. O logotipo multicolor tem **contraste baixo** (cinza `#b2b2b2` sobre `#efefef`, 1,8:1); para telas funcionais use a versão verde.

## Licenças

Fontes **Lexend** e **Barlow**: SIL Open Font License 1.1 (arquivos `LICENSE-OFL.txt` em `fonts/`). Logotipos e identidade pi*VMA, BraCVAM e Fiocruz pertencem aos seus titulares.
