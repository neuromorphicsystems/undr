import * as React from "react";
import { DefaultTheme } from "styled-components";
import { invoke } from "@tauri-apps/api";

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
    content0: "#ffffff",
    content1: "#cccccc",
    content2: "#999999",
    link: "#4285F4",
    error: "#E08065",
    errorBackground: "#4B3532",
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

interface StoredPreferences {
    selectedTheme: "auto" | "light" | "dark";
    configurationPath: string | null;
}

class Preferences {
    storedPreferences: StoredPreferences;
    theme: DefaultTheme;
    loaded: boolean;

    constructor(
        storedPreferences: StoredPreferences,
        theme: DefaultTheme,
        loaded: boolean
    ) {
        this.storedPreferences = storedPreferences;
        this.theme = theme;
        this.loaded = loaded;
    }

    static default() {
        return new Preferences(
            {
                selectedTheme: "auto",
                configurationPath: null,
            },
            resolveTheme("auto", prefersDarkTheme.matches),
            false
        );
    }

    newWithRaw(rawPreferences: StoredPreferences) {
        if (
            typeof rawPreferences === "object" &&
            !Array.isArray(rawPreferences) &&
            rawPreferences !== null
        ) {
            const selectedTheme =
                rawPreferences.selectedTheme === "auto" ||
                rawPreferences.selectedTheme === "light" ||
                rawPreferences.selectedTheme === "dark"
                    ? rawPreferences.selectedTheme
                    : this.storedPreferences.selectedTheme;
            return new Preferences(
                {
                    selectedTheme,
                    configurationPath:
                        rawPreferences.configurationPath === null ||
                        typeof rawPreferences.configurationPath === "string"
                            ? rawPreferences.configurationPath
                            : this.storedPreferences.configurationPath,
                },
                resolveTheme(selectedTheme, prefersDarkTheme.matches),
                true
            );
        } else {
            return new Preferences(
                {
                    selectedTheme: this.storedPreferences.selectedTheme,
                    configurationPath: this.storedPreferences.configurationPath,
                },
                this.theme,
                true
            );
        }
    }

    newWithPrefersDark(prefersDark) {
        return new Preferences(
            {
                selectedTheme: this.storedPreferences.selectedTheme,
                configurationPath: this.storedPreferences.configurationPath,
            },
            resolveTheme(this.storedPreferences.selectedTheme, prefersDark),
            this.loaded
        );
    }
}

export function usePreferences(): [
    Preferences,
    (storedPreferences: StoredPreferences) => void
] {
    const [preferences, setPreferences] = React.useState(Preferences.default());
    React.useEffect(() => {
        invoke("load_preferences")
            .then(rawPreferences =>
                setPreferences(
                    preferences.newWithRaw(rawPreferences as StoredPreferences)
                )
            )
            .catch(error => {
                console.error(error);
            });
    }, []);
    React.useEffect(() => {
        const listener = (event: MediaQueryListEvent) =>
            setPreferences(preferences.newWithPrefersDark(event.matches));
        prefersDarkTheme.addEventListener("change", listener);
        return () => prefersDarkTheme.removeEventListener("change", listener);
    }, [preferences]);
    return [
        preferences,
        (storedPreferences: StoredPreferences) => {
            invoke("store_preferences", { preferences: storedPreferences })
                .then(rawPreferences =>
                    setPreferences(
                        preferences.newWithRaw(
                            rawPreferences as StoredPreferences
                        )
                    )
                )
                .catch(error => {
                    console.error(error);
                });
        },
    ];
}
