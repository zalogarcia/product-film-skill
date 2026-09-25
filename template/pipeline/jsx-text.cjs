#!/usr/bin/env node
// List visible text hard-coded in JSX: text between tags, and string
// literals placed directly as a tag's child. Used by check:claims, which
// requires every visible string to come from COPY in src/timeline.ts.
//
//   node pipeline/jsx-text.cjs src/scenes/Hook.tsx src/ui/Plant.tsx ...
//
// Prints JSON: [{ "file", "line", "text" }]. Parses with the TypeScript
// compiler the starter already depends on, so multi-line JSX is covered.
const fs = require("fs");
const ts = require("typescript");

const found = [];
for (const file of process.argv.slice(2)) {
  const src = ts.createSourceFile(file, fs.readFileSync(file, "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const add = (node, text) => {
    const t = text.replace(/\s+/g, " ").trim();
    if (/[A-Za-z]{2,}/.test(t)) {
      found.push({ file, line: src.getLineAndCharacterOfPosition(node.getStart()).line + 1, text: t });
    }
  };
  const visit = (node) => {
    if (ts.isJsxText(node)) add(node, node.text);
    if (ts.isJsxExpression(node) && node.expression && ts.isJsxElement(node.parent)) {
      const e = node.expression;
      if (ts.isStringLiteral(e) || ts.isNoSubstitutionTemplateLiteral(e)) add(node, e.text);
    }
    ts.forEachChild(node, visit);
  };
  visit(src);
}
process.stdout.write(JSON.stringify(found) + "\n");
