import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

const rootDirectory = new URL("../src/", import.meta.url);
const allowedExtensions = new Set([".js", ".vue", ".css"]);
const issues = [];

async function collectFiles(directoryUrl) {
  const entries = await readdir(directoryUrl, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    const nextUrl = new URL(`${entry.name}${entry.isDirectory() ? "/" : ""}`, directoryUrl);

    if (entry.isDirectory()) {
      files.push(...(await collectFiles(nextUrl)));
      continue;
    }

    if (allowedExtensions.has(path.extname(entry.name))) {
      files.push(nextUrl);
    }
  }

  return files;
}

function addIssue(filePath, message) {
  issues.push(`${filePath}: ${message}`);
}

function checkContent(filePath, content) {
  const lines = content.split("\n");

  lines.forEach((line, index) => {
    if (line.includes("\t")) {
      addIssue(filePath, `line ${index + 1} contains a tab character`);
    }

    if (/\s+$/.test(line)) {
      addIssue(filePath, `line ${index + 1} has trailing whitespace`);
    }
  });

  if (content.includes("<<<<<<<") || content.includes(">>>>>>>") || content.includes("=======")) {
    addIssue(filePath, "contains unresolved merge markers");
  }
}

const files = await collectFiles(rootDirectory);

for (const fileUrl of files) {
  const content = await readFile(fileUrl, "utf8");
  checkContent(fileUrl.pathname, content);
}

if (issues.length) {
  console.error(issues.join("\n"));
  process.exitCode = 1;
} else {
  console.log(`Lint passed for ${files.length} frontend source files.`);
}
