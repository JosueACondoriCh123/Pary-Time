// Genera src/contracts/index.ts desde ../contracts/schemas. Nunca se editan esos tipos a mano.
// Uso: npm run contracts            (escribe)
//      npm run contracts -- --check (exit 1 si el archivo no está al día)
import { readdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { compile } from "json-schema-to-typescript";

const here = dirname(fileURLToPath(import.meta.url));
const schemasDir = join(here, "..", "..", "contracts", "schemas");
const outFile = join(here, "..", "src", "contracts", "index.ts");

// Cada schema trae sus $defs. Los juntamos en uno solo para no duplicar enums como Arm.
const defs = {};
for (const file of readdirSync(schemasDir).filter((f) => f.endsWith(".schema.json")).sort()) {
  const { $defs = {}, $id: _id, $schema: _s, ...schema } = JSON.parse(readFileSync(join(schemasDir, file), "utf8"));
  for (const [name, def] of Object.entries($defs)) {
    if (defs[name] && JSON.stringify(defs[name]) !== JSON.stringify(def)) {
      throw new Error(`$defs.${name} difiere entre schemas (${file})`);
    }
    defs[name] = def;
  }
  defs[schema.title] = schema;
}
// Los `title` de cada campo harían un alias por campo (BlockId1, BlockId2...). Solo los modelos llevan nombre.
function stripFieldTitles(node) {
  if (Array.isArray(node)) return node.forEach(stripFieldTitles);
  if (!node || typeof node !== "object") return;
  for (const prop of Object.values(node.properties ?? {})) {
    delete prop.title;
    stripFieldTitles(prop);
  }
  for (const key of ["anyOf", "oneOf", "allOf", "items", "additionalProperties"]) stripFieldTitles(node[key]);
}
Object.values(defs).forEach(stripFieldTitles);
const names = Object.keys(defs).sort();
const root = {
  title: "Contracts",
  type: "object",
  properties: Object.fromEntries(names.map((n) => [n, { $ref: `#/$defs/${n}` }])),
  additionalProperties: false,
  $defs: Object.fromEntries(names.map((n) => [n, defs[n]])),
};

const banner = "// GENERADO por scripts/contracts.mjs desde contracts/schemas (contracts@1). No editar a mano.";
const ts = await compile(root, "Contracts", {
  bannerComment: banner,
  additionalProperties: false,
  unreachableDefinitions: true,
  style: { singleQuote: false, printWidth: 120 },
});

const current = existsSync(outFile) ? readFileSync(outFile, "utf8") : "";
if (process.argv.includes("--check")) {
  if (current !== ts) {
    console.error("src/contracts/index.ts está desactualizado: corré `npm run contracts`.");
    process.exit(1);
  }
  console.log("contratos al día");
} else {
  writeFileSync(outFile, ts);
  console.log(`escrito ${outFile} (${names.length} tipos)`);
}
