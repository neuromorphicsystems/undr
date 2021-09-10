import { join, dirname } from "path";
import { builtinModules } from "module";

export default {
    build: {
        emptyOutDir: true,
        lib: {
            entry: "main.ts",
            formats: ["cjs"],
        },
        minify: process.env.MODE === "development" ? false : "terser",
        outDir: join(dirname(dirname(__dirname)), "build", "main"),
        rollupOptions: {
            external: ["electron", ...builtinModules],
            output: {
                entryFileNames: "[name].js",
            },
        },
        target: "node14",
    },
};
