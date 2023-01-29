import * as React from "react";
import { DefaultTheme } from "styled-components";
import { invoke } from "@tauri-apps/api";
import * as constants from "./constants";

declare module "styled-components" {
    export interface DefaultTheme {
        background0: string;
        background1: string;
        background2: string;
        background3: string;
        content0: string;
        content1: string;
        content2: string;
        link: string;
        linkActive: string;
        error: string;
        errorActive: string;
        switchBackground: string;
        switchThumbShadow: string;
        disabled: string;
        remote: string;
        remoteActive: string;
        local: string;
        raw: string;
        complete: string;
    }
}

const light: DefaultTheme = {
    background0: "#FFFFFF",
    background1: "#EEEEEE",
    background2: "#DDDDDD",
    background3: "#CCCCCC",
    content0: "#292929",
    content1: "#696969",
    content2: "#898989",
    link: "#268BD2",
    linkActive: "#2772AC",
    error: "#DC322f",
    errorActive: "#B52D28",
    switchBackground: "#BBBBBB",
    switchThumbShadow: "#707070",
    disabled: "#898989",
    remote: "#268BD2",
    remoteActive: "#2772AC",
    local: "#2AA198",
    raw: "#6C71C4",
    complete: "#859900",
};

const dark: DefaultTheme = {
    background0: "#191919",
    background1: "#292929",
    background2: "#393939",
    background3: "#494949",
    content0: "#DDDDDD",
    content1: "#BBBBBB",
    content2: "#777777",
    link: "#268BD2",
    linkActive: "#2772AC",
    error: "#DC322f",
    errorActive: "#B52D28",
    switchBackground: "#888888",
    switchThumbShadow: "#191919",
    disabled: "#777777",
    remote: "#268BD2",
    remoteActive: "#2772AC",
    local: "#2AA198",
    raw: "#6C71C4",
    complete: "#859900",
};

const prefersDarkTheme = window.matchMedia("(prefers-color-scheme: dark)");

const resolveTheme = (
    selectedTheme: "auto" | "light" | "dark",
    prefersDark: boolean
) => {
    switch (selectedTheme) {
        case "auto":
            return prefersDark ? dark : light;
        case "light":
            return light;
        case "dark":
            return dark;
    }
};

export interface StoredPreferences {
    selectedTheme: "auto" | "light" | "dark";
    configurationPath: string | null;
    parallelFileDescriptors: [boolean, number];
    parallelIndexDownloads: [boolean, number];
    parallelDownloads: [boolean, number];
    parallelDecompressions: [boolean, number];
    keep: boolean;
    parallelDoiDownloads: [boolean, number];
    doiTimeout: [boolean, number];
}

export class Preferences {
    storedPreferences: StoredPreferences;
    theme: DefaultTheme;
    availableParallelism: number;
    loaded: boolean;

    constructor(
        storedPreferences: StoredPreferences,
        theme: DefaultTheme,
        availableParallelism: number,
        loaded: boolean
    ) {
        this.storedPreferences = storedPreferences;
        this.theme = theme;
        this.availableParallelism = availableParallelism;
        this.loaded = loaded;
    }

    parallelFileDescriptors() {
        return this.storedPreferences.parallelFileDescriptors[0]
            ? constants.defaultParallelFileDescriptors
            : this.storedPreferences.parallelFileDescriptors[1];
    }

    parallelIndexDownloads() {
        return this.storedPreferences.parallelIndexDownloads[0]
            ? constants.defaultParallelIndexDownloads
            : this.storedPreferences.parallelIndexDownloads[1];
    }

    parallelDownloads() {
        return this.storedPreferences.parallelDownloads[0]
            ? constants.defaultParallelDownloads
            : this.storedPreferences.parallelDownloads[1];
    }

    parallelDecompressions() {
        return this.storedPreferences.parallelDecompressions[0]
            ? this.availableParallelism
            : this.storedPreferences.parallelDecompressions[1];
    }

    parallelDoiDownloads() {
        return this.storedPreferences.parallelDoiDownloads[0]
            ? constants.defaultParallelDoiDownloads
            : this.storedPreferences.parallelDoiDownloads[1];
    }

    doiTimeout() {
        return this.storedPreferences.doiTimeout[0]
            ? constants.defaultTimeout
            : this.storedPreferences.doiTimeout[1];
    }

    static default() {
        return new Preferences(
            {
                selectedTheme: "auto",
                configurationPath: null,
                parallelFileDescriptors: [
                    true,
                    constants.defaultParallelFileDescriptors,
                ],
                parallelIndexDownloads: [
                    true,
                    constants.defaultParallelIndexDownloads,
                ],
                parallelDownloads: [true, constants.defaultParallelDownloads],
                parallelDecompressions: [true, 0], // 0 will be replaced with availableParallelism on first call to newWithRaw
                parallelDoiDownloads: [
                    true,
                    constants.defaultParallelDoiDownloads,
                ],
                keep: false,
                doiTimeout: [true, constants.defaultTimeout],
            },
            resolveTheme("auto", prefersDarkTheme.matches),
            1,
            false
        );
    }

