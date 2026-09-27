// Ícono de la bandeja dibujado en memoria: un anillo con un punto, sin archivos binarios en el repo.
import { nativeImage, type NativeImage } from "electron";

export function trayIcon(size = 32, rgb: [number, number, number] = [0x5b, 0x8d, 0xef]): NativeImage {
  const buf = Buffer.alloc(size * size * 4);
  const c = (size - 1) / 2;
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const d = Math.hypot(x - c, y - c) / (size / 2);
      if ((d > 0.72 && d < 0.95) || d < 0.34) {
        const i = (y * size + x) * 4; // BGRA
        buf[i] = rgb[2];
        buf[i + 1] = rgb[1];
        buf[i + 2] = rgb[0];
        buf[i + 3] = 255;
      }
    }
  }
  return nativeImage.createFromBitmap(buf, { width: size, height: size });
}
