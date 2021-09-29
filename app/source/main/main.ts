import { ChildProcess, spawn } from "child_process";
import { writeFileSync, existsSync, statSync } from "fs";
import {
    app,
    BrowserWindow,
    dialog,
    ipcMain,
    nativeTheme,
    shell,
} from "electron";
import ElectronStore from "electron-store";
import { join } from "path";
import { Dataset, State, Tree, InterfaceAction } from "../common/types";

let window: BrowserWindow | null = null;

const electronStore = new ElectronStore({
    schema: {
        theme: {
            type: "string",
            enum: ["System default", "Light", "Dark"],
        },
        directory: {
            type: "string",
        },
    },
});

{
    const directory = electronStore.get("directory", null) as string | null;
    if (!existsSync(directory!) || !statSync(directory!).isDirectory()) {
        electronStore.delete("directory");
    }
}

const createWindow = (): void => {
    window = new BrowserWindow({
        width: 800,
        height: 600,
        minHeight: 300,
        minWidth: 600,
        show: false,
        autoHideMenuBar: true,
        titleBarStyle: "hidden",
        trafficLightPosition: {
            x: 18,
            y: 18,
        },
        webPreferences: {
            preload: join(__dirname, "preload.js"),
        },
    });
    window.on("ready-to-show", () => window!.show());
    if (import.meta.env.DEV) {
        window.loadURL(import.meta.env.BASE_URL);
    } else {
        window.loadFile("renderer/index.html");
    }
};

app.on("ready", createWindow);

app.on("window-all-closed", () => {
    if (process.platform !== "darwin") {
        app.quit();
    }
});

app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        createWindow();
    }
});

let interfaceProcess: ChildProcess | null = null;

const state: State = {
    childrenCount: 0,
    nameToChild: {},
    fileCount: null,
    directory: electronStore.get("directory") as string | null,
    action: null,
    phase: null,
    details: null,
    datasets: [],
};

const writeConfiguration = () => {
    if (state.directory) {
        writeFileSync(
            join(state.directory, "undr.toml"),
            [
                'directory = "datasets"',
                "",
                ...state.datasets.map(dataset =>
                    [
                        "[[datasets]]",
                        `name = "${dataset.name}"`,
                        `url = "${dataset.url}"`,
                        `mode = "${dataset.mode}"`,
                        `server_type = "${dataset.server_type}"`,
                        "",
                    ].join("\n")
                ),
            ].join("\n")
        );
    }
};

const sendState = () => {
    if (window) {
        window!.webContents.send("state-update", state);
    }
};

const startInterfaceAction = (interfaceAction: InterfaceAction): void => {
    if (interfaceProcess != null) {
        interfaceProcess.removeAllListeners();
        interfaceProcess.stderr!.removeAllListeners();
        interfaceProcess.stdout!.removeAllListeners();
        interfaceProcess.kill("SIGINT");
    }
    interfaceProcess = spawn(
        import.meta.env.DEV
            ? import.meta.env.VITE_INTERFACE!
            : `${__dirname}/../interface/interface`,
        [
            join(state.directory!, "undr.toml"),
            interfaceAction.action,
            ...Object.entries(interfaceAction.options).map(
                ([option, value]) => `--${option}=${value}`
            ),
            ...Object.entries(interfaceAction.flags)
                .filter(([_, value]) => value === true)
                .map(([flag, _]) => `--${flag}`),
        ]
    );
    state.action = interfaceAction.action;
    state.details = null;
    sendState();
    interfaceProcess.on("close", () => {
        interfaceProcess = null;
        state.action = null;
        sendState();
    });
    interfaceProcess.stderr!.on("data", data => {
        console.error(data);
    });
    let length = 0n;
    let buffer: null | Buffer = null;
    const groupPath: string[] = [];
    let tree: Tree = state;
    tree.childrenCount = 0;
    tree.nameToChild = {};
    interfaceProcess.stdout!.on("data", (data: Buffer) => {
        if (buffer == null) {
            buffer = data;
        } else {
            buffer = Buffer.concat([buffer, data]);
        }
        for (;;) {
            if (length === 0n && buffer.length >= 8) {
                length = buffer.readBigUInt64LE();
                buffer = buffer.slice(8);
            }
            if (length === 0n || buffer.length < length) {
                break;
            }
            const message = JSON.parse(
                buffer.slice(0, Number(length)).toString()
            );
            switch (message.type) {
                case "init":
                    state.datasets = message.datasets;
                    break;
                case "group_begin":
                    if (message.group === "process_directory") {
                        state.details = message.directory;
                        if (!tree.hasOwnProperty(message.name)) {
                            tree.childrenCount = message.count;
                            tree.nameToChild[message.name] = {
                                childrenCount: 0,
                                nameToChild: {},
                                fileCount: 0,
                            };
                        }
                        groupPath.push(message.name);
                        tree = tree.nameToChild[message.name];
                    } else if (message.group === "phase") {
                        state.phase = message.name;
                    }
                    break;
                case "group_end":
                    if (message.group === "process_directory") {
                        state.details = null;
                        tree.fileCount = message.files;
                        groupPath.pop();
                        tree = state;
                        for (const name of groupPath) {
                            tree = tree.nameToChild[name];
                        }
                    } else if (message.group === "phase") {
                        state.phase = null;
                    }
                    break;
                case "progress":
                    break;
                case "error":
                    console.error(message);
                    break;
                default:
                    throw new Error(`unknown message type "${message.type}"`);
            }
            if (window) {
                window!.webContents.send("state-update", state);
            }
            if (buffer.length === Number(length)) {
                length = 0n;
                buffer = null;
                break;
            }
            buffer = buffer.slice(Number(length));
            length = 0n;
        }
    });
};

