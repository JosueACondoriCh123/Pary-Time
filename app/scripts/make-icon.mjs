// Genera build/icon.png (256x256) para electron-builder, con el mismo dibujo que el ícono de la bandeja.
// PNG escrito a mano con zlib: sin binarios en el repo ni dependencias extra.
import { mkdirSync, writeFileSync } from "node:fs";
import { deflateSync } from "node:zlib";

const SIZE = 256;
const [R, G, B] = [0x5b, 0x8d, 0xef];

const raw = Buffer.alloc((SIZE * 4 + 1) * SIZE);
const c = (SIZE - 1) / 2;
for (let y = 0; y < SIZE; y++) {
  raw[y * (SIZE * 4 + 1)] = 0; // filtro "none" por fila
  for (let x = 0; x < SIZE; x++) {
    const d = Math.hypot(x - c, y - c) / (SIZE / 2);
    const i = y * (SIZE * 4 + 1) + 1 + x * 4;
    const bg = d < 1;
    const mark = (d > 0.62 && d < 0.8) || d < 0.3;
    if (bg) {
      raw[i] = mark ? R : 0x10;
      raw[i + 1] = mark ? G : 0x13;
      raw[i + 2] = mark ? B : 0x18;
      raw[i + 3] = 255;
    }
  }
}

const CRC_TABLE = Array.from({ length: 256 }, (_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});
function crc32(buf) {
  let c = 0xffffffff;
  for (const b of buf) c = CRC_TABLE[(c ^ b) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}
function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body));
  return Buffer.concat([len, body, crc]);
}

const ihdr = Buffer.alloc(13);
ihdr.writeUInt32BE(SIZE, 0);
ihdr.writeUInt32BE(SIZE, 4);
ihdr[8] = 8; // bits por canal
ihdr[9] = 6; // RGBA
const png = Buffer.concat([
  Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
  chunk("IHDR", ihdr),
  chunk("IDAT", deflateSync(raw)),
  chunk("IEND", Buffer.alloc(0)),
]);

mkdirSync("build", { recursive: true });
writeFileSync("build/icon.png", png);
console.log("build/icon.png listo");
