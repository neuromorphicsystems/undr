import * as esbuild from "esbuild";
import * as fs from "fs";
import mustache from "mustache";
import * as path from "path";
import * as process from "node:process";
import * as svgr from "@svgr/core";

fs.mkdirSync("build", { recursive: true });

(async () => {
    const context = await esbuild.context({
        entryPoints: [path.join("source", "app.tsx")],
        bundle: true,
        define: {
            UNDR_DEFAULT_TOML: JSON.stringify(
                fs
                    .readFileSync(
                        path.join(path.resolve(".."), "undr_default.toml")
                    )
                    .toString()
            ),
        },
        jsx: "automatic",
        jsxDev: process.env.MODE === "development",
        sourcemap: process.env.MODE === "development",
        target: ["es2021"],
        write: false,
        minify: process.env.MODE === "production",
        plugins: [
            {
                name: "svgr",
                setup(build) {
                    build.onLoad({ filter: /\.svg$/ }, async args => ({
                        contents: await svgr.transform(
                            await fs.promises.readFile(args.path),
                            { typescript: true, dimensions: false },
                            { filePath: args.path }
                        ),
                        loader: "tsx",
                    }));
                },
            },
            {
                name: "bundle",
                setup(build) {
                    build.onEnd(result => {
                        if (result.errors.length === 0) {
                            fs.writeFileSync(
                                path.join("build", "index.html"),
                                mustache.render(
                                    fs
                                        .readFileSync(
                                            path.join(
                                                "source",
                                                "index.mustache"
                                            )
                                        )
                                        .toString(),
                                    {
                                        title: "UNDR",
                                        script: result.outputFiles[0].text,
                                    }
                                )
                            );
                            if (process.argv.includes("--watch")) {
                                console.log(
                                    `\x1b[32m✓\x1b[0m ${new Date().toLocaleString()}`
                                );
                            }
                        }
                    });
                },
            },
        ],
    });
    if (process.argv.includes("--watch")) {
        await context.watch();
    } else {
        await context.rebuild();
        await context.dispose();
    }
})();
