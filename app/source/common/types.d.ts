export interface Theme {
    background: string;
    titleBar: string;
    button: string;
    buttonActive: string;
}

export interface UndrInterface {
    target: string;
    action: string;
    options: Record<string, string>;
    flags: Record<string, boolean>;
}
