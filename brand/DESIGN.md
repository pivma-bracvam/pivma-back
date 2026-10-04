# DESIGN.md — pi*VMA

> **Plataforma Inteligente de Validação de Métodos Alternativos**
> Guia de design para quem constrói a aplicação (devs, designers, agentes de código).
> Fonte: *Guia de estilos pi\*VMA* (`source/Guia_de_estilos.pdf`, 7 páginas).

**Como ler este documento.** Cada decisão vem marcada com a sua origem:

- **[guia]** — lido diretamente do PDF (cor, fonte, forma, layout).
- **[derivado]** — proposta minha para uso em interface, porque o guia não cobre (escala tipográfica, estados, espaçamento, regras de uso do logotipo). Revise com a equipe de marca antes de tratar como oficial.

---

## 1. A marca em uma frase

O guia define o projeto como uma plataforma de software que apoia **a submissão, a validação e a rastreabilidade** da criação de novos métodos alternativos, assegurando **confiabilidade, transparência e relevância científica** [guia, p.3].

Tradução para design: **científico, confiável e limpo**, mas com personalidade — cores saturadas, geometria arredondada e um símbolo (o "A" em arco com estrela de brilho) que dá identidade sem ruído. Parceiras institucionais no guia: **BraCVAM** e **Fiocruz** [guia, p.1].

Nome: escreve-se **pi\*VMA** no texto corrido (o asterisco faz parte do nome). No guia aparece também como "Pi\*VMA" no rodapé editorial.

---

## 2. Estrutura da pasta

```
brand/
├── DESIGN.md                  ← este arquivo
├── README.md                  ← mapa rápido da pasta
├── manual/index.html          ← manual de marca visual (abra no navegador)
├── tokens/
│   ├── tokens.css             ← variáveis CSS (cores, tipografia, raios, espaçamento)
│   ├── colors.json            ← cores com origem e uso
│   └── tailwind.preset.js     ← preset Tailwind
├── fonts/                     ← Lexend + Barlow (woff2, OFL) e fonts.css
├── assets/
│   ├── logo/{svg,png}/        ← logotipo em 6 versões
│   ├── symbols/{svg,png}/     ← "A", estrela, check, X (+ versões currentColor)
│   ├── app-icons/{svg,png}/   ← ícones de app
│   ├── favicon/               ← favicon.ico/svg, apple-touch, PWA 192/512/maskable, manifest
│   ├── partners/              ← BraCVAM e Fiocruz (extraídos da p.1)
│   └── patterns/              ← formas decorativas de fundo
└── source/                    ← PDF original + páginas em PNG (referência)
```

Todos os SVG foram **extraídos como vetor do próprio PDF** (o PDF não tem imagens raster), então não há perda de qualidade.

---

## 3. Cores

### 3.1 Paleta da marca [guia, p.5]

| Token | Hex | Papel sugerido |
|---|---|---|
| `--pivma-green` | `#014e2a` | Cor principal: fundos institucionais, texto, botão primário |
| `--pivma-lime` | `#a3ed40` | Destaque; logotipo e texto sobre fundo escuro |
| `--pivma-blue-deep` | `#025ecc` | Azul da paleta; formas decorativas (p.3) |
| `--pivma-yellow` | `#d9ae21` | Alerta / destaque secundário |
| `--pivma-red` | `#db3016` | Erro; o "V" do logotipo; fundo da p.4 |
| `--pivma-paper` | `#efefef` | Fundo base de telas e documentos |

**Atenção — dois azuis.** A página de paleta (p.5) mostra `#025ecc`, mas o **azul vivo realmente usado** no fundo da p.3, nas etiquetas da p.2 e no ponto do "A" do logotipo é **`#0167f7`**. Mantive os dois: `--pivma-blue` (`#0167f7`, azul de ação/foco) e `--pivma-blue-deep` (`#025ecc`, azul da paleta). Vale confirmar com quem fez o guia qual é o oficial para botões e links.

