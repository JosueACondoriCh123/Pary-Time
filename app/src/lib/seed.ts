// Verificación de la semilla en el renderer: sha256(bytes(seed_revealed)) == seed_commitment.
// Igual que core.contracts.seed_commitment: la semilla es hex y se hashean sus bytes, no el texto.

export function hexToBytes(hex: string): Uint8Array<ArrayBuffer> | null {
  if (hex.length % 2 !== 0 || !/^[0-9a-fA-F]*$/.test(hex)) return null;
  const out = new Uint8Array(hex.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  return out;
}

export async function sha256Hex(bytes: Uint8Array<ArrayBuffer>): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

/** true si la semilla revelada corresponde al compromiso preregistrado. */
export async function verifySeed(seedRevealed: string, commitment: string): Promise<boolean> {
  const bytes = hexToBytes(seedRevealed);
  if (!bytes || bytes.length === 0) return false;
  return (await sha256Hex(bytes)) === commitment.toLowerCase();
}
