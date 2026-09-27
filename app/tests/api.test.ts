// El cliente contra un servidor HTTP real (node:http), sin mocks de fetch.
import { createServer, type IncomingMessage, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { ApiError, httpApi, TOKEN_HEADER } from "../src/api";
import health from "../../contracts/examples/Health.json";
import block from "../../contracts/examples/BlockView.hidden.json";

const TOKEN = "t".repeat(64);
const seen: { method: string; url: string; token?: string; body: string }[] = [];
let server: Server;
let baseUrl: string;

function read(req: IncomingMessage): Promise<string> {
  return new Promise((r) => {
    let body = "";
    req.on("data", (c) => (body += c));
    req.on("end", () => r(body));
  });
}

beforeAll(async () => {
  server = createServer(async (req, res) => {
    const token = req.headers[TOKEN_HEADER.toLowerCase()] as string | undefined;
    seen.push({ method: req.method!, url: req.url!, token, body: await read(req) });
    const send = (status: number, data: unknown) => {
      res.writeHead(status, { "Content-Type": "application/json" });
      res.end(JSON.stringify(data));
    };
    if (req.url === "/health") return send(200, health);
    if (token !== TOKEN) return send(401, { detail: "token local inválido" });
    if (req.url?.startsWith("/blocks?date=")) return send(200, [block]);
    if (req.url === "/blocks/blk_a1b2c3d4e5f6" && req.method === "PATCH") return send(409, { detail: "ya confirmado" });
    if (req.url === "/runtime/overlay") return send(501, { detail: "Frente B: todavía no implementado" });
    return send(404, { detail: "Not Found" });
  });
  await new Promise<void>((r) => server.listen(0, "127.0.0.1", r));
  baseUrl = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
});

afterAll(() => new Promise<void>((r) => server.close(() => r())));

describe("httpApi", () => {
  const api = () => httpApi(async () => ({ baseUrl, token: TOKEN }));

  it("/health va sin token", async () => {
    expect(await api().health()).toEqual(health);
    expect(seen.at(-1)!.token).toBeUndefined();
  });

  it("el resto lleva el token en el header, nunca en la URL", async () => {
    const list = await api().listBlocks("2026-09-29");
    expect(list[0].block_id).toBe("blk_a1b2c3d4e5f6");
    const last = seen.at(-1)!;
    expect(last.token).toBe(TOKEN);
    expect(last.url).toBe("/blocks?date=2026-09-29");
    expect(last.url).not.toContain(TOKEN);
  });

  it("409 con el detalle del núcleo", async () => {
    const err = await api().updateBlock("blk_a1b2c3d4e5f6", { planned_minutes: 30 }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(409);
    expect(err.human).toBe("No se puede ahora: ya confirmado");
    expect(JSON.parse(seen.at(-1)!.body)).toEqual({ planned_minutes: 30 });
  });

  it("501 dice que todavía no está", async () => {
    const err = await api().overlay().catch((e) => e);
    expect(err.status).toBe(501);
    expect(err.human).toBe("Todavía no disponible en esta versión.");
  });

  it("sin conexión o con el núcleo caído, un mensaje humano", async () => {
    const down = httpApi(async () => null);
    expect((await down.health().catch((e) => e)).status).toBe(0);
    const closed = httpApi(async () => ({ baseUrl: "http://127.0.0.1:1", token: TOKEN }));
    const err = await closed.listBlocks("2026-09-29").catch((e) => e);
    expect(err.status).toBe(0);
    expect(err.human).toMatch(/no responde/);
  });

  it("token equivocado: 401 humano", async () => {
    const bad = httpApi(async () => ({ baseUrl, token: "otro" }));
    const err = await bad.listBlocks("2026-09-29").catch((e) => e);
    expect(err.status).toBe(401);
    expect(err.human).toMatch(/Reiniciá la app/);
  });
});