### 3.2 Cinzas [guia, p.5–7]

`#b2b2b2` (logotipo monocromático), `#9d9d9c`, `#878787`, `#706f6f` (a escala dos ícones de app na p.6), `#575756` (contorno), `#dbdbdb` a 71 % de opacidade (formas de fundo, p.7).

### 3.3 Papéis semânticos [derivado]

| Papel | Cor | Observação |
|---|---|---|
| Sucesso / aprovado | `#014e2a` | Combina com o ícone de check (p.4) |
| Alerta | `#d9ae21` | **Só texto escuro sobre ele** (ver 3.4) |
| Erro / reprovado | `#db3016` | Combina com o ícone X (p.4) |
| Informação / foco / link | `#0167f7` | |
| Texto secundário | `#3d6b55` | 5,3:1 sobre `#efefef` |

Num produto de **validação**, status (aprovado, em análise, reprovado) é central: nunca dependa só da cor — combine sempre com o ícone (check / X) e com texto.

### 3.4 Contraste (WCAG 2.x, calculado)

Pares que a marca usa e se passam no nível AA (texto normal ≥ 4,5:1; texto grande ≥ 24 px, ou 18,66 px em negrito, ≥ 3:1):

| Combinação | Razão | Uso permitido |
|---|---|---|
| Verde `#014e2a` sobre branco | 9,9:1 | ✅ qualquer texto |
| Verde `#014e2a` sobre `#efefef` | 8,6:1 | ✅ qualquer texto |
| Lima `#a3ed40` sobre verde `#014e2a` | 6,9:1 | ✅ qualquer texto (par principal do guia) |
| Branco sobre azul `#0167f7` | 4,9:1 | ✅ botões e texto |
| Branco sobre `#db3016` | 4,7:1 | ✅ |
| Verde `#014e2a` sobre amarelo `#d9ae21` | 4,7:1 | ✅ texto sobre alertas amarelos |
| `#efefef` sobre azul `#025ecc` | 5,3:1 | ✅ |
| Lima sobre azul `#0167f7` | 3,4:1 | ⚠️ **só texto grande** (como no título da p.3) |
| `#efefef` sobre azul `#0167f7` | 4,3:1 | ⚠️ só texto grande; prefira branco puro |
| `#efefef` sobre vermelho `#db3016` | 4,1:1 | ⚠️ só texto grande (a p.4 usa título grande) |
| Azul `#0167f7` sobre `#efefef` | 4,3:1 | ⚠️ não use para texto pequeno de link; escureça ou sublinhe |
| Cinza `#b2b2b2` sobre `#efefef` | 1,8:1 | ❌ **só decorativo** — nunca para texto informativo |
| Amarelo sobre branco / `#efefef` | 2,1 / 1,8:1 | ❌ nunca texto amarelo sobre claro |
| Lima sobre branco / `#efefef` | 1,4 / 1,2:1 | ❌ lima só sobre fundo escuro |

Consequência prática: **o logotipo multicolor** (letras cinza `#b2b2b2` sobre `#efefef`, 1,8:1) é fiel ao guia, mas tem pouco contraste. Em cabeçalhos e telas funcionais, use a versão **verde** (`pivma-logo-green.svg`, derivada) e reserve a multicolor para apresentações e materiais institucionais.

---

## 4. Tipografia [guia, p.2]

| Função | Família | Peso |
|---|---|---|
| **Títulos** | **Barlow** | SemiBold (600) |
| **Corpo, parágrafos, web** | **Lexend** | Light 300 · Regular 400 · Medium 500 · SemiBold 600 · Bold 700 · ExtraBold 800 |

O guia mostra a cor **verde escuro** sobre `#efefef` nos espécimes. Pelo que está embutido no PDF: parágrafos usam **Lexend Medium** (p.3), rótulos e códigos hex usam **Lexend Light** (p.5), a régua lateral combina **Lexend Bold** (nome) e **Lexend Light** (“guia de marca”).

