import { expect, test } from "vitest";
import {
  PACKS, addItems, appSuggestions, minutesBySite, monogram, normalizeProcess, normalizeSite, packCoverage,
  removeItem, siteLabel,
} from "../src/lib/sites";

test("normalizeSite: dominios, URLs y nombres sueltos dan el patrón de título", () => {
  expect(normalizeSite("youtube.com")).toEqual({ pattern: "youtube", domain: "youtube.com" });
  expect(normalizeSite("https://www.youtube.com/watch?v=abc")).toEqual({ pattern: "youtube", domain: "youtube.com" });
  expect(normalizeSite("  Netflix  ")).toEqual({ pattern: "netflix", domain: null });
  expect(normalizeSite("m.facebook.com")?.pattern).toBe("facebook");
  expect(normalizeSite("listado.mercadolibre.com.ar/celulares")).toEqual({
    pattern: "mercado libre", domain: "listado.mercadolibre.com.ar",
  });
  expect(normalizeSite("bbc.co.uk")?.pattern).toBe("bbc");
  expect(normalizeSite("web.whatsapp.com")?.pattern).toBe("whatsapp");
  expect(normalizeSite("primevideo.com")?.pattern).toBe("prime video");
});

test("normalizeSite: dominios de 1-2 letras se guardan enteros para no coincidir con todo", () => {
  expect(normalizeSite("https://x.com/home")?.pattern).toBe("x.com");
});

test("normalizeSite rechaza lo vacío o inútil", () => {
  expect(normalizeSite("")).toBeNull();
  expect(normalizeSite("   ")).toBeNull();
  expect(normalizeSite("a")).toBeNull();
  expect(normalizeSite("http://")).toBeNull();
});

test("siteLabel y monogram", () => {
  expect(siteLabel("youtube")).toBe("Youtube");
  expect(siteLabel("prime video")).toBe("Prime Video");
  expect(siteLabel("x.com")).toBe("x.com");
  const a = monogram("Discord.exe");
  expect(a.letter).toBe("D");
  expect(monogram("discord")).toEqual(a); // .exe y mayúsculas no cambian el ícono
  expect(a.hue).toBeGreaterThanOrEqual(0);
  expect(a.hue).toBeLessThan(360);
});

test("normalizeProcess agrega .exe y descarta rutas", () => {
  expect(normalizeProcess("discord")).toBe("discord.exe");
  expect(normalizeProcess("Steam.exe")).toBe("Steam.exe");
  expect(normalizeProcess("C:\\Games\\Steam\\steam.EXE")).toBe("steam.EXE");
  expect(normalizeProcess("  ")).toBeNull();
});

test("addItems / removeItem ignoran mayúsculas y no duplican", () => {
  expect(addItems(["YouTube"], ["youtube", "netflix"])).toEqual(["YouTube", "netflix"]);
  expect(removeItem(["YouTube", "netflix"], "youtube")).toEqual(["netflix"]);
});

test("packCoverage cuenta sitios y apps ya presentes", () => {
  const chat = PACKS.find((p) => p.id === "chat")!;
  expect(packCoverage(chat, ["WhatsApp"], ["discord.exe"])).toBe(2);
});

test("appSuggestions: las más usadas que no están en ninguna lista, sin las de trabajo", () => {
  const apps = [
    { process: "chrome.exe", minutes: 300, category: "other" },
    { process: "Spotify.exe", minutes: 120, category: "other" },
    { process: "WINWORD.EXE", minutes: 200, category: "work" },
    { process: "Discord.exe", minutes: 90, category: "distraction" },
    { process: "Figma.exe", minutes: 0, category: "other" },
    { process: "explorer.exe", minutes: 500, category: "other" },
  ];
  expect(appSuggestions(apps, ["Chrome.exe", "discord.exe"])).toEqual([{ process: "Spotify.exe", minutes: 120 }]);
});

test("minutesBySite suma por patrón sin distinguir mayúsculas", () => {
  const m = minutesBySite([{ site: "YouTube", minutes: 10 }, { site: "youtube", minutes: 5 }]);
  expect(m.get("youtube")).toBe(15);
});
