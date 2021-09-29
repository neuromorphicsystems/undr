import { Dataset, State, InterfaceAction } from "../common/types";

declare global {
    interface Window {
        undr: {
            interface: {
                run: (interfaceAction: InterfaceAction) => void;
            };
            theme: {
                load: () => string | null;
                store: (theme: string) => void;
                shouldUseDarkColors: () => boolean;
                onShouldUseDarkColorsUpdate: (
                    callback: (shouldUseDarkColors: boolean) => void
                ) => void;
                offShouldUseDarkColorsUpdate: (
                    callback: (shouldUseDarkColors: boolean) => void
                ) => void;
            };
            directory: {
                choose: () => void;
                show: () => void;
            };
            state: {
                load: () => State;
                onUpdate: (callback: (state: State) => void) => void;
                offUpdate: (callback: (state: State) => void) => void;
            };
            datasets: {
                addOrUpdate: (dataset: Dataset) => void;
                remove: (dataset: Dataset) => void;
            };
            bibtex: {
                export: () => void;
            };
            platform: string;
        };
    }
}

export {};