Ambas são **Google Fonts sob licença SIL OFL 1.1** — livres para uso comercial e embutimento. Os `.woff2` (latin + latin-ext, cobre todos os acentos do português) estão em `fonts/`; para usar:

```html
<link rel="stylesheet" href="fonts/fonts.css">
<link rel="stylesheet" href="tokens/tokens.css">
```

### Escala sugerida [derivado]

| Estilo | Fonte | Tamanho / linha | Peso |
|---|---|---|---|
| Display | Barlow | 56 / 1,1 | 600 |
| H1 | Barlow | 40 / 1,1 | 600 |
| H2 | Barlow | 32 / 1,15 | 600 |
| H3 | Barlow | 24 / 1,3 | 600 |
| H4 | Barlow | 20 / 1,3 | 600 |
| Corpo | Lexend | 16 / 1,55 | 400 (Medium 500 para destaque) |
| Corpo pequeno | Lexend | 14 / 1,5 | 400 |
| Rótulo / legenda | Lexend | 12 / 1,4 | 300–500 |
| Botão | Lexend | 14–16 / 1 | 500–600 |
| Dado / código | Lexend | 14 | 300–500 |

Regras: títulos sempre Barlow SemiBold; nunca use Barlow no corpo. Lexend é larga e de leitura fácil — não passe de ~75 caracteres por linha.

---

## 5. Logotipo

Wordmark **pi\*VMA**: letras de traço arredondado e geometria modular. Detalhes de identidade:

- a **estrela de brilho** substitui o asterisco do nome;
- o **"A"** é um arco aberto (como uma porta / ponte) com um **ponto** na base — no logotipo multicolor o ponto é azul;
- o **"V"** é vermelho na versão multicolor.

### 5.1 Versões

| Arquivo | Origem | Quando usar |
|---|---|---|
| `pivma-logo-multicolor.svg` | [guia, p.7] — P I ★ M em `#b2b2b2`, V `#db3016`, A `#014e2a`, ponto `#0167f7` | Material institucional sobre `#efefef`/claro |
| `pivma-logo-gray.svg` | [guia, p.6] — tudo `#b2b2b2` | Uso monocromático / marca d'água / impressão em 1 cor |
| `pivma-logo-lime.svg` | [guia, p.1 e 3] — tudo `#a3ed40` | Sobre verde escuro `#014e2a` ou azul `#0167f7` |
| `pivma-logo-lime-institucional.svg` | [guia, p.1] — lima + BraCVAM + Fiocruz | Capas, rodapés institucionais, telas de abertura |
| `pivma-logo-green.svg` | [derivado] — tudo `#014e2a` | **Cabeçalhos e telas funcionais** sobre claro |
| `pivma-logo-paper.svg` | [derivado] — tudo `#efefef` | Sobre vermelho, azul ou verde quando lima não couber |

PNG em 256, 512 e 1024 px de largura em `assets/logo/png/` (fundo transparente).

### 5.2 Regras de uso [derivado — o guia não as define]

- **Área de respeito**: mantenha livre, em todos os lados, ao menos **metade da altura do logotipo** (a altura das letras).
- **Tamanho mínimo**: 96 px de largura em tela (wordmark); abaixo disso, use só o símbolo "A" ou o ícone de app.
- **Não**: redistorcer, girar, trocar as cores das letras, aplicar sombras/contornos, colocar sobre fotos sem escurecer, usar a versão lima em fundo claro, usar a multicolor sobre fundos coloridos.
- Logotipos de **BraCVAM e Fiocruz** em `assets/partners/` foram extraídos da p.1 em lima. Para uso fora do contexto do guia, **peça os arquivos oficiais** às instituições e siga os manuais próprios delas.

---

## 6. Símbolos e ícones [guia, p.4]

A página "Elementos" define quatro elementos gráficos, em `assets/symbols/svg/` (cada um em lima, verde, papel, cinza, azul, vermelho e amarelo):

