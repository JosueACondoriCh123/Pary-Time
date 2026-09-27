import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { appendTail, BACKOFF_MS, coreCommand, parseReadyLine, restartDelay } from "../electron/sidecar-logic";

describe("parseReadyLine", () => {
  it("lee la línea del contrato", () => {
    expect(parseReadyLine('NDE1_READY {"port": 51234, "version": "n-de-1@0.1.0", "contracts": "contracts@1"}')).toEqual({
      port: 51234,
      version: "n-de-1@0.1.0",
      contracts: "contracts@1",
    });
  });

  it("tolera espacios y el \\r de Windows", () => {
    expect(parseReadyLine('  NDE1_READY {"port": 80, "version": "v", "contracts": "c"}\r')?.port).toBe(80);
  });

  it.each([
    "INFO arrancando",
    "NDE1_READY",
    "NDE1_READY {roto",
    'NDE1_READY {"port": 0, "version": "v", "contracts": "c"}',
    'NDE1_READY {"port": 70000, "version": "v", "contracts": "c"}',
    'NDE1_READY {"port": "51234", "version": "v", "contracts": "c"}',
    'NDE1_READY {"port": 51234}',
    'xNDE1_READY {"port": 51234, "version": "v", "contracts": "c"}',
  ])("rechaza %s", (line) => {
    expect(parseReadyLine(line)).toBeNull();
  });
});

describe("restartDelay", () => {
  const t0 = 1_000_000_000;

  it("sigue la escalera 1, 2, 5, 10 s", () => {
    const crashes: number[] = [];
    const delays = [0, 1, 2, 3, 4].map((i) => {
      crashes.push(t0 + i * 1000);
      return restartDelay(crashes, t0 + i * 1000);
    });
    expect(delays).toEqual([1000, 2000, 5000, 10000, 10000]);
  });

  it("se rinde con más de 5 caídas en 5 min", () => {
    const crashes = [0, 1, 2, 3, 4, 5].map((i) => t0 + i * 30_000);
    expect(restartDelay(crashes, t0 + 150_000)).toBeNull();
  });

  it("olvida las caídas de hace más de 5 min", () => {
    const old = [0, 1, 2, 3, 4].map((i) => t0 + i * 1000);
    const now = t0 + 10 * 60_000;
    expect(restartDelay([...old, now], now)).toBe(BACKOFF_MS[0]);
  });
});

describe("coreCommand", () => {
  const base = { resourcesPath: "R", repoRoot: join("C:", "repo", "wt"), dataDir: "D" };

  it("empaquetado usa el exe del sidecar", () => {
    const c = coreCommand({ ...base, packaged: true, exists: () => false });
    expect(c.command).toBe(join("R", "nde1-core", "nde1-core.exe"));
    expect(c.args).toEqual(["--port", "0", "--data-dir", "D"]);
  });

  it("en desarrollo prefiere el venv del repo y cae al del repo padre", () => {
    const own = join(base.repoRoot, ".venv", "Scripts", "python.exe");
    const parent = join(base.repoRoot, "..", ".venv", "Scripts", "python.exe");
    expect(coreCommand({ ...base, packaged: false, exists: (p) => p === own }).command).toBe(own);
    const c = coreCommand({ ...base, packaged: false, exists: (p) => p === parent });
    expect(c.command).toBe(parent);
    expect(c.args).toEqual(["-m", "core", "--port", "0", "--data-dir", "D"]);
    expect(c.cwd).toBe(base.repoRoot);
  });

  it("sin Python explica qué probó", () => {
    expect(() => coreCommand({ ...base, packaged: false, exists: () => false })).toThrow(/NDE1_PYTHON/);
  });
});

it("appendTail guarda solo el final", () => {
  expect(appendTail("abc", "defg", 5)).toBe("cdefg");
});
