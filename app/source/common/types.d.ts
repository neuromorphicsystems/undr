export interface Theme {
    content0: string;
    content1: string;
    content2: string;
    background0: string;
    background1: string;
    background2: string;
    backgroundSeparator: string;
    titleBarBackground: string;
    titleBarContent: string;
    controlBackground: string;
    controlForeground: string;
    controlBackgroundActive: string;
    controlForegroundActive: string;
    controlShadow: string;
    link: string;
    active: string;
    warning: string;
    error: string;
}

export interface InterfaceAction {
    action: string;
    options: Record<string, string>;
    flags: Record<string, boolean>;
}

export interface Dataset {
    name: string;
    url: string;
    mode: "remote" | "local" | "decompressed" | "disabled";
    server_type: "apache" | "nginx";
}

export interface Tree {
    childrenCount: number;
    nameToChild: { [key: string]: Tree };
    fileCount: number | null;
}

export interface State extends Tree {
    directory: string | null;
    action: string | null;
    phase: string | null;
    details: string | null;
    datasets: Dataset[];
}