| Elemento | Uso |
|---|---|
| **"A"** (arco + ponto) | Avatar, favicon, ícone de app, loading, marca d'água |
| **Estrela** (brilho de 4 pontas) | Destaque, "novo", detalhe decorativo, itens inteligentes/IA |
| **Check** (círculo com ✓) | Aprovado, validado, sucesso |
| **X** (círculo com ×) | Reprovado, erro, remover |

Para herdar a cor do texto (`color`), use as versões de `symbols/svg/currentcolor/` **inline** no HTML — via `<img>` o `currentColor` não funciona:

```html
<span style="color: var(--color-danger)">
  <!-- conteúdo de assets/symbols/svg/currentcolor/pivma-x.svg inline -->
</span>
```

Tamanhos: o conjunto do guia é pensado para ~24 px em diante; abaixo disso o traço do check/X fica fino. Para ícones utilitários pequenos (setas, menu, busca etc.) o guia **não define** um conjunto — adote uma biblioteca de traço arredondado de ~2 px (por exemplo Lucide) para harmonizar com a geometria da marca.

---

## 7. Ícone de app e favicon

- **Do guia (p.6)**: quatro versões em cinza (`#b2b2b2`, `#9d9d9c`, `#878787`, `#706f6f`), quadrado de cantos arredondados com o "A" e a estrela em `#efefef` → `app-icon-gray-1…4`.
- **Derivados** com a paleta: verde/lima (padrão), azul/lima, lima/verde → `app-icon-green|blue|lime`.
- **Favicon e PWA** (derivados do ícone verde, em `assets/favicon/`): `favicon.ico` (16/32/48), `favicon.svg`, `apple-touch-icon.png` (180), `icon-192.png`, `icon-512.png`, `icon-512-maskable.png` e `site.webmanifest`.

```html
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
<meta name="theme-color" content="#014e2a">
```

Raio do ícone arredondado: ≈ 22 % do lado.

---

## 8. Formas e fundos decorativos [guia, p.3 e p.7]

O guia usa grandes formas geométricas derivadas do arco do "A" (bandas arredondadas e círculos) como fundo, **sempre em tom sobre tom**:

- `shape-blue-bg.svg` — fundo `#0167f7` com forma `#025ecc` (p.3).
- `shape-blue-only.svg` — só a forma, para reposicionar.
- `shape-watermark-gray.svg` — forma da p.7 com a cor do guia (`#dbdbdb` a 71 % de opacidade, sobre `#efefef`); `shape-watermark.svg` é a mesma forma com `currentColor`, para recolorir inline.

Use-as em telas de abertura, login, vazios (empty states) e capas. Não sobreponha conteúdo denso sobre elas e mantenha-as cortadas pela borda, como no guia.

---

## 9. Layout e componentes

> O guia é um documento de marca, não de interface. Esta seção **traduz** o que ele mostra em padrões de UI. Tudo aqui é **[derivado]** salvo onde indicado.

### Princípios visuais (do que o guia mostra)

1. **Fundos de cor chapada e saturada** (verde, azul, vermelho) alternando com o cinza claro — contraste forte e poucas cores por tela.
2. **Cantos arredondados em tudo**: swatches e régua lateral ~8 px, etiquetas ~4 px [guia, p.2 e 5]; combine com os cantos arredondados do logotipo.
3. **Uma cor de destaque por vez**: lima sobre verde; verde sobre claro. Não misture lima, amarelo e azul no mesmo componente.
4. **Muito espaço em branco**; composição centrada e calma.
5. **Régua lateral** (coluna vertical arredondada com ícone no topo, título girado e numeração no pé): é um motivo **editorial do documento**, não precisa virar componente da aplicação — mas serve de inspiração para uma barra de navegação lateral estreita.

### Tokens de forma

| Token | Valor |
|---|---|
| `--radius-xs` | 4 px — etiquetas/tags |
| `--radius-sm` | 8 px — inputs, cartões pequenos |
| `--radius-md` | 12 px — cartões, modais |
| `--radius-lg` | 20 px — painéis de destaque |
| `--radius-pill` | 999 px — botões em pílula, chips |
| espaçamento | 4 · 8 · 12 · 16 · 24 · 32 · 48 · 64 |

