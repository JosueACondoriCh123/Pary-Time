// Empaqueta el proceso principal y el preload de Electron a CommonJS (el preload con sandbox exige CJS).
import { build } from "esbuild";

const common = { bundle: true, platform: "node", format: "cjs", target: "node22", external: ["electron"], logLevel: "info" };
await build({ ...common, entryPoints: ["electron/main.ts"], outfile: "dist-electron/main.cjs" });
await build({ ...common, entryPoints: ["electron/preload.ts"], outfile: "dist-electron/preload.cjs" });
