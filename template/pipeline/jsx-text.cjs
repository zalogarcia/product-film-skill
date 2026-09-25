#!/usr/bin/env node
// List visible text hard-coded in JSX, for check:claims, which requires
// every visible string to come from COPY in src/timeline.ts (read with T()).
//
//   node pipeline/jsx-text.cjs [folder]        default: src (every .tsx under it)
//
// Prints JSON: [{ "file", "line", "text" }]. Parses with the TypeScript
// compiler the starter already depends on. Reported:
//   - text between tags with any letter or digit (<div>40%</div>)
//   - string literals displayed from a child expression ({"Save 40%"},
//     {"...".toUpperCase()}, {isV ? "Tap" : "Click"}, `${n}x faster`);
//     arguments to calls (T("key"), s.padStart(2, "0")) are data, not text
//   - string props, unless the prop is technical (d, viewBox, fill, name ...)
//     or the value is a colour, a number or a single code-like token; props
//     named like text (label, title, caption ...) are always reported
const fs = require("fs");
const path = require("path");
const ts = require("typescript");

const TECH = new Set(
  (
    "key ref id name className style src href width height viewBox d points transform fill stroke strokeWidth " +
    "strokeLinecap strokeLinejoin strokeDasharray strokeDashoffset fillRule clipRule clipPath mask filter opacity " +
    "x y x1 x2 y1 y2 cx cy r rx ry dx dy offset stopColor stopOpacity gradientTransform gradientUnits " +
    "preserveAspectRatio xmlns type baseFrequency numOctaves seed stitchTiles values in in2 result mode operator " +
    "stdDeviation fontFamily textAnchor dominantBaseline vectorEffect markerEnd role dir lang target rel loading " +
    "decoding crossOrigin alt objectFit pauseWhenBuffering"
  ).split(" "),
);
const TEXTY = /^(label|title|text|caption|heading|headline|subtitle|subheading|body|message|placeholder|content|cta|tagline|description|children)$/i;
const hasContent = (s) => /[A-Za-z0-9]/.test(s);
const codeLike = (s) =>
  /^#[0-9a-f]{3,8}$/i.test(s) ||
  /^(rgba?|hsla?)\(/i.test(s) ||
  /^-?[\d.]+(px|%|em|rem|vh|vw|s|ms|deg)?$/.test(s) ||
  /^[\d\s.,-]+$/.test(s) ||
  /^[a-z]+([A-Z][a-z0-9]*)*$/.test(s);

const files = [];
const walk = (d) => {
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    const p = path.join(d, e.name);
    if (e.isDirectory() && e.name !== "node_modules") walk(p);
    else if (e.isFile() && e.name.endsWith(".tsx")) files.push(p);
  }
};
walk(process.argv[2] || "src");

const K = ts.SyntaxKind;
const COMPARE = new Set([
  K.EqualsEqualsEqualsToken, K.ExclamationEqualsEqualsToken, K.EqualsEqualsToken, K.ExclamationEqualsToken,
  K.LessThanToken, K.GreaterThanToken, K.LessThanEqualsToken, K.GreaterThanEqualsToken, K.InKeyword, K.InstanceOfKeyword,
]);

// the string literals an expression can DISPLAY: not call arguments, not nested JSX
const displayed = (expr, out) => {
  const visit = (n) => {
    if (ts.isJsxElement(n) || ts.isJsxSelfClosingElement(n) || ts.isJsxFragment(n)) return;
    if (ts.isCallExpression(n)) {
      // the receiver of "...".toUpperCase() is displayed; plain arguments are data,
      // but a callback's result (rows.map((r) => ...)) is displayed
      visit(n.expression);
      n.arguments.filter((a) => ts.isArrowFunction(a) || ts.isFunctionExpression(a)).forEach(visit);
      return;
    }
    if (ts.isArrowFunction(n) || ts.isFunctionExpression(n)) {
      visit(n.body);
      return;
    }
    // compared, used as a key or indexed with: never displayed
    if (ts.isBinaryExpression(n) && COMPARE.has(n.operatorToken.kind)) return;
    if (ts.isPropertyAssignment(n)) {
      visit(n.initializer);
      return;
    }
    if (ts.isElementAccessExpression(n)) {
      visit(n.expression);
      return;
    }
    if (ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n)) out.push(n.text);
    else if (ts.isTemplateExpression(n)) out.push(n.head.text + n.templateSpans.map((s) => "{}" + s.literal.text).join(""));
    else ts.forEachChild(n, visit);
  };
  visit(expr);
};

const found = [];
for (const file of files) {
  const src = ts.createSourceFile(file, fs.readFileSync(file, "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const add = (node, text) => {
    const t = text.replace(/\s+/g, " ").trim();
    found.push({ file, line: src.getLineAndCharacterOfPosition(node.getStart()).line + 1, text: t });
  };
  const visit = (node) => {
    if (ts.isJsxText(node) && hasContent(node.text)) add(node, node.text);
    if (ts.isJsxExpression(node) && node.expression && (ts.isJsxElement(node.parent) || ts.isJsxFragment(node.parent))) {
      const strs = [];
      displayed(node.expression, strs);
      for (const s of strs) if (hasContent(s)) add(node, s);
    }
    if (ts.isJsxAttribute(node) && node.initializer) {
      const name = node.name.getText();
      const texty = TEXTY.test(name);
      if (texty || !TECH.has(name)) {
        const strs = [];
        const init = node.initializer;
        if (ts.isStringLiteral(init)) strs.push(init.text);
        else if (ts.isJsxExpression(init) && init.expression) displayed(init.expression, strs);
        for (const s of strs) if (hasContent(s) && (texty || !codeLike(s))) add(node, `${name}="${s}"`);
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(src);
}
process.stdout.write(JSON.stringify(found) + "\n");