### Botões

| Tipo | Fundo | Texto | Observação |
|---|---|---|---|
| Primário | `#014e2a` | `#a3ed40` (6,9:1) | Hover: `#013f22` |
| Destaque / ação | `#0167f7` | `#ffffff` (4,9:1) | Foco: anel `rgb(1 103 247 / .35)` 3 px |
| Secundário | transparente, borda `#014e2a` 1,5 px | `#014e2a` | |
| Perigo | `#db3016` | `#ffffff` (4,7:1) | |
| Desabilitado | `#b2b2b2` | `#706f6f` | Sem hover |

Altura 40–44 px, raio `--radius-sm` ou pílula, Lexend Medium 14–16 px.

### Status e alertas

| Estado | Ícone | Cores |
|---|---|---|
| Validado / aprovado | Check | texto/ícone `#014e2a` sobre `#e3f2d3`* |
| Em análise | Estrela ou ponto | texto `#014e2a` sobre amarelo `#d9ae21` |
| Reprovado / erro | X | texto `#ffffff` sobre `#db3016` |
| Informação | — | texto `#ffffff` sobre `#0167f7` |

\* tint claro derivado de lima — confira contraste ao aplicar (verde `#014e2a` sobre ele ≈ 8:1).

### Formulários

Campo: fundo branco, borda `#c9d3cd` 1 px, raio 8 px, texto `#014e2a`, rótulo Lexend 12–14 px. Foco: borda `#0167f7` + anel de foco. Erro: borda `#db3016` + ícone X + mensagem de texto (nunca só a cor).

### Dados (tabelas e gráficos)

Para gráficos, use a paleta da marca na ordem: verde `#014e2a`, azul `#0167f7`, amarelo `#d9ae21`, vermelho `#db3016`, lima `#a3ed40` (lima apenas sobre fundo escuro). Para séries com sentido (aprovado/reprovado), use verde/vermelho **com rótulos ou formas diferentes** — verde e vermelho são ambíguos para daltônicos.

---

## 10. Tom de voz [derivado, a partir do texto do guia]

Português do Brasil, direto e técnico sem ser frio: *submeter*, *validar*, *rastrear*, *método alternativo*. Fale em termos de confiabilidade e transparência: mostre **o que mudou, quem, quando** (rastreabilidade). Evite jargão de marketing e exclamações; mensagens de erro dizem o que aconteceu e o que fazer.

---

## 11. Checklist de implementação

- [ ] Importar `fonts/fonts.css` e `tokens/tokens.css`
- [ ] Títulos em Barlow 600; corpo em Lexend
- [ ] Fundo base `#efefef`; texto principal `#014e2a`
- [ ] Logotipo verde no cabeçalho; multicolor/lima só em contextos institucionais
- [ ] Favicon + manifest + `theme-color` `#014e2a`
- [ ] Status sempre com ícone (check/X) + texto, não só cor
- [ ] Lima só sobre verde escuro; amarelo nunca texto sobre claro
- [ ] Foco visível em todos os controles (anel azul)
- [ ] Confirmar com a equipe de marca: **qual azul é oficial** (`#0167f7` × `#025ecc`) e os arquivos oficiais de BraCVAM/Fiocruz

---

## 12. O que o guia *não* define (lacunas)

Para não parecer que algo é oficial quando não é: o PDF **não traz** — área de respeito, tamanho mínimo, usos incorretos do logotipo, escala tipográfica, tamanhos de fonte, iconografia utilitária, componentes de interface, estados, modo escuro, grade/espaçamento, nem regras para impressão. Tudo isso acima é proposta marcada como **[derivado]**.

---

*Gerado a partir de `Guia_de_estilos.pdf`. Vetores extraídos diretamente do PDF; fontes via Fontsource (SIL OFL 1.1).*