    newWithRaw(
        rawPreferences: StoredPreferences,
        availableParallelism: number
    ) {
        const storedPreferences = { ...this.storedPreferences };
        if (
            typeof rawPreferences === "object" &&
            !Array.isArray(rawPreferences) &&
            rawPreferences !== null
        ) {
            if (
                rawPreferences.selectedTheme === "auto" ||
                rawPreferences.selectedTheme === "light" ||
                rawPreferences.selectedTheme === "dark"
            ) {
                storedPreferences.selectedTheme = rawPreferences.selectedTheme;
            }
            if (
                rawPreferences.configurationPath === null ||
                typeof rawPreferences.configurationPath === "string"
            ) {
                storedPreferences.configurationPath =
                    rawPreferences.configurationPath;
            }
            if (
                Array.isArray(rawPreferences.parallelFileDescriptors) &&
                rawPreferences.parallelFileDescriptors.length === 2 &&
                typeof rawPreferences.parallelFileDescriptors[0] ===
                    "boolean" &&
                typeof rawPreferences.parallelFileDescriptors[1] === "number" &&
                Math.round(rawPreferences.parallelFileDescriptors[1]) > 0
            ) {
                storedPreferences.parallelFileDescriptors = [
                    rawPreferences.parallelFileDescriptors[0],
                    Math.round(rawPreferences.parallelFileDescriptors[1]),
                ];
            }
            if (
                Array.isArray(rawPreferences.parallelIndexDownloads) &&
                rawPreferences.parallelIndexDownloads.length === 2 &&
                typeof rawPreferences.parallelIndexDownloads[0] === "boolean" &&
                typeof rawPreferences.parallelIndexDownloads[1] === "number" &&
                Math.round(rawPreferences.parallelIndexDownloads[1]) > 0
            ) {
                storedPreferences.parallelIndexDownloads = [
                    rawPreferences.parallelIndexDownloads[0],
                    Math.round(rawPreferences.parallelIndexDownloads[1]),
                ];
            }
            if (
                Array.isArray(rawPreferences.parallelDownloads) &&
                rawPreferences.parallelDownloads.length === 2 &&
                typeof rawPreferences.parallelDownloads[0] === "boolean" &&
                typeof rawPreferences.parallelDownloads[1] === "number" &&
                Math.round(rawPreferences.parallelDownloads[1]) > 0
            ) {
                storedPreferences.parallelDownloads = [
                    rawPreferences.parallelDownloads[0],
                    Math.round(rawPreferences.parallelDownloads[1]),
                ];
            }
            if (
                Array.isArray(rawPreferences.parallelDecompressions) &&
                rawPreferences.parallelDecompressions.length === 2 &&
                typeof rawPreferences.parallelDecompressions[0] === "boolean" &&
                typeof rawPreferences.parallelDecompressions[1] === "number" &&
                Math.round(rawPreferences.parallelDecompressions[1]) > 0
            ) {
                storedPreferences.parallelDecompressions = [
                    rawPreferences.parallelDecompressions[0],
                    Math.round(rawPreferences.parallelDecompressions[1]),
                ];
            }
            if (
                Array.isArray(rawPreferences.parallelDoiDownloads) &&
                rawPreferences.parallelDoiDownloads.length === 2 &&
                typeof rawPreferences.parallelDoiDownloads[0] === "boolean" &&
                typeof rawPreferences.parallelDoiDownloads[1] === "number" &&
                Math.round(rawPreferences.parallelDoiDownloads[1]) > 0
            ) {
                storedPreferences.parallelDoiDownloads = [
                    rawPreferences.parallelDoiDownloads[0],
                    Math.round(rawPreferences.parallelDoiDownloads[1]),
                ];
            }
            if (storedPreferences.parallelDecompressions[1] < 1) {
                storedPreferences.parallelDecompressions[1] =
                    availableParallelism;
            }
            if (typeof rawPreferences.keep === "boolean") {
                storedPreferences.keep = rawPreferences.keep;
            }

            if (
                Array.isArray(rawPreferences.doiTimeout) &&
                rawPreferences.doiTimeout.length === 2 &&
                typeof rawPreferences.doiTimeout[0] === "boolean" &&
                typeof rawPreferences.doiTimeout[1] === "number" &&
                rawPreferences.doiTimeout[1] > 0
            ) {
                storedPreferences.doiTimeout = [
                    rawPreferences.doiTimeout[0],
                    rawPreferences.doiTimeout[1],
                ];
            }

            invoke("load_configuration", {
                path: storedPreferences.configurationPath,
            }).catch(console.error);
            return new Preferences(
                storedPreferences,
                resolveTheme(
                    storedPreferences.selectedTheme,
                    prefersDarkTheme.matches
                ),
                availableParallelism,
                true
            );
        }
        return this;
    }

    newWithPrefersDark(prefersDark: boolean) {
        return new Preferences(
            this.storedPreferences,
            resolveTheme(this.storedPreferences.selectedTheme, prefersDark),
            this.availableParallelism,
            this.loaded
        );
    }
}

export const PreferencesContext = React.createContext<
    [Preferences, (storedPreferences: StoredPreferences) => void]
>([Preferences.default(), () => {}]);

export function usePreferences(): [
    Preferences,
    React.Dispatch<React.SetStateAction<Preferences>>,
    (storedPreferences: StoredPreferences) => void
] {
    const [preferences, setPreferences] = React.useState(Preferences.default());
    React.useEffect(() => {
        const listener = (event: MediaQueryListEvent) =>
            setPreferences(preferences =>
                preferences.newWithPrefersDark(event.matches)
            );
        prefersDarkTheme.addEventListener("change", listener);
        return () => prefersDarkTheme.removeEventListener("change", listener);
    }, []);
    return [
        preferences,
        setPreferences,
        (storedPreferences: StoredPreferences) => {
            invoke("store_preferences", { preferences: storedPreferences })
                .then(rawPreferencesAndAvailableParallelism =>
                    setPreferences(preferences =>
                        preferences.newWithRaw(
                            (
                                rawPreferencesAndAvailableParallelism as [
                                    StoredPreferences,
                                    number
                                ]
                            )[0],
                            (
                                rawPreferencesAndAvailableParallelism as [
                                    StoredPreferences,
                                    number
                                ]
                            )[1]
                        )
                    )
                )
                .catch(error => {
                    console.error(error);
                });
        },
    ];
}
