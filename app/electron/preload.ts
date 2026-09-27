// Puente mínimo entre el renderer (sandbox, sin Node) y el proceso principal.
import { contextBridge, ipcRenderer } from "electron";
import type { Nde1Bridge, NavTarget, SidecarState } from "../src/bridge";

const bridge: Nde1Bridge = {
  sidecar: () => ipcRenderer.invoke("nde1:sidecar"),
  connection: () => ipcRenderer.invoke("nde1:connection"),
  onSidecar: (cb) => {
    const listener = (_e: unknown, state: SidecarState) => cb(state);
    ipcRenderer.on("nde1:sidecar", listener);
    return () => ipcRenderer.off("nde1:sidecar", listener);
  },
  retrySidecar: () => ipcRenderer.invoke("nde1:retry"),
  pickFile: () => ipcRenderer.invoke("nde1:pick-file"),
  saveFile: (opts) => ipcRenderer.invoke("nde1:save-file", opts),
  prefs: () => ipcRenderer.invoke("nde1:prefs"),
  setPrefs: (prefs) => ipcRenderer.invoke("nde1:set-prefs", prefs),
  onNavigate: (cb) => {
    const listener = (_e: unknown, to: NavTarget) => cb(to);
    ipcRenderer.on("nde1:navigate", listener);
    return () => ipcRenderer.off("nde1:navigate", listener);
  },
  setOverlayVisible: (visible) => ipcRenderer.send("nde1:overlay-visible", visible),
};

contextBridge.exposeInMainWorld("nde1", bridge);
