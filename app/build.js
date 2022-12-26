import * as esbuild from "esbuild";
import * as fs from "fs";
import mustache from "mustache";
import * as path from "path";
import * as process from "node:process";
import * as svgr from "@svgr/core";

fs.mkdirSync("build", { recursive: true });

const resultToFile = result => {
    fs.writeFileSync(
        path.join("build", "index.html"),
        mustache.render(
            fs.readFileSync(path.join("source", "index.mustache")).toString(),
            {
                title: "UNDR",
                script: result.outputFiles[0].text,
            }
        )
    );
};

esbuild
    .build({
        entryPoints: [path.join("source", "app.tsx")],
        bundle: true,
        define: {
            S3_URL: JSON.stringify(process.env.npm_package_config_s3_url),
            S3_WEBSITE_URL: JSON.stringify(
                process.env.npm_package_config_s3_website_url
            ),
        },
        jsx: "automatic",
        jsxDev: process.env.MODE === "development",
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
        ],
    })
    .then(resultToFile);
