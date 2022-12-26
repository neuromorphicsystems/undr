import { DefaultTheme } from "styled-components";

declare module "styled-components" {
    export interface DefaultTheme {
        background0: string;
        background1: string;
        background2: string;
        content0: string;
        content1: string;
        content2: string;
        link: string;
        error: string;
        errorBackground: string;
    }
}

const light: DefaultTheme = {
    background0: "#FFFFFF",
    background1: "#F5F5F5",
    background2: "#E5E5E5",
    content0: "#292929",
    content1: "#696969",
    content2: "#898989",
    link: "#4285F4",
    error: "#BC3426",
    errorBackground: "#FCECEB",
};

const dark: DefaultTheme = {
    background0: "#191919",
    background1: "#292929",
    background2: "#393939",
    content0: "#DDDDDD",
    content1: "#BBBBBB",
    content2: "#777777",
    link: "#4285F4",
    error: "#E08065",
    errorBackground: "#4B3532",
};

export { light, dark };