if (state.directory != null) {
    startInterfaceAction({
        action: "init",
        options: {},
        flags: {},
    });
}

ipcMain.on("interface-run", (_, interfaceAction: InterfaceAction) =>
    startInterfaceAction(interfaceAction)
);

ipcMain.on("interface-cancel", () => {
    if (interfaceProcess != null) {
        interfaceProcess.kill("SIGINT");
        interfaceProcess = null;
    }
});

ipcMain.on("theme-load", event => {
    event.returnValue = electronStore.get("theme", null);
});

ipcMain.on("theme-store", (_, theme: string) => {
    electronStore.set("theme", theme);
});

ipcMain.on("theme-should-use-dark-colors", event => {
    event.returnValue = nativeTheme.shouldUseDarkColors;
});

nativeTheme.on("updated", () => {
    if (window) {
        window.webContents.send(
            "theme-should-use-dark-colors-update",
            nativeTheme.shouldUseDarkColors
        );
    }
});

ipcMain.on("directory-choose", () => {
    dialog
        .showOpenDialog(window!, {
            properties: ["openDirectory", "createDirectory", "promptToCreate"],
        })
        .then(result => {
            if (
                result.canceled ||
                !result.filePaths ||
                result.filePaths.length === 0
            ) {
                return;
            }
            electronStore.set("directory", result.filePaths[0]);
            state.directory = result.filePaths[0];
            state.datasets = [];
            window!.webContents.send("state-update", state);
            startInterfaceAction({
                action: "init",
                options: {},
                flags: {},
            });
        });
});

ipcMain.on("directory-show", () => {
    const directory = electronStore.get("directory", null) as string | null;
    if (directory) {
        shell.openPath(directory);
    }
});

ipcMain.on("datasets-add-or-update", (_, dataset: Dataset) => {
    if (state.directory) {
        let found = false;
        for (const otherDataset of state.datasets) {
            if (otherDataset.name === dataset.name) {
                found = true;
                otherDataset.url = dataset.url;
                otherDataset.mode = dataset.mode;
                otherDataset.server_type = dataset.server_type;
            }
        }
        if (!found) {
            state.datasets.push(dataset);
            state.datasets.sort((a: Dataset, b: Dataset) =>
                a.name.localeCompare(b.name)
            );
        }
        writeConfiguration();
        sendState();
    }
});

ipcMain.on("datasets-remove", () => {
    if (state.directory) {
        state.datasets = state.datasets.filter(
            otherDataset => otherDataset.name !== DataTransferItem.name
        );
        writeConfiguration();
        sendState();
    }
});

ipcMain.on("bibtex-export", () => {
    if (state.directory) {
        dialog
            .showSaveDialog(window!, {
                defaultPath: join(state.directory, "datasets.bib"),
                filters: [{ name: "BibTeX files", extensions: ["bib"] }],
            })
            .then(result => {
                if (result.canceled) {
                    return;
                }
                if (state.directory) {
                    startInterfaceAction({
                        action: "bibtex",
                        options: { output: result.filePath! },
                        flags: {},
                    });
                }
            });
    }
});

ipcMain.on("state-load", event => {
    event.returnValue = state;
});
