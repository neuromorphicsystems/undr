const child_process = require("child_process");
const electron = require("electron");
const electronBuilder = require("electron-builder");
const fs = require("fs/promises");
const path = require("path");
const vite = require("vite");

const commands = new Set(["release", "watch", "generate-js"]);
if (process.argv.length !== 3 || !commands.has(process.argv[2])) {
    console.error(
        `Syntax: node scripts.js [command], where command is in {${Array.from(
            commands.values()
        ).join(", ")}}`
    );
    process.exit(1);
}

const bundle = async () => {
    for (const root of [
        path.join(__dirname, "source", "main"),
        path.join(__dirname, "source", "renderer"),
    ]) {
        console.group(`build ${root}`);
        await vite.build({ mode: process.env.MODE, root });
        console.groupEnd();
    }
};

class Interface {
    constructor({ platform, arch, directory, executable }) {
        this.platform = platform;
        this.arch = arch;
        this.directory = directory;
        this.executable = executable;
    }

    resources() {
        return [
            {
                from: this.directory,
                to: "interface",
                filter: `!${this.executable}`,
            },
            {
                from: path.join(this.directory, this.executable),
                to: `interface/interface${
                    this.platform === "win" ? ".exe" : ""
                }`,
            },
        ];
    }

    matches(platform, arch) {
        let platformAlias = platform;
        switch (platform) {
            case "darwin":
                platformAlias = "mac";
                break;
            case "win32":
                platformAlias = "win";
                break;
            default:
                break;
        }
        return platformAlias === this.platform && arch === this.arch;
    }
}

const interfaces = [
    new Interface({
        platform: "linux",
        arch: "x64",
        directory: path.join(
            __dirname,
            "interface",
            "build",
            "interface-cp38-manylinux"
        ),
        executable: "interface-cp38-manylinux",
    }),
    new Interface({
        platform: "mac",
        arch: "x64",
        directory: path.join(
            __dirname,
            "interface",
            "build",
            "interface-cp39-macosx"
        ),
        executable: "interface-cp39-macosx",
    }),
    new Interface({
        platform: "win",
        arch: "x64",
        directory: path.join(
            __dirname,
            "interface",
            "build",
            "interface-cp39-win"
        ),
        executable: "interface-cp39-win.exe",
    }),
    new Interface({
        platform: "win",
        arch: "ia32",
        directory: path.join(
            __dirname,
            "interface",
            "build",
            "interface-cp39-win32"
        ),
        executable: "interface-cp39-win32.exe",
    }),
];

(async () => {
    try {
        switch (process.argv[2]) {
            case "release":
                await fs.rm(path.join(__dirname, "build"), {
                    recursive: true,
                    force: true,
                });
                await bundle();
                for (const interface of interfaces) {
                    console.log(
                        `electron-builder ${interface.platform} ${interface.arch}`
                    );
                    await electronBuilder.build({
                        [interface.platform]: ["zip"],
                        [interface.arch]: true,
                        project: __dirname,
                        config: {
                            extraResources: interface.resources(),
                            extraMetadata: {
                                main: "main/main.js",
                            },
                        },
                    });
                }
                break;
            case "watch":
                const rendererServer = await vite.createServer({
                    root: path.join(__dirname, "source", "renderer"),
                });
                await rendererServer.listen();
                const logger = vite.createLogger("warn", {
                    prefix: "[main]",
                });
                let electronProcess = null;
                if (process.env.VITE_INTERFACE === undefined) {
                    for (const interface of interfaces) {
                        if (interface.matches(process.platform, process.arch)) {
                            process.env.VITE_INTERFACE = path.join(
                                interface.directory,
                                interface.executable
                            );
                            break;
                        }
                    }
                }
                if (process.env.VITE_INTERFACE === undefined) {
                    throw new Error(
                        `unsupported platform and arch (${process.platform} ${process.arch})`
                    );
                }
                vite.build({
                    mode: process.env.MODE,
                    base: [
                        `http${
                            rendererServer.config.server.https ? "s" : ""
                        }://`,
                        rendererServer.config.server.host || "localhost",
                        `:${rendererServer.config.server.port}/`,
                    ].join(""),
                    root: path.join(__dirname, "source", "main"),
                    build: {
                        watch: {},
                    },
                    plugins: [
                        {
                            name: "reload-app-on-main-package-change",
                            writeBundle: () => {
                                if (electronProcess !== null) {
                                    electronProcess.kill("SIGINT");
                                    electronProcess = null;
                                }
                                electronProcess = child_process.spawn(
                                    String(electron),
                                    ["."]
                                );
                                electronProcess.stdout.on("data", data =>
                                    logger.warn(data.toString().trim(), {
                                        timestamp: true,
                                    })
                                );
                                electronProcess.stderr.on("data", data =>
                                    logger.error(data.toString().trim(), {
                                        timestamp: true,
                                    })
                                );
                            },
                        },
                    ],
                });
                break;
            case "generate-js":
                await fs.rm(path.join(__dirname, "build"), {
                    recursive: true,
                    force: true,
                });
                await bundle();
                break;
            default:
                throw new Error(`unexpected command "${process.argv[2]}"`);
        }
    } catch (error) {
        console.error(error);
        process.exit(1);
    }
})();
