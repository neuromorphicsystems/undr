const esbuild = require("esbuild");
const fs = require("fs");
const mustache = require("mustache");
const prettier = require("prettier");

(async () => {
    await Promise.all([
        esbuild.build({
            entryPoints: ["app.ts"],
            bundle: true,
            outfile: "build/script.js",
        }),
        esbuild.build({
            entryPoints: ["style.css"],
            bundle: true,
            outfile: "build/style.css",
        }),
    ]);
    fs.writeFileSync(
        "build/index.html",
        prettier.format(
            mustache.render(fs.readFileSync("index.mustache").toString(), {
                title: "UNDR",
                script: fs.readFileSync("build/script.js").toString(),
                style: fs.readFileSync("build/style.css").toString(),
            }),
            {
                tabWidth: 4,
                arrowParens: "avoid",
                parser: "html",
            }
        )
    );
})();
