import "styled-components";
import type { Theme } from "../common/types";

declare module "styled-components" {
    export interface DefaultTheme extends Theme {}
}

export const light: Theme = {
    content0: "#292929",
    content1: "#494949",
    content2: "#888888",
    background0: "#ffffff",
    background1: "#f5f5f5",
    background2: "#ebebeb",
    backgroundSeparator: "#cccccc",
    titleBarBackground: "#ffaf00",
    titleBarContent: "#ffffff",
    controlBackground: "#aaaaaa",
    controlForeground: "#f5f5f5",
    controlBackgroundActive: "#ffd780",
    controlForegroundActive: "#ffaf00",
    controlShadow: "#bbbbbb",
    link: "#ffaf00",
    active: "#ffc342",
    warning: "#e78420",
    error: "#db4733",
    errorActive: "#a83627",
};

export const dark: Theme = {
    content0: "#ffffff",
    content1: "#dddddd",
    content2: "#888888",
    background0: "#141414",
    background1: "#232323",
    background2: "#323232",
    backgroundSeparator: "#414141",
    titleBarBackground: "#414141",
    titleBarContent: "#ffffff",
    controlBackground: "#141414",
    controlForeground: "#888888",
    controlBackgroundActive: "#005cb2",
    controlForegroundActive: "#1e88e5",
    controlShadow: "#232323",
    link: "#005cb2",
    active: "#1e88e5",
    warning: "#e78420",
    error: "#db4733",
    errorActive: "#a83627",
};
