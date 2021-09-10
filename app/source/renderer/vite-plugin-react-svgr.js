import svgr from "@svgr/core";
import { readFile } from "fs/promises";
import { transform } from "esbuild";

export default function svgrPlugin() {
    return {
        name: "vite-plugin-react-svgr",
        enforce: "pre",
        async load(id) {
            if (id.endsWith(".svg")) {
                return (await readFile(id)).toString();
            }
        },
        async transform(source, id) {
            if (id.endsWith(".svg")) {
                return {
                    code: (
                        await transform(
                            await svgr(source, {
                                plugins: [
                                    "@svgr/plugin-svgo",
                                    "@svgr/plugin-jsx",
                                ],
                                dimensions: false,
                                svgoConfig: {
                                    multipass: true,
                                }
                            }),
                            { loader: "jsx" }
                        )
                    ).code,
                    map: null,
                };
            }
        },
    };
}
