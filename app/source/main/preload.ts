import { contextBridge, ipcRenderer } from "electron";
import { Dataset, State, InterfaceAction } from "../common/types";

contextBridge.exposeInMainWorld("undr", {
    interface: {
        run: (interfaceAction: InterfaceAction): void =>
            ipcRenderer.send("interface-run", interfaceAction),
        cancel: (): void => ipcRenderer.send("interface-cancel"),
    },
    theme: {
        load: (): string | null => ipcRenderer.sendSync("theme-load"),
        store: (theme: string): void => {
            ipcRenderer.send("theme-store", theme);
        },
        shouldUseDarkColors: (): boolean =>
            ipcRenderer.sendSync("theme-should-use-dark-colors"),
        onShouldUseDarkColorsUpdate: (
            callback: (shouldUseDarkColors: boolean) => void
        ): void => {
            ipcRenderer.addListener(
                "theme-should-use-dark-colors-update",
                (_, shouldUseDarkColors: boolean) =>
                    callback(shouldUseDarkColors)
            );
        },
        offShouldUseDarkColorsUpdate: (
            callback: (shouldUseDarkColors: boolean) => void
        ): void => {
            ipcRenderer.removeListener(
                "theme-should-use-dark-colors-update",
                callback
            );
        },
    },
    timeout: {
        load: (): number => ipcRenderer.sendSync("timeout-load"),
        store: (timeout: number) => {
            ipcRenderer.send("timeout-store", timeout);
        },
    },
    workersCount: {
        load: (): number => ipcRenderer.sendSync("workers-count-load"),
        store: (workersCount: number) => {
            ipcRenderer.send("workers-count-store", workersCount);
        },
    },
    directory: {
        choose: (): void => ipcRenderer.send("directory-choose"),
        show: (): void => ipcRenderer.send("directory-show"),
    },
    state: {
        load: (): State => ipcRenderer.sendSync("state-load"),
        clearError: (): void => ipcRenderer.send("state-clear-error"),
        onUpdate: (callback: (state: State) => void): void => {
            ipcRenderer.on("state-update", (_, state: State) =>
                callback(state)
            );
        },
        offUpdate: (callback: (state: State) => void): void => {
            ipcRenderer.removeListener("state-update", callback);
        },
    },
    datasets: {
        addOrUpdate: (dataset: Dataset): void =>
            ipcRenderer.send("datasets-add-or-update", dataset),
        remove: (dataset: Dataset): void =>
            ipcRenderer.send("datasets-remove", dataset),
    },
    bibtex: {
        export: (): void => ipcRenderer.send("bibtex-export"),
    },
    platform: process.platform,
});
