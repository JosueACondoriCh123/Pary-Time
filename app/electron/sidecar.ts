// Lanza y vigila el núcleo Python. Protocolo en contracts/README.md.
import { spawn, type ChildProcess } from "node:child_process";
import { EventEmitter } from "node:events";
import { createInterface } from "node:readline";
import type { SidecarState } from "../src/bridge";
import { appendTail, parseReadyLine, restartDelay, type CoreCommand } from "./sidecar-logic";

const READY_TIMEOUT_MS = 20_000;

export class Sidecar extends EventEmitter {
  state: SidecarState = { phase: "starting" };
  private child: ChildProcess | null = null;
  private crashes: number[] = [];
  private stderrTail = "";
  private stopping = false;
  private retryTimer: NodeJS.Timeout | null = null;

  constructor(
    private readonly command: () => CoreCommand,
    private readonly token: string,
  ) {
    super();
  }

  start(): void {
    this.stopping = false;
    this.clearRetry();
    this.stderrTail = "";
    this.set({ phase: "starting" });

    let cmd: CoreCommand;
    try {
      cmd = this.command();
    } catch (err) {
      this.set({ phase: "failed", stderr: String((err as Error).message) });
      return;
    }

    const child = spawn(cmd.command, cmd.args, {
      cwd: cmd.cwd,
      env: { ...process.env, NDE1_TOKEN: this.token, PYTHONUNBUFFERED: "1", PYTHONIOENCODING: "utf-8" },
      windowsHide: true,
      stdio: ["ignore", "pipe", "pipe"],
    });
    this.child = child;

    const readyTimer = setTimeout(() => {
      this.stderrTail = appendTail(this.stderrTail, "\n[app] el núcleo no respondió en 20 s\n");
      child.kill();
    }, READY_TIMEOUT_MS);

    createInterface({ input: child.stdout! }).on("line", (line) => {
      const info = parseReadyLine(line);
      if (info && this.child === child) {
        clearTimeout(readyTimer);
        this.set({ phase: "ready", baseUrl: `http://127.0.0.1:${info.port}`, version: info.version });
      }
    });
    child.stderr!.setEncoding("utf8");
    child.stderr!.on("data", (chunk: string) => {
      this.stderrTail = appendTail(this.stderrTail, chunk);
    });

    const onGone = (reason: string) => {
      clearTimeout(readyTimer);
      if (this.child !== child) return;
      this.child = null;
      if (this.stopping) return;
      this.stderrTail = appendTail(this.stderrTail, `\n[app] ${reason}\n`);
      this.scheduleRestart();
    };
    child.on("error", (err) => onGone(`no se pudo lanzar: ${err.message}`));
    child.on("exit", (code, signal) => onGone(`el núcleo terminó (código ${code ?? "-"}, señal ${signal ?? "-"})`));
  }

  /** Botón "reintentar" después de demasiadas caídas: empieza de cero. */
  retry(): void {
    this.crashes = [];
    this.kill();
    this.start();
  }

  stop(): void {
    this.stopping = true;
    this.clearRetry();
    this.kill();
  }

  private scheduleRestart(): void {
    const now = Date.now();
    this.crashes.push(now);
    const delay = restartDelay(this.crashes, now);
    if (delay === null) {
      this.set({ phase: "failed", stderr: this.stderrTail.trim() });
      return;
    }
    this.set({ phase: "restarting", retryInMs: delay, stderr: this.stderrTail.trim() });
    this.retryTimer = setTimeout(() => this.start(), delay);
  }

  private kill(): void {
    const child = this.child;
    this.child = null;
    if (child && child.exitCode === null) child.kill();
  }

  private clearRetry(): void {
    if (this.retryTimer) clearTimeout(this.retryTimer);
    this.retryTimer = null;
  }

  private set(state: SidecarState): void {
    this.state = state;
    this.emit("state", state);
  }
}
