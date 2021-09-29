import { join, dirname } from "path";
import reactRefresh from "@vitejs/plugin-react-refresh";
import svgrPlugin from "./vite-plugin-react-svgr";

export default {
    base: "",
    build: {
        emptyOutDir: true,
        minify: process.env.MODE === "development" ? false : "terser",
        outDir: join(dirname(dirname(__dirname)), "build", "renderer"),
        rollupOptions: {
            output: {
                entryFileNames: "[name].js",
            },
        },
        target: "chrome91",
    },
    plugins: [svgrPlugin(), reactRefresh()],
};
