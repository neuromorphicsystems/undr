import { ChildProcess, spawn } from "child_process";
import { app, BrowserWindow, ipcMain } from "electron";
import ElectronStore from "electron-store";
import { Theme, UndrInterface } from "../common/types";

let window: BrowserWindow | null = null;

const store = new ElectronStore({
    schema: {
        theme: {
            type: "object",
            properties: {
                background: {
                    type: "string",
                    pattern: "^#[a-fA-F0-9]{6}$",
                },
            },
            required: ["background"],
        },
    },
});

console.log(app.getPath("userData"));

const createWindow = (): void => {
    window = new BrowserWindow({
        width: 800,
        height: 600,
        show: false,
        autoHideMenuBar: true,
        titleBarStyle: "hidden",
        trafficLightPosition: {
            x: 18,
            y: 18,
        }
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

ipcMain.on(
    "action",
    (event, { target, action, options, flags }: UndrInterface) => {
        if (interfaceProcess != null) {
            interfaceProcess.kill("SIGINT");
        }
        interfaceProcess = spawn(
            import.meta.env.DEV
                ? import.meta.env.VITE_INTERFACE!
                : `${__dirname}/../interface/interface`,
            [
                target,
                action,
                ...Object.entries(options).map(
                    ([option, value]) => `--${option}=${value}`
                ),
                ...Object.entries(flags)
                    .filter(([_, value]) => value === true)
                    .map(([flag, _]) => `--${flag}`),
            ]
        );
        interfaceProcess.on("close", () => {
            interfaceProcess = null;
        });
        interfaceProcess.stderr!.on("data", data => {
            console.error(data);
        });
        interfaceProcess.stdout!.on("data", data => {
            if (window) {
                window.webContents.send("interface", JSON.parse(data));
            }
        });
    }
);

ipcMain.on("cancel", () => {
    if (interfaceProcess != null) {
        interfaceProcess.kill("SIGINT");
        interfaceProcess = null;
    }
});
